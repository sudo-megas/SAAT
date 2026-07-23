import calendar as cal
from dataclasses import dataclass
from datetime import date, timedelta

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


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
