from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from saat.image_import import import_image, remove_image
from saat.storage import WatchRecord
from saat.ui import icons
from saat.ui.images import IMAGE_EXTENSIONS, cropped_pixmap, list_images

THUMB_SIZE = 64


@dataclass
class _PendingImage:
    filename: str
    display_path: Path       # where to read pixels from for the in-form preview
    source_path: Path | None  # set only for a newly added file still outside images/


class ImagesTab(QWidget):
    """Drag-and-drop and a file picker, copies files into the watch's
    images/, generates thumbnails with Pillow, allows reordering and setting
    the primary. See SPEC.md §5.7. Staged in memory until commit() — nothing
    touches disk until the dialog is actually saved."""

    changed = Signal()

    def __init__(self, record: WatchRecord | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._pending: list[_PendingImage] = []
        self._removed_existing: set[str] = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        hint = QLabel("Drag and drop image files here, or:")
        hint.setProperty("muted", True)
        layout.addWidget(hint)

        add_button = QPushButton("Add images…")
        icons.set_icon(add_button, "image-add")
        add_button.clicked.connect(self._pick_files)
        layout.addWidget(add_button, alignment=Qt.AlignmentFlag.AlignLeft)

        self._rows_layout = QVBoxLayout()
        self._rows_layout.setSpacing(6)
        layout.addLayout(self._rows_layout)
        layout.addStretch()

        if record is not None and record.watch is not None:
            for path in list_images(record):
                self._pending.append(_PendingImage(filename=path.name, display_path=path, source_path=None))
        self._render()

    def filenames(self) -> list[str]:
        return [item.filename for item in self._pending]

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        self._add_sources(p for p in paths if p.suffix.lower() in IMAGE_EXTENSIONS)

    def _pick_files(self) -> None:
        filter_str = "Images (*" + " *".join(sorted(IMAGE_EXTENSIONS)) + ")"
        paths, _ = QFileDialog.getOpenFileNames(self, "Add images", "", filter_str)
        self._add_sources(Path(p) for p in paths)

    def _add_sources(self, paths) -> None:
        added = False
        for path in paths:
            filename = self._unique_filename(path.name)
            self._pending.append(_PendingImage(filename=filename, display_path=path, source_path=path))
            added = True
        if added:
            self._render()
            self.changed.emit()

    def _unique_filename(self, name: str) -> str:
        existing = {item.filename for item in self._pending}
        if name not in existing:
            return name
        stem, suffix = Path(name).stem, Path(name).suffix
        n = 2
        while f"{stem}-{n}{suffix}" in existing:
            n += 1
        return f"{stem}-{n}{suffix}"

    def _remove(self, item: _PendingImage) -> None:
        if item.source_path is None:
            self._removed_existing.add(item.filename)
        self._pending.remove(item)
        self._render()
        self.changed.emit()

    def _move(self, item: _PendingImage, delta: int) -> None:
        i = self._pending.index(item)
        j = i + delta
        if 0 <= j < len(self._pending):
            self._pending[i], self._pending[j] = self._pending[j], self._pending[i]
            self._render()
            self.changed.emit()

    def _set_primary(self, item: _PendingImage) -> None:
        self._pending.remove(item)
        self._pending.insert(0, item)
        self._render()
        self.changed.emit()

    def _render(self) -> None:
        while self._rows_layout.count():
            child = self._rows_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for index, item in enumerate(self._pending):
            self._rows_layout.addWidget(self._build_row(item, is_primary=index == 0))

    def _build_row(self, item: _PendingImage, is_primary: bool) -> QWidget:
        row = QFrame()
        row.setProperty("class", "form-list-row")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        thumb = QLabel()
        thumb.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        pixmap = cropped_pixmap(item.display_path, THUMB_SIZE, THUMB_SIZE)
        if pixmap is not None:
            thumb.setPixmap(pixmap)
        else:
            thumb.setProperty("class", "strap-photo-placeholder")
        layout.addWidget(thumb)

        name_col = QVBoxLayout()
        name_label = QLabel(item.filename)
        name_col.addWidget(name_label)
        if is_primary:
            badge = QLabel("PRIMARY")
            badge.setProperty("class", "fitted-badge")
            name_col.addWidget(badge)
        layout.addLayout(name_col, 1)

        up_button = QPushButton("Up")
        up_button.setEnabled(not is_primary)
        up_button.clicked.connect(lambda: self._move(item, -1))
        layout.addWidget(up_button)

        down_button = QPushButton("Down")
        down_button.setEnabled(item is not self._pending[-1])
        down_button.clicked.connect(lambda: self._move(item, 1))
        layout.addWidget(down_button)

        if not is_primary:
            primary_button = QPushButton("Set Primary")
            icons.set_icon(primary_button, "star")
            primary_button.clicked.connect(lambda: self._set_primary(item))
            layout.addWidget(primary_button)

        remove_button = QPushButton()
        remove_button.setProperty("variant", "link")
        remove_button.setToolTip("Remove image")
        icons.set_icon(remove_button, "remove")
        remove_button.clicked.connect(lambda: self._remove(item))
        layout.addWidget(remove_button)

        return row

    def commit(self, images_dir: Path) -> list[str]:
        """Copies staged files in, generates their thumbnails, deletes
        removed files. Call only after the watch's own record.path is known
        (i.e. after create_watch()/save_watch() succeeds)."""
        for filename in self._removed_existing:
            remove_image(images_dir, filename)

        for item in self._pending:
            if item.source_path is not None:
                import_image(item.source_path, images_dir, item.filename)

        return self.filenames()
