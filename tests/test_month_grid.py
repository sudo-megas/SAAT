import unittest
from datetime import date, timedelta

from saat.ui.month_grid import month_grid_days


class MonthGridDaysTests(unittest.TestCase):
    def test_grid_is_a_whole_number_of_weeks(self) -> None:
        for year, month in [(2026, 7), (2026, 2), (2024, 2), (2026, 11)]:
            days = month_grid_days(year, month)
            self.assertEqual(len(days) % 7, 0)

    def test_every_day_of_the_month_is_present_and_marked_in_month(self) -> None:
        days = month_grid_days(2026, 7)
        in_month = [d.day for d in days if d.in_month]
        self.assertEqual(in_month, [date(2026, 7, n) for n in range(1, 32)])

    def test_padding_days_are_marked_out_of_month(self) -> None:
        days = month_grid_days(2026, 7)
        leading = [d for d in days if not d.in_month and d.day < date(2026, 7, 1)]
        trailing = [d for d in days if not d.in_month and d.day > date(2026, 7, 31)]
        self.assertEqual(len(leading) + len(trailing) + 31, len(days))

    def test_week_starts_on_monday(self) -> None:
        """SPEC.md §5.5: weeks starting Monday. The number of leading padding
        cells before day 1 must equal date.weekday() (0=Monday)."""
        for year, month in [(2026, 7), (2026, 3), (2026, 11)]:
            days = month_grid_days(year, month)
            leading_count = sum(1 for d in days if not d.in_month and d.day < date(year, month, 1))
            self.assertEqual(leading_count, date(year, month, 1).weekday())

    def test_grid_is_one_continuous_run_of_consecutive_dates(self) -> None:
        days = month_grid_days(2026, 7)
        for previous, current in zip(days, days[1:]):
            self.assertEqual(current.day - previous.day, timedelta(days=1))


if __name__ == "__main__":
    unittest.main()
