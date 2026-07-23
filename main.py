# SAAT — Watch Collection Manager
# Copyright (C) 2026 sudo-megas
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from saat.config import Config
from saat.paths import resource_dir
from saat.ui.main_window import MainWindow
from saat.ui.theme import MODE_DARK, apply_theme, load_bundled_fonts


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SAAT")
    app.setWindowIcon(QIcon(str(resource_dir() / "resources" / "icon" / "saat.png")))

    load_bundled_fonts()

    config = Config()
    apply_theme(app, config.theme_mode() or MODE_DARK)

    window = MainWindow(config=config)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
