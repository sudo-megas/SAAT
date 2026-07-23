from datetime import date, timedelta

from saat.models import Watch
from saat.ui.formatting import fmt_date

DUE_SOON_DAYS = 90


def next_service_due(watch: Watch) -> date | None:
    """SPEC.md §4: the most recent `log` entry of kind Service, plus
    `service_interval_years` — not stored, not derived from acquisition date.
    None whenever either piece is missing: no Service entry means there's
    nothing to project from, and a blank interval means the owner isn't
    tracking this watch's service schedule at all."""
    interval = watch.maintenance.service_interval_years
    if interval is None:
        return None
    service_dates = [e.date for e in watch.log if e.kind == "Service" and e.date is not None]
    if not service_dates:
        return None

    baseline = max(service_dates)
    whole_years, fraction = divmod(interval, 1)
    try:
        due = baseline.replace(year=baseline.year + int(whole_years))
    except ValueError:
        due = baseline.replace(year=baseline.year + int(whole_years), day=28)  # baseline was Feb 29, target year isn't a leap year
    if fraction:
        due += timedelta(days=round(fraction * 365.25))
    return due


def is_maintenance_due(watch: Watch, today: date | None = None) -> bool:
    """Overdue, or due within DUE_SOON_DAYS. Silent (False) when there's no
    baseline to project from — most watches will never have this filled in
    and the UI must not nag. See SPEC.md §4."""
    due = next_service_due(watch)
    if due is None:
        return False
    today = today if today is not None else date.today()
    return due <= today + timedelta(days=DUE_SOON_DAYS)


def maintenance_due_text(watch: Watch, today: date | None = None) -> str | None:
    """None when nothing is due — the detail page's line is silent then, not
    rendered as an empty banner."""
    due = next_service_due(watch)
    if due is None:
        return None
    today = today if today is not None else date.today()
    if due < today:
        return f"Service overdue — was due {fmt_date(due)}"
    if due <= today + timedelta(days=DUE_SOON_DAYS):
        return f"Service due {fmt_date(due)}"
    return None
