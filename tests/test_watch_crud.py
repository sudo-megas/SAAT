import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import dataclasses
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog

from saat.config import Config
from saat.image_import import import_image, thumbnail_path
from saat.models import Acquisition, Watch
from saat.storage import create_watch, load_collection, save_watch
from saat.ui.collection_view import CollectionView
from saat.ui.detail_view import DetailView
from saat.ui.dialogs import DeleteConfirmDialog
from saat.ui.empty_state import EmptyStateView
from saat.ui.main_window import MainWindow
from saat.ui.watch_form import WatchForm

_app = QApplication.instance() or QApplication([])


def _accept_with(images=None, **field_values):
    """Fake WatchForm.exec(): set fields on the real (unshown) form instance,
    call the real _on_save(), and return Accepted — exercises the actual
    validation/build logic without blocking on the modal event loop."""
    def _exec(self):
        if "brand" in field_values:
            self._brand.setText(field_values["brand"])
        if "model" in field_values:
            self._model.setText(field_values["model"])
        if "nickname" in field_values:
            self._nickname.setText(field_values["nickname"])
        if images:
            self.images_tab()._add_sources(images)
        self._on_save()
        return QDialog.DialogCode.Accepted
    return _exec


def _reject_exec(self):
    return QDialog.DialogCode.Rejected


class UITestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-crud-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _config(self) -> Config:
        return Config(self.tmp / "config.toml")


