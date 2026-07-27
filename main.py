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

from saat.autostart import AUTOSTART_FLAG
from saat.config import Config
from saat.paths import data_dir, resource_dir
from saat.single_instance import SingleInstanceGuard
from saat.ui.main_window import MainWindow
from saat.ui.theme import MODE_DARK, apply_theme, load_bundled_fonts


def main() -> int:
    # Read before QApplication(sys.argv) construction, which mutates the
    # argv list it's handed (stripping any Qt-recognized options) -- this
    # flag isn't one, but snapshotting first avoids depending on that.
    started_via_autostart = AUTOSTART_FLAG in sys.argv[1:]

    app = QApplication(sys.argv)
    app.setApplicationName("SAAT")
    app.setWindowIcon(QIcon(str(resource_dir() / "resources" / "icon" / "saat.png")))

    guard = SingleInstanceGuard(data_dir())
    if not guard.try_become_primary():
        # Another instance already owns this data_dir() and has been
        # signalled to raise itself -- exit silently, no error dialog.
        return 0

    load_bundled_fonts()

    config = Config()
    apply_theme(app, config.theme_mode() or MODE_DARK)

    window = MainWindow(config=config)
    guard.raise_requested.connect(window.bring_to_front)
    app.aboutToQuit.connect(guard.close)
    if not window.should_start_hidden(started_via_autostart):
        window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
