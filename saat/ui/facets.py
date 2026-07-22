from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from saat.models import Watch

NOT_WORN_DAYS_THRESHOLD = 90


@dataclass(frozen=True)
class Facet:
    key: str
    label: str
    extract: Callable[[Watch], list[str]]
    sort_key: Callable[[str], object] = str.casefold


def _lug_width_values(watch: Watch) -> list[str]:
    return [f"{watch.case.lug_width_mm} mm"] if watch.case.lug_width_mm is not None else []


def _single(value: str | None) -> list[str]:
    return [value] if value else []


# SPEC.md §5.1 — the sidebar's multi-select facets, in the order listed there.
VALUE_FACETS: list[Facet] = [
    Facet("status", "Status", lambda w: _single(w.status)),
    Facet("style", "Style", lambda w: _single(w.style)),
    Facet("group", "Group", lambda w: _single(w.group)),
    Facet("movement_kind", "Movement Kind", lambda w: _single(w.movement.kind)),
    Facet("case_material", "Case Material", lambda w: _single(w.case.material)),
    Facet("lug_width", "Lug Width", _lug_width_values, sort_key=lambda v: int(v.split()[0])),
    Facet("tags", "Tags", lambda w: list(w.tags)),
]

VALUE_FACETS_BY_KEY: dict[str, Facet] = {f.key: f for f in VALUE_FACETS}


def days_since_worn(watch: Watch, today: date | None = None) -> int | None:
    """None means never worn — distinct from 0 (worn today). See SPEC.md §4."""
    if not watch.worn:
        return None
    reference = today if today is not None else date.today()
    return (reference - max(watch.worn)).days


def is_not_worn_90d(watch: Watch, today: date | None = None) -> bool:
    """SPEC.md §4: worn's derived 'Not worn in 90 days' filter facet. A watch
    that has never been worn qualifies too — it is, if anything, the most
    extreme case of not having been worn recently."""
    days = days_since_worn(watch, today)
    return days is None or days >= NOT_WORN_DAYS_THRESHOLD
