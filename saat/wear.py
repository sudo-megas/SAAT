import calendar as cal
import dataclasses
from datetime import date, timedelta
from pathlib import Path

from saat.storage import WatchRecord, save_watch


def build_worn_index(records: list[WatchRecord]) -> dict[date, WatchRecord]:
    """date -> the WatchRecord assigned that date. SPEC.md §5.5: built in
    memory at load, never centralised to a separate store — wear history
    lives in each watch's own `worn` list, nowhere else. SPEC.md §5.12:
    non-Owned watches (Wishlist, Incoming, Sold, Gifted) never wear
    anything, so they're excluded here too."""
    index: dict[date, WatchRecord] = {}
    for record in records:
        if record.watch is None or record.watch.status != "Owned":
            continue
        for day in record.watch.worn:
            index[day] = record
    return index


def _strip_dates(
    backups_dir: Path, records: list[WatchRecord], dates: set[date], exclude_slug: str | None
) -> dict[str, WatchRecord]:
    """Removes `dates` from every watch that owns any of them, except
    `exclude_slug` (the assignment target, whose own dates are handled
    separately). Returns {slug: saved_record} for only the watches touched."""
    updated: dict[str, WatchRecord] = {}
    for record in records:
        if record.watch is None or record.slug == exclude_slug:
            continue
        overlap = dates & set(record.watch.worn)
        if not overlap:
            continue
        new_worn = sorted(d for d in record.watch.worn if d not in overlap)
        updated[record.slug] = save_watch(
            backups_dir,
            dataclasses.replace(record, watch=dataclasses.replace(record.watch, worn=new_worn)),
            backup=False,
        )
    return updated


def assign_worn(
    backups_dir: Path, records: list[WatchRecord], dates: list[date], target: WatchRecord
) -> list[WatchRecord]:
    """Assigns every date in `dates` to `target`, taking each date away from
    whichever other watch currently owns it — SPEC.md §5.5's one-watch-per-
    day rule, enforced silently, no prompt. A date already assigned to
    `target` is left as-is, so calling this twice for the same day is a
    no-op on disk (see mark_worn_today). Returns a new records list; only
    the records actually touched are replaced."""
    assert target.watch is not None
    wanted = set(dates)
    updated = _strip_dates(backups_dir, records, wanted, exclude_slug=target.slug)

    new_target_worn = sorted(set(target.watch.worn) | wanted)
    if new_target_worn != sorted(target.watch.worn):
        updated[target.slug] = save_watch(
            backups_dir,
            dataclasses.replace(target, watch=dataclasses.replace(target.watch, worn=new_target_worn)),
            backup=False,
        )

    return [updated.get(r.slug, r) for r in records]


def clear_worn(backups_dir: Path, records: list[WatchRecord], dates: list[date]) -> list[WatchRecord]:
    """Removes every date in `dates` from whichever watch(es) currently own
    them — a drag-selected range can span more than one owner, so this may
    touch more than one watch at once."""
    updated = _strip_dates(backups_dir, records, set(dates), exclude_slug=None)
    return [updated.get(r.slug, r) for r in records]


def mark_worn_today(
    backups_dir: Path, records: list[WatchRecord], target: WatchRecord, today: date | None = None
) -> list[WatchRecord]:
    """"Wore this today" — SPEC.md §5.6: one click, no dialog, and pressing
    it twice in a day is a no-op. Still enforces one-watch-per-day, so it
    silently takes today away from whichever other watch (if any) owns it."""
    return assign_worn(backups_dir, records, [today if today is not None else date.today()], target)


# --- Milestone 13: calendar Stats mode — period-scoped derivations --------
#
# Everything below is pure (records + date bounds in, data out) and reads
# straight from each watch's own `worn` list — no central store, matching
# build_worn_index()'s own rule. "Period" here is always a FULL calendar
# unit (the whole month/year containing `today`, not just the elapsed part
# of it) so a fresh period's denominators are stable and consistent with
# year_view.py already rendering a whole year including unelapsed months.

