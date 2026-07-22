import unittest
from datetime import date

from saat.models import Watch
from saat.ui.wear_stats import days_since_worn, last_worn, longest_streak, times_worn_this_year


def _watch(worn: list[date]) -> Watch:
    return Watch(brand="Seiko", model="SARB033", worn=worn)


class LastWornTests(unittest.TestCase):
    def test_never_worn_is_none(self) -> None:
        self.assertIsNone(last_worn(_watch([])))

    def test_returns_the_most_recent_date(self) -> None:
        watch = _watch([date(2026, 1, 1), date(2026, 6, 1), date(2026, 3, 1)])
        self.assertEqual(last_worn(watch), date(2026, 6, 1))


class DaysSinceWornTests(unittest.TestCase):
    def test_never_worn_is_none(self) -> None:
        self.assertIsNone(days_since_worn(_watch([])))

    def test_counts_from_the_most_recent_entry(self) -> None:
        watch = _watch([date(2026, 1, 1), date(2026, 6, 1)])
        self.assertEqual(days_since_worn(watch, today=date(2026, 6, 11)), 10)


class TimesWornThisYearTests(unittest.TestCase):
    def test_counts_only_entries_in_the_reference_year(self) -> None:
        watch = _watch([date(2025, 12, 31), date(2026, 1, 1), date(2026, 6, 1)])
        self.assertEqual(times_worn_this_year(watch, today=date(2026, 7, 1)), 2)

    def test_zero_for_a_never_worn_watch(self) -> None:
        self.assertEqual(times_worn_this_year(_watch([]), today=date(2026, 7, 1)), 0)


class LongestStreakTests(unittest.TestCase):
    def test_never_worn_is_zero(self) -> None:
        self.assertEqual(longest_streak(_watch([])), 0)

    def test_single_date_is_a_streak_of_one(self) -> None:
        self.assertEqual(longest_streak(_watch([date(2026, 1, 1)])), 1)

    def test_consecutive_days_form_a_streak(self) -> None:
        watch = _watch([date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)])
        self.assertEqual(longest_streak(watch), 3)

    def test_a_gap_breaks_the_streak(self) -> None:
        watch = _watch([date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 10)])
        self.assertEqual(longest_streak(watch), 2)

    def test_returns_the_longest_of_several_streaks(self) -> None:
        watch = _watch([
            date(2026, 1, 1), date(2026, 1, 2),
            date(2026, 2, 1), date(2026, 2, 2), date(2026, 2, 3), date(2026, 2, 4),
            date(2026, 3, 1),
        ])
        self.assertEqual(longest_streak(watch), 4)

    def test_out_of_order_and_duplicate_dates_are_handled(self) -> None:
        watch = _watch([date(2026, 1, 3), date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 2)])
        self.assertEqual(longest_streak(watch), 3)


if __name__ == "__main__":
    unittest.main()
