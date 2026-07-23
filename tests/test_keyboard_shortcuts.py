import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QDialog

from saat.config import Config
from saat.models import Watch
from saat.storage import create_watch, load_collection
from saat.ui.compare_view import CompareView
from saat.ui.main_window import MainWindow
from saat.ui.watch_form import WatchForm

_app = QApplication.instance() or QApplication([])


def _shortcuts(window: MainWindow, sequence: str) -> list[QShortcut]:
    target = QKeySequence(sequence)
    return [sc for sc in window.findChildren(QShortcut) if sc.key() == target]


class UITestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-shortcuts-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _config(self) -> Config:
        return Config(self.tmp / "config.toml")

    def _window(self, count: int = 1) -> MainWindow:
        for model in "ABCDEF"[:count]:
            create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model=model))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        window.show()
        return window


class GlobalShortcutRegistrationTests(UITestCase):
    def test_each_expected_shortcut_is_registered_exactly_once(self) -> None:
        window = self._window()
        for sequence in ("Ctrl+N", "Ctrl+F", "Ctrl+E", "Ctrl+W", "Ctrl+Q", "Esc"):
            with self.subTest(sequence=sequence):
                self.assertEqual(len(_shortcuts(window, sequence)), 1)

    def test_ctrl_n_shortcut_is_wired_to_open_the_add_form(self) -> None:
        window = self._window()
        [shortcut] = _shortcuts(window, "Ctrl+N")

        with patch.object(WatchForm, "exec", return_value=QDialog.DialogCode.Rejected) as mock_exec:
            shortcut.activated.emit()

        mock_exec.assert_called_once()


class EditCurrentShortcutTests(UITestCase):
    def test_ctrl_e_while_on_detail_view_edits_the_shown_record(self) -> None:
        window = self._window()
        [record] = load_collection(self.watches_dir)
        window._show_detail(record)

        with patch.object(window, "_show_edit_form") as mock_edit:
            window._edit_current()

        mock_edit.assert_called_once_with(record)

    def test_ctrl_e_while_on_collection_view_does_nothing(self) -> None:
        window = self._window()

        with patch.object(window, "_show_edit_form") as mock_edit:
            window._edit_current()

        mock_edit.assert_not_called()


class WoreTodayCurrentShortcutTests(UITestCase):
    def test_ctrl_w_while_on_detail_view_marks_the_shown_record_worn(self) -> None:
        window = self._window()
        [record] = load_collection(self.watches_dir)
        window._show_detail(record)

        with patch.object(window, "_on_wore_today") as mock_wore:
            window._wore_today_current()

        mock_wore.assert_called_once_with(record)

    def test_ctrl_w_while_on_collection_view_does_nothing(self) -> None:
        window = self._window()

        with patch.object(window, "_on_wore_today") as mock_wore:
            window._wore_today_current()

        mock_wore.assert_not_called()

    def test_ctrl_w_end_to_end_persists_a_real_wear_record(self) -> None:
        window = self._window()
        [record] = load_collection(self.watches_dir)
        window._show_detail(record)

        window._wore_today_current()

        [reloaded] = load_collection(self.watches_dir)
        self.assertEqual(reloaded.watch.worn, [date.today()])


class FocusSearchShortcutTests(UITestCase):
    def test_ctrl_f_while_on_collection_view_focuses_the_search_field(self) -> None:
        window = self._window()
        QApplication.processEvents()

        window._focus_search()
        QApplication.processEvents()

        self.assertTrue(window._collection_view._top_bar._search_field.hasFocus())

    def test_ctrl_f_while_on_detail_view_does_nothing(self) -> None:
        window = self._window()
        [record] = load_collection(self.watches_dir)
        window._show_detail(record)
        QApplication.processEvents()

        window._focus_search()
        QApplication.processEvents()

        self.assertFalse(window._collection_view._top_bar._search_field.hasFocus())


class EscapeShortcutTests(UITestCase):
    def test_escape_from_detail_view_returns_to_collection(self) -> None:
        window = self._window()
        [record] = load_collection(self.watches_dir)
        window._show_detail(record)

        window._on_escape()

        self.assertIs(window.centralWidget().currentWidget(), window._collection_view)

    def test_escape_from_compare_view_returns_to_collection(self) -> None:
        window = self._window(count=2)
        collection_view = window.centralWidget().currentWidget()
        for card in collection_view._grid_view._cards:
            card._checkbox.setChecked(True)
        collection_view._top_bar._compare_button.click()
        self.assertIsInstance(window.centralWidget().currentWidget(), CompareView)

        window._on_escape()

        self.assertIs(window.centralWidget().currentWidget(), window._collection_view)

    def test_escape_while_on_collection_view_is_a_no_op(self) -> None:
        window = self._window()
        collection_view = window.centralWidget().currentWidget()

        window._on_escape()

        self.assertIs(window.centralWidget().currentWidget(), collection_view)


if __name__ == "__main__":
    unittest.main()
