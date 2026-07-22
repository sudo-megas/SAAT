import sys

from PySide6.QtWidgets import QApplication

from saat.ui.main_window import MainWindow
from saat.ui.theme import apply_theme


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SAAT")
    apply_theme(app)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