PERIOD_MONTH = "month"
PERIOD_YEAR = "year"
PERIOD_ALL_TIME = "all_time"


def _valid_watches(records: list[WatchRecord]) -> list[WatchRecord]:
    """Owned only. SPEC.md §5.12: a watch that isn't Owned (Wishlist,
    Incoming, Sold, Gifted) is never worn, so it must not appear in
    rotation, not-worn, coverage, or the even-split denominator — this is
    the single choke point every Stats derivation below reads through."""
    return [r for r in records if r.watch is not None and r.watch.status == "Owned"]


def _name_key(record: WatchRecord) -> tuple[str, str]:
    return (record.watch.brand.casefold(), record.watch.model.casefold())


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = cal.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def period_bounds(period: str, records: list[WatchRecord], today: date | None = None) -> tuple[date, date] | None:
    """The span each Stats period covers. All time is the one period whose
    span depends on data: it runs from the earliest date any watch was ever
    worn through today, and is undefined (None) until something has been
    worn at least once. (`max(today, earliest)` guards the rare case where
    every recorded date is a pre-planned future one — SPEC.md §5.5 allows
    that — which would otherwise put the span's start after its end.)"""
    today = today if today is not None else date.today()
    if period == PERIOD_MONTH:
        return _month_bounds(today.year, today.month)
    if period == PERIOD_YEAR:
        return date(today.year, 1, 1), date(today.year, 12, 31)
    if period == PERIOD_ALL_TIME:
        all_dates = [d for r in _valid_watches(records) for d in r.watch.worn]
        if not all_dates:
            return None
        earliest = min(all_dates)
        return earliest, max(today, earliest)
    raise ValueError(f"unknown period: {period!r}")


def previous_period_bounds(period: str, today: date | None = None) -> tuple[date, date] | None:
    """The prior equivalent period, for period-over-period deltas. All time
    has no previous equivalent — there's nothing before "everything so far" —
    so callers must treat None as "omit the comparison", not "zero change"."""
    today = today if today is not None else date.today()
    if period == PERIOD_MONTH:
        last_day_of_previous_month = date(today.year, today.month, 1) - timedelta(days=1)
        return _month_bounds(last_day_of_previous_month.year, last_day_of_previous_month.month)
    if period == PERIOD_YEAR:
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
    if period == PERIOD_ALL_TIME:
        return None
    raise ValueError(f"unknown period: {period!r}")


def days_worn_by_watch(records: list[WatchRecord], start: date, end: date) -> dict[str, int]:
    """slug -> count of days in [start, end] present in that watch's own
    `worn` list."""
    return {r.slug: sum(1 for d in r.watch.worn if start <= d <= end) for r in _valid_watches(records)}


def _recorded_dates(records: list[WatchRecord], start: date, end: date) -> set[date]:
    """Distinct days in [start, end] with any watch assigned. A set, not a
    sum of per-watch counts: assign_worn enforces one watch per day, but a
    hand-edited watch.toml (SPEC.md §3 tolerates malformed/inconsistent
    files rather than crashing) could still double-claim a day, and this
    must agree with the Month footer's dict-based dedup
    (calendar_view.py's worn_index) rather than double-counting it."""
    return {d for r in _valid_watches(records) for d in r.watch.worn if start <= d <= end}


def rotation_ranking(records: list[WatchRecord], start: date, end: date) -> list[tuple[WatchRecord, int, float]]:
    """Watches actually in rotation this period — (record, days_worn, share)
    for every watch worn at least once, ranked by days_worn descending, ties
    broken alphabetically by brand/model. `share` is each watch's proportion
    of days *recorded* (sums to 100% down the list, barring the hand-edited
    double-claim case _recorded_dates guards against) — a different scale
    than the bar length and even-split tick, which plot against the
    period's length instead (see even_split_reference)."""
    counts = days_worn_by_watch(records, start, end)
    total_recorded = len(_recorded_dates(records, start, end))
    by_slug = {r.slug: r for r in _valid_watches(records)}
    ranked = sorted(
        ((by_slug[slug], count) for slug, count in counts.items() if count > 0),
        key=lambda pair: (-pair[1], _name_key(pair[0])),
    )
    return [(record, count, count / total_recorded) for record, count in ranked]


