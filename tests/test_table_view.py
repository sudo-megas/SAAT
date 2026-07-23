import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from saat.models import Watch
from saat.storage import create_watch, load_collection
from saat.ui.columns import DEFAULT_COLUMN_KEYS
from saat.ui.table_view import TableView

_app = QApplication.instance() or QApplication([])


class TableViewSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-table-selection-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="A"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="B"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="C"))
        self.records = load_collection(self.watches_dir)
        self.table = TableView(on_columns_changed=lambda keys: None)
        self.table.set_columns(DEFAULT_COLUMN_KEYS)
        self.table.set_records(self.records)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_selection_initially(self) -> None:
        self.assertEqual(self.table.selected_slugs(), set())

    def test_selecting_a_row_directly_reflects_in_selected_slugs(self) -> None:
        # selectRow() replaces the selection outright, even under
        # ExtendedSelection — verified empirically; real multi-row selection
        # (ctrl/shift-click) is exercised through set_selected_slugs() below.
        self.table.selectRow(0)
        self.assertEqual(self.table.selected_slugs(), {self.records[0].slug})

    def test_set_selected_slugs_selects_the_matching_rows(self) -> None:
        target = {self.records[1].slug}
        self.table.set_selected_slugs(target)
        self.assertEqual(self.table.selected_slugs(), target)

    def test_set_selected_slugs_does_not_emit_selection_changed(self) -> None:
        received = []
        self.table.selection_changed.connect(received.append)
        self.table.set_selected_slugs({self.records[0].slug})
        self.assertEqual(received, [])

    def test_a_real_selection_change_emits_selection_changed_with_the_slug_set(self) -> None:
        received = []
        self.table.selection_changed.connect(received.append)
        self.table.selectRow(0)
        self.assertEqual(received, [{self.records[0].slug}])

    def test_set_selected_slugs_replaces_rather_than_accumulates(self) -> None:
        self.table.set_selected_slugs({self.records[0].slug})
        self.table.set_selected_slugs({self.records[1].slug})
        self.assertEqual(self.table.selected_slugs(), {self.records[1].slug})


if __name__ == "__main__":
    unittest.main()
