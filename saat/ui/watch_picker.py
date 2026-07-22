from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from saat.storage import WatchRecord
from saat.ui.images import cropped_pixmap, first_image
from saat.ui.search import search_matches

THUMB_SIZE = 40


class WatchPicker(QDialog):
    """SPEC.md §5.5: "a compact picker (search field plus the collection as
    thumbnails)." Used for a single day or a drag-selected range alike —
    the caller decides what a pick or a Clear applies to. Only pre-marks the
    current watch for a single already-filled day; a multi-day range can
    have mixed owners, so there's no one watch to mark."""

    def __init__(
        self,
        records: list[WatchRecord],
        current: WatchRecord | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Assign a watch")
        self._records = [r for r in records if r.watch is not None]
        self._current_slug = current.slug if current is not None else None
        self._chosen: WatchRecord | None = None
        self._cleared = False

        self._search_field = QLineEdit()
        self._search_field.setPlaceholderText("Search brand, model, reference, caliber, tags…")
        self._search_field.textChanged.connect(self._render_list)

        self._list = QListWidget()
        self._list.setIconSize(QSize(THUMB_SIZE, THUMB_SIZE))
        # A single click picks and closes ("Pick one, the day fills" —
        # SPEC.md §5.5); itemActivated also catches Enter after arrow-key nav.
        self._list.itemClicked.connect(self._on_item_chosen)
        self._list.itemActivated.connect(self._on_item_chosen)

        buttons = QDialogButtonBox()
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self._on_clear)
        buttons.addButton(clear_button, QDialogButtonBox.ButtonRole.DestructiveRole)
        cancel_button = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._search_field)
        layout.addWidget(self._list, stretch=1)
        layout.addWidget(buttons)
        self.resize(420, 480)

        self._render_list()
        self._search_field.setFocus()

    def chosen_record(self) -> WatchRecord | None:
        return self._chosen

    def was_cleared(self) -> bool:
        return self._cleared

    def _render_list(self) -> None:
        self._list.clear()
        query = self._search_field.text()
        for record in self._records:
            if not search_matches(record.watch, query):
                continue
            label = f"{record.watch.brand} {record.watch.model}"
            if record.slug == self._current_slug:
                label += "  (current)"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, record)
            path = first_image(record)
            pixmap = cropped_pixmap(path, THUMB_SIZE, THUMB_SIZE) if path else None
            if pixmap is not None:
                item.setIcon(QIcon(pixmap))
            self._list.addItem(item)

    def _on_item_chosen(self, item: QListWidgetItem) -> None:
        self._chosen = item.data(Qt.ItemDataRole.UserRole)
        self._cleared = False
        self.accept()

    def _on_clear(self) -> None:
        self._chosen = None
        self._cleared = True
        self.accept()
