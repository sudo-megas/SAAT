import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

import tomlkit

from saat.models import Watch
from saat.storage import WatchRecord, create_watch, load_collection
from saat.wear import (
    PERIOD_ALL_TIME,
    PERIOD_MONTH,
    PERIOD_YEAR,
    assign_worn,
    build_worn_index,
    clear_worn,
    compute_period_stats,
    coverage,
    days_worn_by_watch,
    even_split_reference,
    longest_gap_in_period,
    longest_run_in_period,
    mark_worn_today,
    not_worn_in_period,
    period_bounds,
    period_deltas,
    previous_period_bounds,
    rotation_ranking,
    weekday_most_worn,
)


def _record(
    slug: str, brand: str, model: str, worn: list[date] | None = None, status: str = "Owned"
) -> WatchRecord:
    return WatchRecord(
        slug=slug, path=Path(f"/nonexistent/{slug}"), watch=Watch(brand=brand, model=model, worn=worn or [], status=status)
    )


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

    def test_a_non_owned_watch_is_excluded_from_the_index(self) -> None:
        """SPEC.md §5.12: a Wishlist/Incoming/Sold/Gifted watch never wears
        anything, even if its worn list carries stray dates (e.g. left over
        from a status change)."""
        create_watch(
            self.watches_dir, self.backups_dir,
            Watch(brand="Seiko", model="SARB033", status="Wishlist", worn=[date(2026, 1, 1)]),
        )
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


# --- Milestone 13: calendar Stats mode period-scoped derivations ----------
# These are pure (no disk I/O), so unlike the classes above they don't need
# WearTestCase's temp-directory setup — records are built directly with
# _record(), matching test_collection_summary.py's convention.


class PeriodBoundsTests(unittest.TestCase):
    def test_this_month_spans_the_full_calendar_month_not_elapsed_to_date(self) -> None:
        self.assertEqual(period_bounds(PERIOD_MONTH, [], today=date(2026, 2, 5)), (date(2026, 2, 1), date(2026, 2, 28)))

    def test_this_year_spans_the_full_calendar_year(self) -> None:
        self.assertEqual(period_bounds(PERIOD_YEAR, [], today=date(2026, 3, 1)), (date(2026, 1, 1), date(2026, 12, 31)))

    def test_all_time_spans_from_the_earliest_worn_date_to_today(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2024, 5, 1), date(2025, 1, 1)])
        self.assertEqual(
            period_bounds(PERIOD_ALL_TIME, [record], today=date(2026, 6, 1)), (date(2024, 5, 1), date(2026, 6, 1))
        )

    def test_all_time_is_none_when_nothing_has_ever_been_worn(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033")
        self.assertIsNone(period_bounds(PERIOD_ALL_TIME, [record], today=date(2026, 6, 1)))

    def test_all_time_end_does_not_precede_start_when_every_date_is_a_future_plan(self) -> None:
        """SPEC.md §5.5 allows recording future days to plan ahead. If the
        only worn date ever entered is in the future, All time must not
        produce a start-after-end span."""
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 8, 1)])
        self.assertEqual(
            period_bounds(PERIOD_ALL_TIME, [record], today=date(2026, 6, 1)), (date(2026, 8, 1), date(2026, 8, 1))
        )


class PreviousPeriodBoundsTests(unittest.TestCase):
    def test_previous_month_is_the_full_prior_calendar_month(self) -> None:
        self.assertEqual(previous_period_bounds(PERIOD_MONTH, today=date(2026, 3, 15)), (date(2026, 2, 1), date(2026, 2, 28)))

    def test_previous_month_from_january_wraps_to_december_of_the_prior_year(self) -> None:
        self.assertEqual(
            previous_period_bounds(PERIOD_MONTH, today=date(2026, 1, 15)), (date(2025, 12, 1), date(2025, 12, 31))
        )

    def test_previous_year_is_the_full_prior_calendar_year(self) -> None:
        self.assertEqual(previous_period_bounds(PERIOD_YEAR, today=date(2026, 6, 1)), (date(2025, 1, 1), date(2025, 12, 31)))

    def test_all_time_has_no_previous_equivalent(self) -> None:
        self.assertIsNone(previous_period_bounds(PERIOD_ALL_TIME, today=date(2026, 6, 1)))


