from dataclasses import dataclass

from saat.models import Strap
from saat.storage import WatchRecord


@dataclass(frozen=True)
class CompatibleStrap:
    record: WatchRecord
    strap: Strap


def _effective_width(strap: Strap, owner: WatchRecord) -> int | None:
    """SPEC.md §4: a strap's width_mm 'defaults to case.lug_width_mm' — a
    strap with no width of its own matches on its own watch's lug width."""
    return strap.width_mm if strap.width_mm is not None else owner.watch.case.lug_width_mm


def compatible_straps(target: WatchRecord, all_records: list[WatchRecord]) -> list[CompatibleStrap]:
    """SPEC.md §5.9: straps belonging to *other* watches whose (effective)
    width matches this watch's case.lug_width_mm. Silent — [] — when this
    watch has no lug width to match against; there's nothing to compare."""
    if target.watch is None or target.watch.case.lug_width_mm is None:
        return []
    target_width = target.watch.case.lug_width_mm

    matches = []
    for record in all_records:
        if record.slug == target.slug or record.watch is None:
            continue
        for strap in record.watch.straps:
            if _effective_width(strap, record) == target_width:
                matches.append(CompatibleStrap(record=record, strap=strap))
    return matches