def even_split_reference(records: list[WatchRecord], start: date, end: date) -> float | None:
    """The even-split day count (period_days / watch_count) the Rotation
    bars tick against. Meaningless — and, landing at exactly the full bar
    length, actively misleading — with fewer than two watches, so this
    returns None rather than a divide-by-zero or a same-as-100% mark; the
    caller omits the tick entirely when this is None."""
    watch_count = len(_valid_watches(records))
    if watch_count < 2:
        return None
    period_days = (end - start).days + 1
    return period_days / watch_count


def not_worn_in_period(records: list[WatchRecord], start: date, end: date) -> list[WatchRecord]:
    """The exact complement of rotation_ranking's watches: zero days worn
    this period, name-sorted since there's no wear count left to rank by."""
    counts = days_worn_by_watch(records, start, end)
    return sorted((r for r in _valid_watches(records) if counts.get(r.slug, 0) == 0), key=_name_key)


def coverage(records: list[WatchRecord], start: date, end: date) -> tuple[int, int]:
    """(days_recorded, period_days). days_recorded counts distinct calendar
    days with any watch assigned — see _recorded_dates for why this is a
    dedup rather than a sum of per-watch counts."""
    period_days = (end - start).days + 1
    days_recorded = len(_recorded_dates(records, start, end))
    return days_recorded, period_days


def weekday_most_worn(records: list[WatchRecord], start: date, end: date) -> dict[int, WatchRecord | None]:
    """For each weekday (0=Monday..6=Sunday, matching SPEC.md §5.5's week-
    starts-Monday grid), the watch worn on that weekday most often within
    the period, or None if nothing was ever recorded on that weekday."""
    tallies: dict[int, dict[str, int]] = {i: {} for i in range(7)}
    by_slug = {r.slug: r for r in _valid_watches(records)}
    for r in _valid_watches(records):
        for d in r.watch.worn:
            if start <= d <= end:
                tallies[d.weekday()][r.slug] = tallies[d.weekday()].get(r.slug, 0) + 1

    result: dict[int, WatchRecord | None] = {}
    for weekday, counts in tallies.items():
        if not counts:
            result[weekday] = None
            continue
        best_slug = min(counts, key=lambda slug: (-counts[slug], _name_key(by_slug[slug])))
        result[weekday] = by_slug[best_slug]
    return result


def period_deltas(
    records: list[WatchRecord], start: date, end: date, previous_start: date, previous_end: date
) -> tuple[int, int]:
    """(days_recorded delta, distinct-watches-worn delta) against the
    previous equivalent period, signed so the caller can render explicit
    +/-. There is no previous equivalent for All time — see
    previous_period_bounds — so this is never called for it."""
    days_recorded, _ = coverage(records, start, end)
    previous_days_recorded, _ = coverage(records, previous_start, previous_end)

    current_counts = days_worn_by_watch(records, start, end)
    previous_counts = days_worn_by_watch(records, previous_start, previous_end)
    distinct_current = sum(1 for count in current_counts.values() if count > 0)
    distinct_previous = sum(1 for count in previous_counts.values() if count > 0)

    return days_recorded - previous_days_recorded, distinct_current - distinct_previous