class DaysWornByWatchTests(unittest.TestCase):
    def test_counts_only_days_within_the_range(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, 1), date(2026, 1, 15), date(2026, 2, 1)])
        self.assertEqual(days_worn_by_watch([record], date(2026, 1, 1), date(2026, 1, 31)), {"seiko-sarb033": 2})

    def test_a_watch_with_no_days_in_range_still_gets_a_zero_entry(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033")
        self.assertEqual(days_worn_by_watch([record], date(2026, 1, 1), date(2026, 1, 31)), {"seiko-sarb033": 0})

    def test_broken_records_are_excluded(self) -> None:
        broken = WatchRecord(slug="broken", path=Path("/nonexistent/broken"), watch=None, load_error="bad toml")
        self.assertEqual(days_worn_by_watch([broken], date(2026, 1, 1), date(2026, 1, 31)), {})


class RotationRankingTests(unittest.TestCase):
    def test_ranks_by_days_worn_descending(self) -> None:
        seiko = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, d) for d in range(1, 6)])
        omega = _record("omega-speedmaster", "Omega", "Speedmaster", worn=[date(2026, 1, 10)])
        ranking = rotation_ranking([seiko, omega], date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual([r.slug for r, _, _ in ranking], ["seiko-sarb033", "omega-speedmaster"])

    def test_zero_day_watches_are_excluded_not_ranked_at_zero(self) -> None:
        worn = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, 1)])
        idle = _record("omega-speedmaster", "Omega", "Speedmaster")
        ranking = rotation_ranking([worn, idle], date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual([r.slug for r, _, _ in ranking], ["seiko-sarb033"])

    def test_share_sums_to_one_and_reflects_proportion_of_days_recorded(self) -> None:
        a = _record("a", "Seiko", "A", worn=[date(2026, 1, d) for d in range(1, 4)])  # 3 days
        b = _record("b", "Omega", "B", worn=[date(2026, 1, d) for d in range(4, 6)])  # 2 days
        ranking = rotation_ranking([a, b], date(2026, 1, 1), date(2026, 1, 31))
        shares = [share for _, _, share in ranking]
        self.assertAlmostEqual(sum(shares), 1.0)
        self.assertAlmostEqual(shares[0], 3 / 5)

    def test_share_denominator_matches_coverages_dedup_on_a_double_claimed_day(self) -> None:
        """Same hand-edited-double-claim scenario as CoverageTests — share's
        denominator (days actually recorded) must agree with coverage()'s,
        not silently diverge because one sums and the other dedupes."""
        a = _record("a", "Seiko", "A", worn=[date(2026, 1, 1)])
        b = _record("b", "Omega", "B", worn=[date(2026, 1, 1), date(2026, 1, 2)])
        ranking = rotation_ranking([a, b], date(2026, 1, 1), date(2026, 1, 31))
        shares = {r.slug: share for r, _, share in ranking}
        self.assertAlmostEqual(shares["b"], 2 / 2)  # 2 of 2 distinct recorded days, not 2 of 3

    def test_ties_break_alphabetically_by_brand_then_model(self) -> None:
        zenith = _record("zenith-elprimero", "Zenith", "El Primero", worn=[date(2026, 1, 1)])
        alpina = _record("alpina-startimer", "Alpina", "Startimer", worn=[date(2026, 1, 2)])
        ranking = rotation_ranking([zenith, alpina], date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual([r.slug for r, _, _ in ranking], ["alpina-startimer", "zenith-elprimero"])

    def test_a_non_owned_watch_with_worn_dates_is_excluded(self) -> None:
        """SPEC.md §5.12. Defends against a hand-edited watch.toml where worn
        dates survive a status change to Wishlist/Incoming/Sold/Gifted."""
        wishlist = _record("wishlist-watch", "Seiko", "SARB033", worn=[date(2026, 1, 1)], status="Wishlist")
        ranking = rotation_ranking([wishlist], date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(ranking, [])


class EvenSplitReferenceTests(unittest.TestCase):
    def test_none_with_zero_watches(self) -> None:
        self.assertIsNone(even_split_reference([], date(2026, 1, 1), date(2026, 1, 31)))

    def test_none_with_a_single_watch(self) -> None:
        """SPEC.md: meaningless with one watch, must not render as a
        divide-by-zero or a full bar."""
        record = _record("seiko-sarb033", "Seiko", "SARB033")
        self.assertIsNone(even_split_reference([record], date(2026, 1, 1), date(2026, 1, 31)))

    def test_period_days_over_watch_count_for_two_or_more(self) -> None:
        a = _record("a", "Seiko", "A")
        b = _record("b", "Omega", "B")
        self.assertAlmostEqual(even_split_reference([a, b], date(2026, 1, 1), date(2026, 1, 31)), 31 / 2)

    def test_non_owned_watches_do_not_inflate_the_watch_count(self) -> None:
        """The live bug this milestone fixes: a Wishlist watch previously
        counted toward the denominator even though it can never be worn,
        skewing the even-split reference for the watches that actually are
        in rotation."""
        owned = _record("a", "Seiko", "A", status="Owned")
        wishlist = _record("b", "Omega", "B", status="Wishlist")
        # Only one Owned watch present -> meaningless, same as the
        # single-watch case above, not (2 watches -> 31/2).
        self.assertIsNone(even_split_reference([owned, wishlist], date(2026, 1, 1), date(2026, 1, 31)))


class NotWornInPeriodTests(unittest.TestCase):
    def test_lists_only_zero_day_watches_sorted_by_name(self) -> None:
        worn = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, 1)])
        zenith = _record("zenith-elprimero", "Zenith", "El Primero")
        alpina = _record("alpina-startimer", "Alpina", "Startimer")
        result = not_worn_in_period([worn, zenith, alpina], date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual([r.slug for r in result], ["alpina-startimer", "zenith-elprimero"])

    def test_empty_when_every_watch_was_worn(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, 1)])
        self.assertEqual(not_worn_in_period([record], date(2026, 1, 1), date(2026, 1, 31)), [])

    def test_is_the_exact_complement_of_rotation_ranking(self) -> None:
        worn = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, 1)])
        idle = _record("omega-speedmaster", "Omega", "Speedmaster")
        records = [worn, idle]
        start, end = date(2026, 1, 1), date(2026, 1, 31)
        ranked_slugs = {r.slug for r, _, _ in rotation_ranking(records, start, end)}
        not_worn_slugs = {r.slug for r in not_worn_in_period(records, start, end)}
        self.assertEqual(ranked_slugs | not_worn_slugs, {"seiko-sarb033", "omega-speedmaster"})
        self.assertEqual(ranked_slugs & not_worn_slugs, set())

    def test_a_non_owned_watch_is_excluded_entirely_not_listed_as_not_worn(self) -> None:
        """SPEC.md §5.12: excluded from wear tracking altogether, not just
        counted among the "not worn" watches."""
        wishlist = _record("wishlist-watch", "Seiko", "SARB033", status="Wishlist")
        self.assertEqual(not_worn_in_period([wishlist], date(2026, 1, 1), date(2026, 1, 31)), [])


