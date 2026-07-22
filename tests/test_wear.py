import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

import tomlkit

from saat.models import Watch
from saat.storage import create_watch, load_collection
from saat.wear import assign_worn, build_worn_index, clear_worn, mark_worn_today


class WearTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-wear-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


class BuildWornIndexTests(WearTestCase):
    def test_index_maps_each_date_to_its_watch(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", worn=[date(2026, 1, 1)]))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Omega", model="Speedmaster", worn=[date(2026, 1, 2)]))
        records = load_collection(self.watches_dir)
        index = build_worn_index(records)
        self.assertEqual(index[date(2026, 1, 1)].watch.brand, "Seiko")
        self.assertEqual(index[date(2026, 1, 2)].watch.brand, "Omega")

    def test_malformed_record_is_skipped_not_crashed_on(self) -> None:
        broken = self.watches_dir / "broken"
        broken.mkdir()
        (broken / "watch.toml").write_text("brand = ][not valid", encoding="utf-8")
        records = load_collection(self.watches_dir)
        self.assertEqual(build_worn_index(records), {})


class AssignWornTests(WearTestCase):
    def test_assigning_an_unowned_date_saves_only_the_target(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        records = load_collection(self.watches_dir)
        [target] = records

        updated = assign_worn(self.backups_dir, records, [date(2026, 6, 1)], target)

        [reloaded] = load_collection(self.watches_dir)
        self.assertEqual(reloaded.watch.worn, [date(2026, 6, 1)])
        self.assertEqual(updated[0].watch.worn, [date(2026, 6, 1)])

    def test_one_watch_per_day_silently_steals_the_date_from_the_previous_owner(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", worn=[date(2026, 6, 1)]))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Omega", model="Speedmaster"))
        records = load_collection(self.watches_dir)
        seiko = next(r for r in records if r.watch.brand == "Seiko")
        omega = next(r for r in records if r.watch.brand == "Omega")

        assign_worn(self.backups_dir, records, [date(2026, 6, 1)], omega)

        reloaded = {r.watch.brand: r.watch.worn for r in load_collection(self.watches_dir)}
        self.assertEqual(reloaded["Seiko"], [])
        self.assertEqual(reloaded["Omega"], [date(2026, 6, 1)])

    def test_assigning_a_range_of_dates_at_once(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        records = load_collection(self.watches_dir)
        [target] = records
        date_range = [date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3)]

        assign_worn(self.backups_dir, records, date_range, target)

        [reloaded] = load_collection(self.watches_dir)
        self.assertEqual(reloaded.watch.worn, date_range)

    def test_reassigning_an_already_owned_date_to_the_same_watch_does_not_touch_disk(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", worn=[date(2026, 6, 1)]))
        records = load_collection(self.watches_dir)
        [target] = records
        toml_path = target.path / "watch.toml"
        mtime_before = toml_path.stat().st_mtime_ns

        assign_worn(self.backups_dir, records, [date(2026, 6, 1)], target)

        self.assertEqual(toml_path.stat().st_mtime_ns, mtime_before)

    def test_worn_dates_are_written_as_native_toml_dates_not_strings(self) -> None:
        """SPEC.md §3: dates use TOML's native date type, not strings. The
        calendar is the first thing writing worn dates in volume."""
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        records = load_collection(self.watches_dir)
        [target] = records

        assign_worn(self.backups_dir, records, [date(2026, 6, 1)], target)

        doc = tomlkit.parse((target.path / "watch.toml").read_text(encoding="utf-8"))
        self.assertIsInstance(doc["worn"][0], date)

    def test_backup_is_skipped_for_a_wear_only_save(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", worn=[date(2026, 6, 1)]))
        records = load_collection(self.watches_dir)
        [target] = records

        assign_worn(self.backups_dir, records, [date(2026, 6, 2)], target)

        self.assertFalse(self.backups_dir.exists() and any(self.backups_dir.glob("*.toml")))


class ClearWornTests(WearTestCase):
    def test_clearing_an_assigned_date_empties_it(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", worn=[date(2026, 6, 1)]))
        records = load_collection(self.watches_dir)

        clear_worn(self.backups_dir, records, [date(2026, 6, 1)])

        [reloaded] = load_collection(self.watches_dir)
        self.assertEqual(reloaded.watch.worn, [])

    def test_clearing_an_unassigned_date_is_a_no_op(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        records = load_collection(self.watches_dir)

        result = clear_worn(self.backups_dir, records, [date(2026, 6, 1)])

        self.assertEqual(result, records)

    def test_clearing_a_range_spanning_two_owners_touches_both(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", worn=[date(2026, 6, 1)]))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Omega", model="Speedmaster", worn=[date(2026, 6, 2)]))
        records = load_collection(self.watches_dir)

        clear_worn(self.backups_dir, records, [date(2026, 6, 1), date(2026, 6, 2)])

        reloaded = {r.watch.brand: r.watch.worn for r in load_collection(self.watches_dir)}
        self.assertEqual(reloaded["Seiko"], [])
        self.assertEqual(reloaded["Omega"], [])


class MarkWornTodayTests(WearTestCase):
    def test_marks_today_for_the_target_watch(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        records = load_collection(self.watches_dir)
        [target] = records

        mark_worn_today(self.backups_dir, records, target, today=date(2026, 6, 1))

        [reloaded] = load_collection(self.watches_dir)
        self.assertEqual(reloaded.watch.worn, [date(2026, 6, 1)])

    def test_pressing_it_twice_in_a_day_is_a_no_op(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        records = load_collection(self.watches_dir)
        [target] = records

        once = mark_worn_today(self.backups_dir, records, target, today=date(2026, 6, 1))
        twice = mark_worn_today(self.backups_dir, once, once[0], today=date(2026, 6, 1))

        self.assertEqual(twice[0].watch.worn, [date(2026, 6, 1)])

    def test_steals_today_from_whichever_watch_currently_owns_it(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", worn=[date(2026, 6, 1)]))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Omega", model="Speedmaster"))
        records = load_collection(self.watches_dir)
        omega = next(r for r in records if r.watch.brand == "Omega")

        mark_worn_today(self.backups_dir, records, omega, today=date(2026, 6, 1))

        reloaded = {r.watch.brand: r.watch.worn for r in load_collection(self.watches_dir)}
        self.assertEqual(reloaded["Seiko"], [])
        self.assertEqual(reloaded["Omega"], [date(2026, 6, 1)])


if __name__ == "__main__":
    unittest.main()
