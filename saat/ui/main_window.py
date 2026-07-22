from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow

from saat.config import Config
from saat.paths import app_dir
from saat.storage import load_collection
from saat.ui.collection_view import CollectionView
from saat.ui.empty_state import EmptyStateView

MIN_SIZE = QSize(1100, 700)
DEFAULT_SIZE = QSize(1600, 1000)


class MainWindow(QMainWindow):
    def __init__(
        self,
        watches_dir: Path | None = None,
        backups_dir: Path | None = None,
        config: Config | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("SAAT")
        self.setMinimumSize(MIN_SIZE)

        self._watches_dir = watches_dir if watches_dir is not None else app_dir() / "watches"
        self._backups_dir = backups_dir if backups_dir is not None else app_dir() / "backups"
        self._config = config if config is not None else Config()
        self._restore_geometry()

        self._load_and_show_collection()

    def _load_and_show_collection(self) -> None:
        records = load_collection(self._watches_dir)
        if records:
            self.setCentralWidget(CollectionView(records, self._config, self))
        else:
            self.setCentralWidget(EmptyStateView(self._watches_dir, self))

    def _restore_geometry(self) -> None:
        geometry = self._config.window_geometry()
        if not geometry or "width" not in geometry or "height" not in geometry:
            self.resize(DEFAULT_SIZE)
            return

        width = max(int(geometry["width"]), MIN_SIZE.width())
        height = max(int(geometry["height"]), MIN_SIZE.height())
        self.resize(width, height)

        x, y = geometry.get("x"), geometry.get("y")
        if x is not None and y is not None:
            self.move(int(x), int(y))

        if geometry.get("maximized"):
            self.setWindowState(Qt.WindowState.WindowMaximized)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._config.set_window_geometry({
            "width": self.width(),
            "height": self.height(),
            "x": self.x(),
            "y": self.y(),
            "maximized": self.isMaximized(),
        })
        self._config.save()
        super().closeEvent(event)