class CoverageTests(unittest.TestCase):
    def test_days_recorded_over_period_days(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, 1), date(2026, 1, 2)])
        self.assertEqual(coverage([record], date(2026, 1, 1), date(2026, 1, 31)), (2, 31))

    def test_zero_recorded_with_no_wear_data(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033")
        self.assertEqual(coverage([record], date(2026, 1, 1), date(2026, 1, 31)), (0, 31))

    def test_sums_across_watches_without_double_counting(self) -> None:
        a = _record("a", "Seiko", "A", worn=[date(2026, 1, 1)])
        b = _record("b", "Omega", "B", worn=[date(2026, 1, 2)])
        days_recorded, _ = coverage([a, b], date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(days_recorded, 2)

    def test_a_hand_edited_day_claimed_by_two_watches_is_not_double_counted(self) -> None:
        """assign_worn enforces one watch per day, but a hand-edited
        watch.toml (SPEC.md §3 tolerates malformed/inconsistent files) could
        still double-claim a date. days_recorded must match the Month
        footer's dict-based worn_index, which only ever counts it once."""
        a = _record("a", "Seiko", "A", worn=[date(2026, 1, 1)])
        b = _record("b", "Omega", "B", worn=[date(2026, 1, 1)])
        days_recorded, _ = coverage([a, b], date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(days_recorded, 1)


class WeekdayMostWornTests(unittest.TestCase):
    """2026-01-05/12/19/26 are Mondays (weekday 0); 2026-01-04 is a Sunday
    (weekday 6) — verified against date.weekday(), not assumed."""

    def test_the_watch_worn_most_on_a_given_weekday_wins(self) -> None:
        seiko = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, 5), date(2026, 1, 12)])
        omega = _record("omega-speedmaster", "Omega", "Speedmaster", worn=[date(2026, 1, 19)])
        result = weekday_most_worn([seiko, omega], date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(result[0].slug, "seiko-sarb033")

    def test_a_weekday_with_no_data_is_none(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, 5)])
        result = weekday_most_worn([record], date(2026, 1, 1), date(2026, 1, 31))
        self.assertIsNone(result[6])

    def test_ties_break_alphabetically_by_brand_then_model(self) -> None:
        zenith = _record("zenith-elprimero", "Zenith", "El Primero", worn=[date(2026, 1, 5)])
        alpina = _record("alpina-startimer", "Alpina", "Startimer", worn=[date(2026, 1, 12)])
        result = weekday_most_worn([zenith, alpina], date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(result[0].slug, "alpina-startimer")


class PeriodDeltasTests(unittest.TestCase):
    def test_positive_days_delta_when_more_was_recorded_than_previously(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 2, 1), date(2026, 2, 2), date(2026, 1, 1)])
        days_delta, _ = period_deltas([record], date(2026, 2, 1), date(2026, 2, 28), date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(days_delta, 1)

    def test_negative_distinct_watch_delta_when_fewer_watches_were_worn(self) -> None:
        seiko = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, 1), date(2026, 2, 1)])
        omega = _record("omega-speedmaster", "Omega", "Speedmaster", worn=[date(2026, 1, 2)])
        _, watch_delta = period_deltas(
            [seiko, omega], date(2026, 2, 1), date(2026, 2, 28), date(2026, 1, 1), date(2026, 1, 31)
        )
        self.assertEqual(watch_delta, -1)


