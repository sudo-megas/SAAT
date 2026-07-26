from pathlib import Path

from PySide6.QtCore import QUrl, Qt, Signal
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

        heading = QLabel("Your collection is empty.")
        heading.setProperty("role", "empty-heading")
        heading.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        body = QLabel(
            "Watches live in the watches/ folder as editable TOML files.\n"
            "Add your first one to get started."
        )
        body.setProperty("muted", True)
        body.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        add_button = QPushButton("Add watch")
        add_button.setProperty("variant", "primary")
        add_button.clicked.connect(self.add_watch_requested.emit)

        open_folder = QPushButton("Open watches/ folder")
        open_folder.setProperty("variant", "link")
        open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        open_folder.clicked.connect(self._open_watches_folder)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)
        for widget in (dial, heading, body, add_button, open_folder):
            layout.addWidget(widget, alignment=Qt.AlignmentFlag.AlignHCenter)

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
