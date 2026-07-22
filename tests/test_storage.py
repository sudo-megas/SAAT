import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from saat.models import LogEntry, Movement, Strap, TimingEntry, Watch
from saat.storage import (
    BACKUP_KEEP,
    WATCH_FILENAME,
    create_watch,
    delete_watch,
    load_collection,
    save_watch,
    slugify,
    unique_slug,
)


def full_watch() -> Watch:
    return Watch(
        brand="Seiko",
        model="SARB033",
        reference="SARB033",
        nickname="",
        serial="123456",
        group="Seiko Group",
        style="Dress",
        status="Owned",
        storage="Box 2, slot 4",
        rating=4,
        tags=["daily", "grail"],
        movement=Movement(caliber="6R15", kind="Automatic", power_reserve_hours=50, jewels=23, bph=21600),
        straps=[Strap(material="Leather", fitted=True), Strap(material="NATO", fitted=False)],
        log=[LogEntry(date=date(2024, 1, 1), kind="Service", note="Full service")],
        worn=[date(2024, 1, 1), date(2024, 1, 2)],
        timing=[TimingEntry(date=date(2024, 1, 1), deviation_sec=3, position="Dial Up")],
        notes="A daily beater.",
    )


class StorageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


class SlugTests(unittest.TestCase):
    def test_basic(self) -> None:
        self.assertEqual(slugify("Seiko", "SARB033"), "seiko-sarb033")

    def test_non_alphanumeric_collapses_to_hyphens(self) -> None:
        self.assertEqual(slugify("Grand Seiko", "SBGA211 (Snowflake)"), "grand-seiko-sbga211-snowflake")

    def test_unique_slug_appends_counter_on_collision(self) -> None:
        existing = {"seiko-sarb033"}
        self.assertEqual(unique_slug("Seiko", "SARB033", existing), "seiko-sarb033-2")
        existing.add("seiko-sarb033-2")
        self.assertEqual(unique_slug("Seiko", "SARB033", existing), "seiko-sarb033-3")


class RoundTripTests(StorageTestCase):
    def test_create_and_reload(self) -> None:
        original = full_watch()
        record = create_watch(self.watches_dir, self.backups_dir, original)
        self.assertEqual(record.slug, "seiko-sarb033")
        self.assertTrue((record.path / WATCH_FILENAME).exists())
        self.assertTrue((record.path / "images").is_dir())

        [reloaded] = load_collection(self.watches_dir)
        self.assertIsNone(reloaded.load_error)
        self.assertEqual(reloaded.watch.brand, "Seiko")
        self.assertEqual(reloaded.watch.model, "SARB033")
        self.assertEqual(reloaded.watch.tags, ["daily", "grail"])
        self.assertEqual(reloaded.watch.movement.caliber, "6R15")
        self.assertEqual(reloaded.watch.movement.bph, 21600)
        self.assertEqual(len(reloaded.watch.straps), 2)
        self.assertTrue(reloaded.watch.straps[0].fitted)
        self.assertEqual(reloaded.watch.worn, [date(2024, 1, 1), date(2024, 1, 2)])
        self.assertEqual(reloaded.watch.log[0].note, "Full service")
        self.assertEqual(reloaded.watch.timing[0].deviation_sec, 3)
        self.assertEqual(reloaded.watch.notes, "A daily beater.")

    def test_minimal_watch_saves_with_only_brand_and_model(self) -> None:
        record = create_watch(self.watches_dir, self.backups_dir, Watch(brand="Casio", model="F-91W"))
        [reloaded] = load_collection(self.watches_dir)
        self.assertIsNone(reloaded.load_error)
        self.assertEqual(reloaded.watch.brand, "Casio")
        self.assertIsNone(reloaded.watch.rating)

    def test_save_preserves_hand_written_comments(self) -> None:
        folder = self.watches_dir / "seiko-sarb033"
        (folder / "images").mkdir(parents=True)
        (folder / WATCH_FILENAME).write_text(
            'brand = "Seiko"\n'
            'model = "SARB033"\n'
            "\n"
            "[movement]\n"
            'caliber = "6R15"\n'
            "accuracy_min = -20  # accuracy not published by the manufacturer\n",
            encoding="utf-8",
        )

        [record] = load_collection(self.watches_dir)
        record.watch.rating = 5
        save_watch(self.backups_dir, record)

        text = (folder / WATCH_FILENAME).read_text(encoding="utf-8")
        self.assertIn("# accuracy not published by the manufacturer", text)
        self.assertIn("rating = 5", text)

    def test_atomic_write_leaves_no_tmp_file(self) -> None:
        record = create_watch(self.watches_dir, self.backups_dir, Watch(brand="Casio", model="F-91W"))
        tmp_path = record.path / (WATCH_FILENAME + ".tmp")
        self.assertFalse(tmp_path.exists())