class LongestRunInPeriodTests(unittest.TestCase):
    def test_longest_consecutive_run_for_one_watch(self) -> None:
        record = _record(
            "seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 10)]
        )
        length, winner = longest_run_in_period([record], date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(length, 3)
        self.assertEqual(winner.slug, "seiko-sarb033")

    def test_a_run_is_bounded_at_the_period_edges(self) -> None:
        """A real streak that starts before `start` only counts its
        in-period portion."""
        record = _record(
            "seiko-sarb033", "Seiko", "SARB033",
            worn=[date(2025, 12, 30), date(2025, 12, 31), date(2026, 1, 1), date(2026, 1, 2)],
        )
        length, _ = longest_run_in_period([record], date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(length, 2)

    def test_a_run_does_not_cross_a_change_of_owner(self) -> None:
        seiko = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, 1), date(2026, 1, 2)])
        omega = _record("omega-speedmaster", "Omega", "Speedmaster", worn=[date(2026, 1, 3), date(2026, 1, 4)])
        length, _ = longest_run_in_period([seiko, omega], date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(length, 2)

    def test_zero_with_nothing_recorded(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033")
        self.assertEqual(longest_run_in_period([record], date(2026, 1, 1), date(2026, 1, 31)), (0, None))


class LongestGapInPeriodTests(unittest.TestCase):
    def test_longest_gap_between_recorded_days(self) -> None:
        # Bookended at both ends of the period, so the entire interior
        # (Jan 2-30, 29 days) is the one unambiguous gap — with only a
        # single unbookended date, an unrecorded tail running to the
        # period's end could dominate and obscure what's being measured.
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, 1), date(2026, 1, 31)])
        self.assertEqual(longest_gap_in_period([record], date(2026, 1, 1), date(2026, 1, 31)), 29)

    def test_zero_when_every_day_in_the_period_is_recorded(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)])
        self.assertEqual(longest_gap_in_period([record], date(2026, 1, 1), date(2026, 1, 3)), 0)

    def test_the_whole_period_is_one_gap_when_nothing_is_recorded(self) -> None:
        self.assertEqual(longest_gap_in_period([], date(2026, 1, 1), date(2026, 1, 31)), 31)


