import calendar as cal
from dataclasses import dataclass
from datetime import date, timedelta

from saat.selection import week_dates


@dataclass(frozen=True)
class GridDay:
    day: date
    in_month: bool


def month_grid_days(year: int, month: int) -> list[GridDay]:
    """One row per week, Monday first (SPEC.md §5.5), padded with the
    adjacent months' overflow days so every week is a full row of seven.
    Shared by the month view and the year view."""
    first_weekday, days_in_month = cal.monthrange(year, month)
    first_of_month = date(year, month, 1)

    leading = [first_of_month - timedelta(days=first_weekday - i) for i in range(first_weekday)]
    current = [date(year, month, d) for d in range(1, days_in_month + 1)]

    total = len(leading) + len(current)
    trailing_count = (7 - total % 7) % 7
    last_day = current[-1]
    trailing = [last_day + timedelta(days=i + 1) for i in range(trailing_count)]

    return (
        [GridDay(d, in_month=False) for d in leading]
        + [GridDay(d, in_month=True) for d in current]
        + [GridDay(d, in_month=False) for d in trailing]
    )


def week_grid_days(anchor: date) -> list[GridDay]:
    """Seven days, Monday..Sunday of the week containing `anchor` (SPEC.md
    §5.5: weeks start Monday) — one row for the calendar's Week mode
    (milestone 20). Every entry is in_month=True: unlike a month grid, a
    week has no adjacent-period overflow to pad or dim, so all seven days
    are equally "real" and interactive."""
    return [GridDay(d, in_month=True) for d in week_dates(anchor)]