def longest_run_in_period(records: list[WatchRecord], start: date, end: date) -> tuple[int, WatchRecord | None]:
    """Longest run of consecutive days *within [start, end]* assigned to the
    same watch — a real streak that starts before `start` or continues past
    `end` only counts its in-period portion. This is a period-scoped,
    cross-collection figure, distinct from a single watch's all-time
    longest_streak() in wear_stats.py."""
    owner_by_day: dict[date, str] = {}
    for r in _valid_watches(records):
        for d in r.watch.worn:
            if start <= d <= end:
                owner_by_day[d] = r.slug
    by_slug = {r.slug: r for r in _valid_watches(records)}

    best_len, best_slug = 0, None
    current_len, current_slug = 0, None
    day = start
    while day <= end:
        owner = owner_by_day.get(day)
        if owner is not None and owner == current_slug:
            current_len += 1
        elif owner is not None:
            current_slug, current_len = owner, 1
        else:
            current_slug, current_len = None, 0
        if current_len > best_len:
            best_len, best_slug = current_len, current_slug
        day += timedelta(days=1)

    return best_len, (by_slug[best_slug] if best_slug is not None else None)


def longest_gap_in_period(records: list[WatchRecord], start: date, end: date) -> int:
    """Longest run of consecutive days within [start, end] with nothing
    recorded at all, regardless of watch."""
    recorded_days = {d for r in _valid_watches(records) for d in r.watch.worn if start <= d <= end}

    best_len = current_len = 0
    day = start
    while day <= end:
        if day in recorded_days:
            current_len = 0
        else:
            current_len += 1
            best_len = max(best_len, current_len)
        day += timedelta(days=1)

    return best_len


@dataclasses.dataclass(frozen=True)
class PeriodStats:
    """Everything Stats mode needs for one period, bundled behind a single
    call — see compute_period_stats. `start`/`end`/`period_days` are the
    zeroed-out shape (None/None/0) only for All time with no wear data
    anywhere; every other case always has real bounds, even with zero
    watches, since This month/This year need no data to be defined."""

    period: str
    start: date | None
    end: date | None
    period_days: int
    watch_count: int
    days_recorded: int
    rotation: list[tuple[WatchRecord, int, float]]
    even_split: float | None
    not_worn: list[WatchRecord]
    weekday_most_worn: dict[int, WatchRecord | None]
    deltas: tuple[int, int] | None
    longest_run: tuple[int, WatchRecord | None]
    longest_gap: int


def compute_period_stats(records: list[WatchRecord], period: str, today: date | None = None) -> PeriodStats:
    """Bundles every Stats-mode derivation behind one call, the same shape
    as collection_summary.compute_collection_summary. Always returns a real
    (if mostly-zeroed) object, never None, so the widget's only special case
    is `watch_count == 0` — every other section governs its own visibility
    from its own (possibly empty/zero) field."""
    today = today if today is not None else date.today()
    watch_count = len(_valid_watches(records))
    bounds = period_bounds(period, records, today)

    if bounds is None:
        # All time, nothing ever worn: every valid watch is trivially "not
        # worn" regardless of date range, and every other derivation is
        # undefined without a span to measure against.
        return PeriodStats(
            period=period,
            start=None,
            end=None,
            period_days=0,
            watch_count=watch_count,
            days_recorded=0,
            rotation=[],
            even_split=None,
            not_worn=sorted(_valid_watches(records), key=_name_key),
            weekday_most_worn={i: None for i in range(7)},
            deltas=None,
            longest_run=(0, None),
            longest_gap=0,
        )

    start, end = bounds
    days_recorded, period_days = coverage(records, start, end)
    previous_bounds = previous_period_bounds(period, today)
    deltas = period_deltas(records, start, end, *previous_bounds) if previous_bounds is not None else None

    return PeriodStats(
        period=period,
        start=start,
        end=end,
        period_days=period_days,
        watch_count=watch_count,
        days_recorded=days_recorded,
        rotation=rotation_ranking(records, start, end),
        even_split=even_split_reference(records, start, end),
        not_worn=not_worn_in_period(records, start, end),
        weekday_most_worn=weekday_most_worn(records, start, end),
        deltas=deltas,
        longest_run=longest_run_in_period(records, start, end),
        longest_gap=longest_gap_in_period(records, start, end),
    )
