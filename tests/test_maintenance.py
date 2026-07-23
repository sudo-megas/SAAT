import unittest
from datetime import date, timedelta

from saat.models import LogEntry, Maintenance, Watch
from saat.ui.maintenance import is_maintenance_due, maintenance_due_text, next_service_due

TODAY = date(2026, 7, 23)


def _watch(interval_years: float | None, log: list[LogEntry] | None = None) -> Watch:
    return Watch(
        brand="Seiko", model="SARB033",
        maintenance=Maintenance(service_interval_years=interval_years),
        log=log or [],
    )


class NextServiceDueTests(unittest.TestCase):
    def test_no_interval_is_none(self) -> None:
        watch = _watch(None, [LogEntry(date=date(2020, 1, 1), kind="Service")])
        self.assertIsNone(next_service_due(watch))

    def test_interval_but_no_log_entries_is_none(self) -> None:
        watch = _watch(5)
        self.assertIsNone(next_service_due(watch))

    def test_log_entries_of_other_kinds_do_not_count_as_a_baseline(self) -> None:
        watch = _watch(5, [LogEntry(date=date(2020, 1, 1), kind="Battery"), LogEntry(date=date(2021, 1, 1), kind="Note")])
        self.assertIsNone(next_service_due(watch))

    def test_uses_the_most_recent_service_entry(self) -> None:
        watch = _watch(5, [
            LogEntry(date=date(2018, 1, 1), kind="Service"),
            LogEntry(date=date(2020, 6, 15), kind="Service"),
            LogEntry(date=date(2019, 1, 1), kind="Service"),
        ])
        due = next_service_due(watch)
        self.assertEqual(due.year, 2025)
        self.assertEqual(due.month, 6)

    def test_non_service_entries_after_the_last_service_are_ignored(self) -> None:
        watch = _watch(5, [
            LogEntry(date=date(2020, 1, 1), kind="Service"),
            LogEntry(date=date(2024, 1, 1), kind="Battery"),
        ])
        due = next_service_due(watch)
        self.assertEqual(due.year, 2025)

    def test_whole_year_interval_is_calendar_exact_not_a_365_25_day_approximation(self) -> None:
        """A 1-year interval from a leap-year baseline must land on the same
        calendar date next year — not a day short from averaging in leap days."""
        watch = _watch(1, [LogEntry(date=date(2020, 1, 1), kind="Service")])
        self.assertEqual(next_service_due(watch), date(2021, 1, 1))

    def test_fractional_year_interval_adds_approximate_days_on_top_of_whole_years(self) -> None:
        watch = _watch(1.5, [LogEntry(date=date(2020, 1, 1), kind="Service")])
        due = next_service_due(watch)
        self.assertEqual(due.year, 2021)
        self.assertTrue(date(2021, 6, 1) <= due <= date(2021, 7, 15))

    def test_leap_day_baseline_falls_back_to_february_28_in_a_non_leap_target_year(self) -> None:
        watch = _watch(1, [LogEntry(date=date(2020, 2, 29), kind="Service")])
        self.assertEqual(next_service_due(watch), date(2021, 2, 28))


class IsMaintenanceDueTests(unittest.TestCase):
    def test_no_baseline_is_not_due(self) -> None:
        watch = _watch(5)
        self.assertFalse(is_maintenance_due(watch, TODAY))

    def test_far_in_the_future_is_not_due(self) -> None:
        watch = _watch(5, [LogEntry(date=TODAY, kind="Service")])  # due in ~5 years
        self.assertFalse(is_maintenance_due(watch, TODAY))

    def test_overdue_is_due(self) -> None:
        watch = _watch(1, [LogEntry(date=date(2020, 1, 1), kind="Service")])  # due 2021
        self.assertTrue(is_maintenance_due(watch, TODAY))

    def test_due_today_counts(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033", maintenance=Maintenance(service_interval_years=1),
                       log=[LogEntry(date=date(2025, 7, 23), kind="Service")])
        self.assertTrue(is_maintenance_due(watch, TODAY))

    def test_within_90_days_is_due(self) -> None:
        # interval chosen so the due date lands 30 days after TODAY
        watch = Watch(brand="Seiko", model="SARB033", maintenance=Maintenance(service_interval_years=1),
                       log=[LogEntry(date=date(2025, 6, 23), kind="Service")])
        self.assertTrue(is_maintenance_due(watch, TODAY))

    def test_exactly_90_days_out_is_due(self) -> None:
        due_in_90 = TODAY + timedelta(days=90)
        # back-solve a service date one year before that due date
        service_date = due_in_90.replace(year=due_in_90.year - 1)
        watch = Watch(brand="Seiko", model="SARB033", maintenance=Maintenance(service_interval_years=1),
                       log=[LogEntry(date=service_date, kind="Service")])
        self.assertTrue(is_maintenance_due(watch, TODAY))

    def test_91_days_out_is_not_due(self) -> None:
        due_in_91 = TODAY + timedelta(days=91)
        service_date = due_in_91.replace(year=due_in_91.year - 1)
        watch = Watch(brand="Seiko", model="SARB033", maintenance=Maintenance(service_interval_years=1),
                       log=[LogEntry(date=service_date, kind="Service")])
        self.assertFalse(is_maintenance_due(watch, TODAY))


class MaintenanceDueTextTests(unittest.TestCase):
    def test_none_when_nothing_is_due(self) -> None:
        watch = _watch(5)
        self.assertIsNone(maintenance_due_text(watch, TODAY))

    def test_none_when_due_date_is_far_in_the_future(self) -> None:
        watch = _watch(5, [LogEntry(date=TODAY, kind="Service")])
        self.assertIsNone(maintenance_due_text(watch, TODAY))

    def test_overdue_text_mentions_overdue_and_the_original_due_date(self) -> None:
        watch = _watch(1, [LogEntry(date=date(2020, 1, 1), kind="Service")])
        text = maintenance_due_text(watch, TODAY)
        self.assertIn("overdue", text.lower())
        self.assertIn("01.01.2021", text)

    def test_due_today_reads_as_due_not_overdue(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033", maintenance=Maintenance(service_interval_years=1),
                       log=[LogEntry(date=date(2025, 7, 23), kind="Service")])
        text = maintenance_due_text(watch, TODAY)
        self.assertNotIn("overdue", text.lower())
        self.assertIn("due", text.lower())


if __name__ == "__main__":
    unittest.main()
