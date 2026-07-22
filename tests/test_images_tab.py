import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import dataclasses
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from PySide6.QtWidgets import QApplication

from saat.image_import import thumbnail_path
from saat.models import Watch
from saat.storage import create_watch, load_collection, save_watch
from saat.ui.images import list_images
from saat.ui.images_tab import ImagesTab
from saat.ui.watch_form import WatchForm

_app = QApplication.instance() or QApplication([])


class UITestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-images-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.source_dir = self.tmp / "sources"
        self.watches_dir.mkdir()
        self.source_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_source_image(self, name: str, size=(800, 1000), color=(120, 90, 60)) -> Path:
        path = self.source_dir / name
        Image.new("RGB", size, color).save(path)
        return path


class ImportAndThumbnailTests(UITestCase):
    def test_committing_a_new_image_copies_original_untouched_and_writes_thumbnail(self) -> None:
        record = create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        source = self._make_source_image("photo.jpg")

        tab = ImagesTab(record=None)
        tab._add_sources([source])
        images_dir = record.path / "images"
        result = tab.commit(images_dir)

        self.assertEqual(result, ["photo.jpg"])
        self.assertTrue((images_dir / "photo.jpg").exists())
        self.assertTrue(thumbnail_path(images_dir, "photo.jpg").exists())
        self.assertEqual((images_dir / "photo.jpg").read_bytes(), source.read_bytes())

        with Image.open(thumbnail_path(images_dir, "photo.jpg")) as thumb:
            self.assertLessEqual(max(thumb.size), 640)

    def test_full_round_trip_through_form_and_storage(self) -> None:
        source = self._make_source_image("main.jpg")

        form = WatchForm(records=[], record=None)
        form._brand.setText("Seiko")
        form._model.setText("SARB033")
        form.images_tab()._add_sources([source])
        form._on_save()

        created = create_watch(self.watches_dir, self.backups_dir, form.saved_watch())
        form.images_tab().commit(created.path / "images")

        [reloaded] = load_collection(self.watches_dir)
        self.assertEqual(reloaded.watch.images, ["main.jpg"])
        self.assertEqual([p.name for p in list_images(reloaded)], ["main.jpg"])
        self.assertTrue((created.path / "images" / "main.jpg").exists())
        self.assertTrue(thumbnail_path(created.path / "images", "main.jpg").exists())

    def test_removed_existing_image_is_deleted_from_disk_on_commit(self) -> None:
        record = create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        images_dir = record.path / "images"
        source = self._make_source_image("gone.jpg")
        tab = ImagesTab(record=None)
        tab._add_sources([source])
        tab.commit(images_dir)
        self.assertTrue((images_dir / "gone.jpg").exists())

        [record] = load_collection(self.watches_dir)
        record = save_watch(self.backups_dir, dataclasses.replace(record, watch=dataclasses.replace(record.watch, images=["gone.jpg"])))
        [record] = load_collection(self.watches_dir)

        tab2 = ImagesTab(record)
        self.assertEqual(tab2.filenames(), ["gone.jpg"])
        tab2._remove(tab2._pending[0])
        tab2.commit(images_dir)

        self.assertFalse((images_dir / "gone.jpg").exists())
        self.assertFalse(thumbnail_path(images_dir, "gone.jpg").exists())


class ReorderAndPrimaryTests(UITestCase):
    def test_set_primary_moves_image_to_front(self) -> None:
        a = self._make_source_image("a.jpg")
        b = self._make_source_image("b.jpg")

        tab = ImagesTab(record=None)
        tab._add_sources([a, b])
        self.assertEqual(tab.filenames(), ["a.jpg", "b.jpg"])

        tab._set_primary(tab._pending[1])
        self.assertEqual(tab.filenames(), ["b.jpg", "a.jpg"])

    def test_up_down_move_swaps_adjacent_images(self) -> None:
        a = self._make_source_image("a.jpg")
        b = self._make_source_image("b.jpg")
        c = self._make_source_image("c.jpg")

        tab = ImagesTab(record=None)
        tab._add_sources([a, b, c])
        tab._move(tab._pending[2], -1)  # move c up past b
        self.assertEqual(tab.filenames(), ["a.jpg", "c.jpg", "b.jpg"])


class StrapImageReferenceTests(UITestCase):
    def test_removing_a_referenced_image_nulls_the_strap_reference(self) -> None:
        record = create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        a = self._make_source_image("a.jpg")

        form = WatchForm(records=[record], record=record)
        form.images_tab()._add_sources([a])

        strap_row = form._straps_editor.add_row()
        index = strap_row.image_combo.findData("a.jpg")
        self.assertGreaterEqual(index, 0)
        strap_row.image_combo.setCurrentIndex(index)
        self.assertEqual(form._straps_editor.values()[0].image, "a.jpg")

        form.images_tab()._remove(form.images_tab()._pending[0])

        self.assertIsNone(form._straps_editor.values()[0].image)

    def test_reordering_images_does_not_disturb_an_unrelated_strap_reference(self) -> None:
        record = create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        a = self._make_source_image("a.jpg")
        b = self._make_source_image("b.jpg")

        form = WatchForm(records=[record], record=record)
        form.images_tab()._add_sources([a, b])

        strap_row = form._straps_editor.add_row()
        strap_row.image_combo.setCurrentIndex(strap_row.image_combo.findData("a.jpg"))

        form.images_tab()._set_primary(form.images_tab()._pending[1])  # promotes b.jpg

        self.assertEqual(strap_row.get_value().image, "a.jpg")


class BackwardCompatibilityTests(UITestCase):
    def test_legacy_watch_toml_without_images_field_falls_back_to_alphabetical(self) -> None:
        record = create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        images_dir = record.path / "images"
        shutil.copy2(self._make_source_image("wrist.jpg"), images_dir / "wrist.jpg")
        shutil.copy2(self._make_source_image("case.jpg"), images_dir / "case.jpg")

        import tomlkit
        toml_path = record.path / "watch.toml"
        doc = tomlkit.parse(toml_path.read_text(encoding="utf-8"))
        del doc["images"]  # simulate a watch.toml written before this field existed
        toml_path.write_text(tomlkit.dumps(doc), encoding="utf-8")

        [reloaded] = load_collection(self.watches_dir)
        self.assertEqual(reloaded.watch.images, [])
        names = [p.name for p in list_images(reloaded)]
        self.assertEqual(names, ["case.jpg", "wrist.jpg"])


if __name__ == "__main__":
    unittest.main()
