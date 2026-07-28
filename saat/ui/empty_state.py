from pathlib import Path

from PySide6.QtCore import QEvent, QUrl, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QPaintEvent, QPainter
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from saat.paths import data_dir
from saat.ui import perlage, theme
from saat.ui.watch_dial import WatchDialWidget


class EmptyStateView(QWidget):
    """The first screen the owner ever sees: a live watch dial above a quiet
    line of copy -- a technical drawing in the app's own hairline vocabulary,
    not the cartoon illustration SPEC.md §5.8 rules out."""

    add_watch_requested = Signal()

    def __init__(self, watches_dir: Path | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._watches_dir = watches_dir if watches_dir is not None else data_dir() / "watches"

        dial = WatchDialWidget()

        self._heading = QLabel()
        self._heading.setProperty("role", "empty-heading")
        self._heading.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._body = QLabel()
        self._body.setProperty("muted", True)
        self._body.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._add_button = QPushButton()
        self._add_button.setProperty("variant", "primary")
        self._add_button.clicked.connect(self.add_watch_requested.emit)

        self._open_folder_button = QPushButton()
        self._open_folder_button.setProperty("variant", "link")
        self._open_folder_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_folder_button.clicked.connect(self._open_watches_folder)

        self._retranslate()

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)
        for widget in (dial, self._heading, self._body, self._add_button, self._open_folder_button):
            layout.addWidget(widget, alignment=Qt.AlignmentFlag.AlignHCenter)

    def _retranslate(self) -> None:
        self._heading.setText(self.tr("Your collection is empty."))
        self._body.setText(
            self.tr(
                "Watches live in the watches/ folder as editable TOML files.\n"
                "Add your first one to get started."
            )
        )
        self._add_button.setText(self.tr("Add watch"))
        self._open_folder_button.setText(self.tr("Open watches/ folder"))

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)

    def _open_watches_folder(self) -> None:
        self._watches_dir.mkdir(exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._watches_dir)))

    def paintEvent(self, event: QPaintEvent) -> None:
        # No existing background paint to preserve here (unlike Sidebar's
        # QSS one) -- fill the plate backdrop by hand, then tile perlage on
        # top of it. The dial widget paints its own opaque plate@ fill over
        # whatever's behind its own bounding box, so it isn't competing with
        # the texture underneath it.
        colors = theme.colors()
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(colors.plate))
        tile = perlage.render_perlage_tile(colors.plate, colors.rule)
        painter.fillRect(self.rect(), QBrush(tile))
        painter.end()
