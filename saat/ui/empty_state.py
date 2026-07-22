from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from saat.paths import app_dir


class EmptyStateView(QWidget):
    """The first screen the owner ever sees: no collection, no illustration, no noise."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

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

        open_folder = QPushButton("Open watches/ folder")
        open_folder.setProperty("variant", "link")
        open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        open_folder.clicked.connect(self._open_watches_folder)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)
        for widget in (heading, body, add_button, open_folder):
            layout.addWidget(widget, alignment=Qt.AlignmentFlag.AlignHCenter)

    def _open_watches_folder(self) -> None:
        watches_dir = app_dir() / "watches"
        watches_dir.mkdir(exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(watches_dir)))
