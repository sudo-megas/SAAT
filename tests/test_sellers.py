import shutil
import tempfile
import unittest
from pathlib import Path

from saat.models import Acquisition, Watch
from saat.sellers import Seller, find_seller, load_sellers, save_sellers, sellers_path
from saat.storage import create_watch

WATCH_FILENAME = "watch.toml"


class SellersTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-sellers-test-"))
        self.data_dir = self.tmp
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()
        self.path = sellers_path(self.data_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


class SellersPathTests(unittest.TestCase):
    def test_lives_beside_watches_not_config(self) -> None:
        """SPEC.md §3: data_dir(), not config_dir() — user-authored content
        that travels with the collection."""
        self.assertEqual(sellers_path(Path("/some/data/dir")), Path("/some/data/dir/sellers.toml"))


class LoadSellersTests(SellersTestCase):
    def test_missing_file_returns_empty_list(self) -> None:
        """SPEC.md §3: ships absent — the app works normally without it."""
        self.assertEqual(load_sellers(self.path), [])

    def test_round_trips_every_field(self) -> None:
        seller = Seller(name="Some Shop", url="https://example.com", city="Istanbul", notes="Good prices")
        save_sellers(self.backups_dir, self.path, [seller])

        [reloaded] = load_sellers(self.path)
        self.assertEqual(reloaded, seller)

    def test_optional_fields_may_be_absent(self) -> None:
        save_sellers(self.backups_dir, self.path, [Seller(name="Bare Shop")])
        [reloaded] = load_sellers(self.path)
        self.assertEqual(reloaded, Seller(name="Bare Shop", url=None, city=None, notes=None))

    def test_multiple_sellers_preserve_order(self) -> None:
        save_sellers(self.backups_dir, self.path, [Seller(name="A"), Seller(name="B"), Seller(name="C")])
        self.assertEqual([s.name for s in load_sellers(self.path)], ["A", "B", "C"])

    def test_malformed_file_returns_empty_list_without_crashing(self) -> None:
        self.path.write_text("name = ][not valid toml", encoding="utf-8")
        self.assertEqual(load_sellers(self.path), [])

    def test_an_entry_missing_a_name_is_skipped(self) -> None:
        self.path.write_text('[[seller]]\nurl = "https://example.com"\n', encoding="utf-8")
        self.assertEqual(load_sellers(self.path), [])


class SaveSellersBackupTests(SellersTestCase):
    def test_no_backup_on_first_save(self) -> None:
        save_sellers(self.backups_dir, self.path, [Seller(name="A")])
        self.assertFalse(self.backups_dir.exists())

    def test_overwrite_creates_a_backup(self) -> None:
        """SPEC.md §3: sellers.toml falls under the backup scheme, same as
        watch.toml — reuses storage.backup_watch_toml's pruned rotation."""
        save_sellers(self.backups_dir, self.path, [Seller(name="A")])
        save_sellers(self.backups_dir, self.path, [Seller(name="A"), Seller(name="B")])

        backups = list(self.backups_dir.glob("sellers-*.toml"))
        self.assertEqual(len(backups), 1)
        self.assertIn('name = "A"', backups[0].read_text(encoding="utf-8"))


class FindSellerTests(unittest.TestCase):
    def test_exact_match(self) -> None:
        sellers = [Seller(name="Some Shop", url="https://example.com")]
        self.assertEqual(find_seller(sellers, "Some Shop").url, "https://example.com")

    def test_no_match_returns_none(self) -> None:
        sellers = [Seller(name="Some Shop")]
        self.assertIsNone(find_seller(sellers, "Other Shop"))

    def test_match_is_case_sensitive(self) -> None:
        sellers = [Seller(name="Some Shop")]
        self.assertIsNone(find_seller(sellers, "some shop"))


class LooseCouplingTests(SellersTestCase):
    """SPEC.md §3: deleting a sellers.toml entry must never orphan or alter
    a watch — the strongest form of that guarantee is that the watch.toml
    bytes on disk don't change at all."""

    def test_deleting_a_seller_entry_leaves_every_watch_toml_byte_identical(self) -> None:
        record = create_watch(
            self.watches_dir, self.backups_dir,
            Watch(brand="Seiko", model="SARB033", acquisition=Acquisition(seller="Some Shop")),
        )
        watch_toml_path = record.path / WATCH_FILENAME
        before = watch_toml_path.read_bytes()

        save_sellers(self.backups_dir, self.path, [Seller(name="Some Shop", url="https://example.com")])
        save_sellers(self.backups_dir, self.path, [])  # the deletion

        after = watch_toml_path.read_bytes()
        self.assertEqual(before, after)

    def test_the_watchs_seller_string_is_untouched_after_deletion(self) -> None:
        from saat.storage import load_collection

        create_watch(
            self.watches_dir, self.backups_dir,
            Watch(brand="Seiko", model="SARB033", acquisition=Acquisition(seller="Some Shop")),
        )
        save_sellers(self.backups_dir, self.path, [Seller(name="Some Shop")])
        save_sellers(self.backups_dir, self.path, [])

        [reloaded] = load_collection(self.watches_dir)
        self.assertEqual(reloaded.watch.acquisition.seller, "Some Shop")


if __name__ == "__main__":
    unittest.main()