class ComputePeriodStatsTests(unittest.TestCase):
    def test_zero_valid_watches_produces_a_fully_zeroed_result_without_crashing(self) -> None:
        stats = compute_period_stats([], PERIOD_MONTH, today=date(2026, 1, 15))
        self.assertEqual(stats.watch_count, 0)
        self.assertEqual(stats.rotation, [])
        self.assertEqual(stats.not_worn, [])
        self.assertEqual(stats.period_days, 31)  # This month is well-defined even with no watches

    def test_watches_exist_but_nothing_worn_this_period(self) -> None:
        """Confirmed design: sections hide individually (Rotation empty)
        rather than the whole panel switching to an empty state — Not-worn
        still lists every watch and Coverage still reads a real 0%."""
        a = _record("a", "Seiko", "A")
        b = _record("b", "Omega", "B")
        stats = compute_period_stats([a, b], PERIOD_MONTH, today=date(2026, 1, 15))
        self.assertEqual(stats.rotation, [])
        self.assertEqual({r.slug for r in stats.not_worn}, {"a", "b"})
        self.assertEqual(stats.days_recorded, 0)
        self.assertIsNotNone(stats.deltas)

    def test_all_time_with_no_data_ever_recorded(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033")
        stats = compute_period_stats([record], PERIOD_ALL_TIME, today=date(2026, 1, 15))
        self.assertIsNone(stats.start)
        self.assertEqual([r.slug for r in stats.not_worn], ["seiko-sarb033"])
        self.assertIsNone(stats.deltas)

    def test_deltas_are_none_for_all_time_even_with_data(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, 1)])
        stats = compute_period_stats([record], PERIOD_ALL_TIME, today=date(2026, 1, 15))
        self.assertIsNone(stats.deltas)

    def test_deltas_are_present_for_month_and_year(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, 1)])
        for period in (PERIOD_MONTH, PERIOD_YEAR):
            with self.subTest(period=period):
                stats = compute_period_stats([record], period, today=date(2026, 1, 15))
                self.assertIsNotNone(stats.deltas)

    def test_non_owned_watches_are_excluded_from_watch_count(self) -> None:
        owned = _record("a", "Seiko", "A")
        wishlist = _record("b", "Omega", "B", status="Wishlist")
        stats = compute_period_stats([owned, wishlist], PERIOD_MONTH, today=date(2026, 1, 15))
        self.assertEqual(stats.watch_count, 1)


if __name__ == "__main__":
    unittest.main()
