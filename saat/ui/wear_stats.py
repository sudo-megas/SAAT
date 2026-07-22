from datetime import date

from saat.models import Watch


def last_worn(watch: Watch) -> date | None:
    return max(watch.worn) if watch.worn else None


def days_since_worn(watch: Watch, today: date | None = None) -> int | None:
    """None means never worn — distinct from 0 (worn today). See SPEC.md §4."""
    if not watch.worn:
        return None
    reference = today if today is not None else date.today()
    return (reference - max(watch.worn)).days


def times_worn_this_year(watch: Watch, today: date | None = None) -> int:
    year = (today if today is not None else date.today()).year
    return sum(1 for d in watch.worn if d.year == year)


def longest_streak(watch: Watch) -> int:
    """Longest run of consecutive calendar days in `worn`."""
    if not watch.worn:
        return 0
    days = sorted(set(watch.worn))
    best = current = 1
    for previous, current_day in zip(days, days[1:]):
        if (current_day - previous).days == 1:
            current += 1
            best = max(best, current)
        else:
            current = 1
    return best
