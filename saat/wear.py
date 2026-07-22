import dataclasses
from datetime import date
from pathlib import Path

from saat.storage import WatchRecord, save_watch


def build_worn_index(records: list[WatchRecord]) -> dict[date, WatchRecord]:
    """date -> the WatchRecord assigned that date. SPEC.md §5.5: built in
    memory at load, never centralised to a separate store — wear history
    lives in each watch's own `worn` list, nowhere else."""
    index: dict[date, WatchRecord] = {}
    for record in records:
        if record.watch is None:
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
