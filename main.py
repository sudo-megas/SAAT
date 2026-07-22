import sys

from PySide6.QtWidgets import QApplication

from saat.config import Config
from saat.ui.main_window import MainWindow
from saat.ui.theme import MODE_DARK, apply_theme


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SAAT")

    config = Config()
    apply_theme(app, config.theme_mode() or MODE_DARK)

    window = MainWindow(config=config)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