class LoaderToleranceTests(StorageTestCase):
    def test_underscore_and_dot_prefixed_dirs_are_skipped(self) -> None:
        for name in ("_template", ".hidden"):
            folder = self.watches_dir / name
            folder.mkdir()
            (folder / WATCH_FILENAME).write_text('brand = "X"\nmodel = "Y"\n', encoding="utf-8")

        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Casio", model="F-91W"))

        records = load_collection(self.watches_dir)
        self.assertEqual([r.slug for r in records], ["casio-f-91w"])

    def test_malformed_toml_does_not_raise(self) -> None:
        folder = self.watches_dir / "broken"
        folder.mkdir()
        (folder / WATCH_FILENAME).write_text("brand = ][not valid toml", encoding="utf-8")

        [record] = load_collection(self.watches_dir)
        self.assertEqual(record.slug, "broken")
        self.assertIsNone(record.watch)
        self.assertIsNotNone(record.load_error)

    def test_missing_required_fields_does_not_raise(self) -> None:
        folder = self.watches_dir / "no-brand"
        folder.mkdir()
        (folder / WATCH_FILENAME).write_text('nickname = "Mystery watch"\n', encoding="utf-8")

        [record] = load_collection(self.watches_dir)
        self.assertIsNone(record.watch)
        self.assertIn("brand", record.load_error)

    def test_missing_watches_dir_returns_empty(self) -> None:
        self.assertEqual(load_collection(self.tmp / "does-not-exist"), [])


class BackupTests(StorageTestCase):
    def test_no_backup_on_first_save(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, full_watch())
        self.assertFalse(self.backups_dir.exists())

    def test_backup_created_on_overwrite(self) -> None:
        record = create_watch(self.watches_dir, self.backups_dir, full_watch())
        record.watch.rating = 1
        save_watch(self.backups_dir, record)

        backups = list(self.backups_dir.glob("seiko-sarb033-*.toml"))
        self.assertEqual(len(backups), 1)

    def test_backups_pruned_to_newest_20(self) -> None:
        record = create_watch(self.watches_dir, self.backups_dir, full_watch())
        for i in range(25):
            record.watch.rating = i % 5
            record = save_watch(self.backups_dir, record)

        backups = [p for p in self.backups_dir.iterdir() if p.is_file()]
        self.assertEqual(len(backups), BACKUP_KEEP)


class DeleteTests(StorageTestCase):
    def test_delete_moves_whole_folder_to_backups_deleted(self) -> None:
        record = create_watch(self.watches_dir, self.backups_dir, full_watch())
        (record.path / "images" / "main.jpg").write_bytes(b"fake-jpeg-bytes")

        delete_watch(self.backups_dir, record)

        self.assertFalse(record.path.exists())
        moved = self.backups_dir / "deleted" / "seiko-sarb033"
        self.assertTrue((moved / WATCH_FILENAME).exists())
        self.assertTrue((moved / "images" / "main.jpg").exists())

    def test_delete_does_not_use_rm_rf_on_watches_dir(self) -> None:
        record = create_watch(self.watches_dir, self.backups_dir, full_watch())
        delete_watch(self.backups_dir, record)
        self.assertTrue(self.watches_dir.exists())


if __name__ == "__main__":
    unittest.main()