class AddFlowTests(UITestCase):
    def test_add_from_empty_state_creates_watch_and_shows_collection(self) -> None:
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        empty_state = window.centralWidget().currentWidget()
        self.assertIsInstance(empty_state, EmptyStateView)

        with patch.object(WatchForm, "exec", _accept_with(brand="Seiko", model="SARB033")):
            empty_state.add_watch_requested.emit()

        view = window.centralWidget().currentWidget()
        self.assertIsInstance(view, CollectionView)
        self.assertEqual(len(view.records), 1)
        self.assertEqual(view.records[0].watch.brand, "Seiko")

    def test_add_with_a_staged_image_commits_it_to_the_new_watchs_folder(self) -> None:
        from PIL import Image

        from saat.image_import import thumbnail_path

        source = self.tmp / "photo.jpg"
        Image.new("RGB", (800, 1000), (90, 70, 40)).save(source)

        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        empty_state = window.centralWidget().currentWidget()

        with patch.object(WatchForm, "exec", _accept_with(brand="Seiko", model="SARB033", images=[source])):
            empty_state.add_watch_requested.emit()

        view = window.centralWidget().currentWidget()
        [record] = view.records
        self.assertEqual(record.watch.images, ["photo.jpg"])
        images_dir = record.path / "images"
        self.assertTrue((images_dir / "photo.jpg").exists())
        self.assertTrue(thumbnail_path(images_dir, "photo.jpg").exists())

    def test_add_from_collection_top_bar_appends_to_existing_collection(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Casio", model="F-91W"))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()

        with patch.object(WatchForm, "exec", _accept_with(brand="Seiko", model="SARB033")):
            collection_view.add_watch_requested.emit()

        view = window.centralWidget().currentWidget()
        self.assertEqual(len(view.records), 2)

    def test_add_from_wishlist_scope_defaults_status_to_wishlist(self) -> None:
        """SPEC.md §5.12: otherwise the new watch saves as Owned and
        immediately vanishes from the scope it was just added from."""
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Casio", model="F-91W"))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()
        collection_view._top_bar.set_scope("wishlist")

        captured = {}

        def _capture_status_and_reject(self):
            captured["status"] = self._status.currentText()
            return QDialog.DialogCode.Rejected

        with patch.object(WatchForm, "exec", _capture_status_and_reject):
            collection_view.add_watch_requested.emit()

        self.assertEqual(captured["status"], "Wishlist")

    def test_cancelling_add_form_creates_nothing(self) -> None:
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        empty_state = window.centralWidget().currentWidget()

        with patch.object(WatchForm, "exec", _reject_exec):
            empty_state.add_watch_requested.emit()

        self.assertIsInstance(window.centralWidget().currentWidget(), EmptyStateView)
        self.assertEqual(load_collection(self.watches_dir), [])


class EditFlowTests(UITestCase):
    def test_edit_updates_watch_and_returns_to_its_detail_page(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()
        [record] = collection_view.records

        collection_view.record_activated.emit(record)
        detail_view = window.centralWidget().currentWidget()
        self.assertIsInstance(detail_view, DetailView)

        with patch.object(WatchForm, "exec", _accept_with(nickname="Cocktail Time")):
            detail_view.edit_requested.emit(record)

        current = window.centralWidget().currentWidget()
        self.assertIsInstance(current, DetailView)
        [updated] = load_collection(self.watches_dir)
        self.assertEqual(updated.watch.nickname, "Cocktail Time")
        self.assertEqual(updated.watch.brand, "Seiko")  # untouched fields survive

    def test_edit_of_an_unrelated_field_preserves_existing_images_and_their_order(self) -> None:
        from PIL import Image

        record = create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        images_dir = record.path / "images"
        for name, color in [("a.jpg", (90, 70, 40)), ("b.jpg", (60, 60, 65))]:
            source = self.tmp / name
            Image.new("RGB", (800, 1000), color).save(source)
            import_image(source, images_dir, name)
        record = save_watch(
            self.backups_dir,
            dataclasses.replace(record, watch=dataclasses.replace(record.watch, images=["a.jpg", "b.jpg"])),
        )

        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()
        [record] = collection_view.records

        collection_view.record_activated.emit(record)
        detail_view = window.centralWidget().currentWidget()

        with patch.object(WatchForm, "exec", _accept_with(nickname="Cocktail Time")):
            detail_view.edit_requested.emit(record)

        [updated] = load_collection(self.watches_dir)
        self.assertEqual(updated.watch.images, ["a.jpg", "b.jpg"])
        self.assertTrue((images_dir / "a.jpg").exists())
        self.assertTrue((images_dir / "b.jpg").exists())
        self.assertTrue(thumbnail_path(images_dir, "a.jpg").exists())
        self.assertTrue(thumbnail_path(images_dir, "b.jpg").exists())


class MoveToOwnedFlowTests(UITestCase):
    """SPEC.md §5.12: one action from the detail page, no dialog."""

    def test_price_defaults_from_target_price_when_unset(self) -> None:
        create_watch(
            self.watches_dir, self.backups_dir,
            Watch(brand="Seiko", model="SARB033", status="Wishlist", acquisition=Acquisition(target_price=650, currency="USD")),
        )
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()
        [record] = collection_view.records

        collection_view.record_activated.emit(record)
        detail_view = window.centralWidget().currentWidget()
        detail_view.move_to_owned_requested.emit(record)

        [updated] = load_collection(self.watches_dir)
        self.assertEqual(updated.watch.status, "Owned")
        self.assertEqual(updated.watch.acquisition.price, 650)
        self.assertEqual(updated.watch.acquisition.target_price, 650)  # left in place, not discarded

    def test_an_existing_price_is_not_overwritten_by_target_price(self) -> None:
        create_watch(
            self.watches_dir, self.backups_dir,
            Watch(
                brand="Seiko", model="SARB033", status="Wishlist",
                acquisition=Acquisition(price=400, target_price=650, currency="USD"),
            ),
        )
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()
        [record] = collection_view.records

        collection_view.record_activated.emit(record)
        detail_view = window.centralWidget().currentWidget()
        detail_view.move_to_owned_requested.emit(record)

        [updated] = load_collection(self.watches_dir)
        self.assertEqual(updated.watch.acquisition.price, 400)

    def test_returns_to_the_same_watchs_detail_page(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", status="Wishlist"))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()
        [record] = collection_view.records

        collection_view.record_activated.emit(record)
        detail_view = window.centralWidget().currentWidget()
        detail_view.move_to_owned_requested.emit(record)

        current = window.centralWidget().currentWidget()
        self.assertIsInstance(current, DetailView)
        self.assertEqual(current.record.watch.status, "Owned")


class DeleteFlowTests(UITestCase):
    def test_confirmed_delete_moves_folder_and_shows_empty_state(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()
        [record] = collection_view.records
        collection_view.record_activated.emit(record)
        detail_view = window.centralWidget().currentWidget()

        with patch.object(DeleteConfirmDialog, "exec", return_value=QDialog.DialogCode.Accepted):
            detail_view.delete_requested.emit(record)

        self.assertIsInstance(window.centralWidget().currentWidget(), EmptyStateView)
        self.assertEqual(load_collection(self.watches_dir), [])
        self.assertTrue((self.backups_dir / "deleted" / record.slug).exists())

    def test_cancelled_delete_keeps_the_watch(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()
        [record] = collection_view.records
        collection_view.record_activated.emit(record)
        detail_view = window.centralWidget().currentWidget()

        with patch.object(DeleteConfirmDialog, "exec", return_value=QDialog.DialogCode.Rejected):
            detail_view.delete_requested.emit(record)

        self.assertEqual(len(load_collection(self.watches_dir)), 1)


class DeleteConfirmDialogTests(UITestCase):
    def test_delete_button_enabled_only_when_typed_text_matches_model(self) -> None:
        dialog = DeleteConfirmDialog(Watch(brand="Seiko", model="SARB033"))
        self.assertFalse(dialog._delete_button.isEnabled())

        dialog._input.setText("SARB03")
        self.assertFalse(dialog._delete_button.isEnabled())

        dialog._input.setText("SARB033")
        self.assertTrue(dialog._delete_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
