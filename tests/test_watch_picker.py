import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from saat.models import Watch
from saat.storage import WatchRecord
from saat.ui.watch_picker import WatchPicker

_app = QApplication.instance() or QApplication([])


def _record(slug: str, brand: str, model: str) -> WatchRecord:
    return WatchRecord(slug=slug, path=Path(f"/nonexistent/{slug}"), watch=Watch(brand=brand, model=model))


class WatchPickerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = [
            _record("seiko-skx007", "Seiko", "SKX007"),
            _record("omega-speedmaster", "Omega", "Speedmaster"),
        ]

    def test_lists_every_watch_by_default(self) -> None:
        picker = WatchPicker(self.records)
        self.assertEqual(picker._list.count(), 2)

    def test_search_narrows_the_list(self) -> None:
        picker = WatchPicker(self.records)
        picker._search_field.setText("skx")
        self.assertEqual(picker._list.count(), 1)
        self.assertIn("SKX007", picker._list.item(0).text())

    def test_current_watch_is_marked(self) -> None:
        picker = WatchPicker(self.records, current=self.records[0])
        item = picker._list.item(0)
        self.assertIn("(current)", item.text())

    def test_clicking_an_item_chooses_it_and_accepts(self) -> None:
        picker = WatchPicker(self.records)
        picker._on_item_chosen(picker._list.item(1))
        self.assertEqual(picker.chosen_record().slug, "omega-speedmaster")
        self.assertFalse(picker.was_cleared())

    def test_clear_button_accepts_with_no_chosen_record(self) -> None:
        picker = WatchPicker(self.records)
        picker._on_clear()
        self.assertIsNone(picker.chosen_record())
        self.assertTrue(picker.was_cleared())

    def test_malformed_records_are_not_offered(self) -> None:
        broken = WatchRecord(slug="broken", path=Path("/nonexistent/broken"), watch=None, load_error="bad toml")
        picker = WatchPicker([*self.records, broken])
        self.assertEqual(picker._list.count(), 2)


if __name__ == "__main__":
    unittest.main()
