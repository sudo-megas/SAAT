import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

from saat.sellers import Seller, load_sellers, sellers_path
from saat.ui.sellers_dialog import SellersDialog

_app = QApplication.instance() or QApplication([])


class SellersDialogTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-sellers-dialog-test-"))
        self.backups_dir = self.tmp / "backups"
        self.path = sellers_path(self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


class SellersDialogTests(SellersDialogTestCase):
    def test_constructing_with_existing_sellers_lists_them(self) -> None:
        dialog = SellersDialog([Seller(name="A"), Seller(name="B")], self.backups_dir, self.path)
        self.assertEqual(dialog._list.count(), 2)
        self.assertEqual(dialog._list.item(0).text(), "A")

    def test_adding_a_new_seller_persists_and_appears_in_the_list(self) -> None:
        dialog = SellersDialog([], self.backups_dir, self.path)
        dialog._name.setText("Some Shop")
        dialog._url.setText("https://example.com")
        dialog._on_save()

        self.assertEqual(dialog.sellers(), [Seller(name="Some Shop", url="https://example.com")])
        self.assertEqual(load_sellers(self.path), [Seller(name="Some Shop", url="https://example.com")])
        self.assertEqual(dialog._list.count(), 1)

    def test_saving_with_a_blank_name_warns_and_does_not_add(self) -> None:
        dialog = SellersDialog([], self.backups_dir, self.path)
        with patch.object(QMessageBox, "warning") as warning:
            dialog._on_save()
        warning.assert_called_once()
        self.assertEqual(dialog.sellers(), [])

    def test_selecting_a_list_item_populates_the_form(self) -> None:
        dialog = SellersDialog([Seller(name="Some Shop", url="https://example.com", city="Istanbul")], self.backups_dir, self.path)
        dialog._list.setCurrentRow(0)
        self.assertEqual(dialog._name.text(), "Some Shop")
        self.assertEqual(dialog._url.text(), "https://example.com")
        self.assertEqual(dialog._city.text(), "Istanbul")

    def test_editing_the_selected_entry_updates_in_place(self) -> None:
        dialog = SellersDialog([Seller(name="Some Shop"), Seller(name="Other Shop")], self.backups_dir, self.path)
        dialog._list.setCurrentRow(0)
        dialog._city.setText("Ankara")
        dialog._on_save()

        self.assertEqual(len(dialog.sellers()), 2)  # updated, not duplicated
        updated = next(s for s in dialog.sellers() if s.name == "Some Shop")
        self.assertEqual(updated.city, "Ankara")

    def test_deleting_the_selected_entry_removes_it(self) -> None:
        dialog = SellersDialog([Seller(name="Some Shop"), Seller(name="Other Shop")], self.backups_dir, self.path)
        dialog._list.setCurrentRow(0)
        dialog._on_delete()

        self.assertEqual([s.name for s in dialog.sellers()], ["Other Shop"])
        self.assertEqual([s.name for s in load_sellers(self.path)], ["Other Shop"])

    def test_delete_button_disabled_until_something_is_selected(self) -> None:
        dialog = SellersDialog([Seller(name="Some Shop")], self.backups_dir, self.path)
        self.assertFalse(dialog._delete_button.isEnabled())
        dialog._list.setCurrentRow(0)
        self.assertTrue(dialog._delete_button.isEnabled())

    def test_new_clears_the_form_and_deselects(self) -> None:
        dialog = SellersDialog([Seller(name="Some Shop")], self.backups_dir, self.path)
        dialog._list.setCurrentRow(0)
        dialog._on_new()
        self.assertEqual(dialog._name.text(), "")
        self.assertEqual(dialog._list.currentRow(), -1)
        self.assertFalse(dialog._delete_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
