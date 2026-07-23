import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from saat.models import Watch
from saat.storage import create_watch, load_collection
from saat.ui.grid_view import GridView

_app = QApplication.instance() or QApplication([])


class GridViewKeyboardNavTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-grid-keyboard-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _view(self, count: int = 6) -> GridView:
        for model in "ABCDEF"[:count]:
            create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model=model))
        records = sorted(load_collection(self.watches_dir), key=lambda r: r.watch.model)
        view = GridView()
        view.set_records(records)
        view.resize(1400, 900)
        view.show()
        QApplication.processEvents()
        self.assertGreaterEqual(view._columns, 2, "test needs at least two columns to be meaningful")
        return view

    def test_focusing_the_grid_puts_the_cursor_on_the_first_card(self) -> None:
        view = self._view()
        view.setFocus()
        QApplication.processEvents()

        self.assertTrue(view._cards[0].property("cursor-focused"))
        view.close()

    def test_losing_focus_hides_the_cursor_ring(self) -> None:
        view = self._view()
        view.setFocus()
        QApplication.processEvents()
        view.clearFocus()
        QApplication.processEvents()

        self.assertFalse(view._cards[0].property("cursor-focused"))
        view.close()

    def test_right_arrow_moves_the_cursor_to_the_next_card(self) -> None:
        view = self._view()
        view.setFocus()
        QApplication.processEvents()

        QTest.keyClick(view, Qt.Key.Key_Right)

        self.assertFalse(view._cards[0].property("cursor-focused"))
        self.assertTrue(view._cards[1].property("cursor-focused"))
        view.close()

    def test_left_arrow_at_the_first_card_stays_put(self) -> None:
        view = self._view()
        view.setFocus()
        QApplication.processEvents()

        QTest.keyClick(view, Qt.Key.Key_Left)

        self.assertTrue(view._cards[0].property("cursor-focused"))
        view.close()

    def test_down_arrow_moves_the_cursor_by_the_column_count(self) -> None:
        view = self._view()
        columns = view._columns
        view.setFocus()
        QApplication.processEvents()

        QTest.keyClick(view, Qt.Key.Key_Down)

        self.assertTrue(view._cards[columns].property("cursor-focused"))
        view.close()

    def test_up_arrow_past_the_top_row_stays_put(self) -> None:
        view = self._view()
        view.setFocus()
        QApplication.processEvents()

        QTest.keyClick(view, Qt.Key.Key_Up)

        self.assertTrue(view._cards[0].property("cursor-focused"))
        view.close()

    def test_enter_activates_the_focused_card(self) -> None:
        view = self._view()
        view.setFocus()
        QApplication.processEvents()
        received = []
        view.record_activated.connect(received.append)

        QTest.keyClick(view, Qt.Key.Key_Right)
        QTest.keyClick(view, Qt.Key.Key_Return)

        self.assertEqual(received, [view._cards[1].record])
        view.close()

    def test_rebuilding_records_resets_the_cursor(self) -> None:
        view = self._view()
        view.setFocus()
        QApplication.processEvents()
        QTest.keyClick(view, Qt.Key.Key_Right)
        self.assertIsNotNone(view._focus_index)

        records = sorted(load_collection(self.watches_dir), key=lambda r: r.watch.model)
        view.set_records(records)

        self.assertIsNone(view._focus_index)
        view.close()


if __name__ == "__main__":
    unittest.main()
