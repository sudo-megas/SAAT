from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow

from saat.config import Config
from saat.ui.empty_state import EmptyStateView

MIN_SIZE = QSize(1100, 700)
DEFAULT_SIZE = QSize(1600, 1000)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SAAT")
        self.setMinimumSize(MIN_SIZE)

        self._config = Config()
        self._restore_geometry()

        # No data layer yet — the empty state is the only screen milestone 1 renders.
        self.setCentralWidget(EmptyStateView(self))

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
