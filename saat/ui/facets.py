from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from PySide6.QtCore import QT_TRANSLATE_NOOP

from saat.models import Watch
from saat.ui.wear_stats import days_since_worn

NOT_WORN_DAYS_THRESHOLD = 90


@dataclass(frozen=True)
class Facet:
    key: str
    label: str
    extract: Callable[[Watch], list[str]]
    sort_key: Callable[[str], object] = str.casefold
    # Milestone 21: whether this facet's *values* are enum* vocabulary
    # (already QT_TRANSLATE_NOOP-registered under "EnumChoices" via
    # watch_form.py's suggestion lists) and so eligible for
    # QCoreApplication.translate("EnumChoices", value) at display time in
    # sidebar.py. False for lug_width (a formatted number+unit, e.g.
    # "20 mm" -- not vocabulary) and tags (free-form user text).
    translate_values: bool = True


def _lug_width_values(watch: Watch) -> list[str]:
    return [f"{watch.case.lug_width_mm} mm"] if watch.case.lug_width_mm is not None else []


def _single(value: str | None) -> list[str]:
    return [value] if value else []


# SPEC.md §5.1 — the sidebar's multi-select facets, in the order listed
# there. QT_TRANSLATE_NOOP-marked (same reason as columns.py's Column.label:
# lupdate can't see a value reached via a dict/loop variable) so
# sidebar.py's _build_value_group can render the translated heading via
# QCoreApplication.translate("Facets", facet.label) while the field itself
# stays canonical English.
VALUE_FACETS: list[Facet] = [
    Facet("status", QT_TRANSLATE_NOOP("Facets", "Status"), lambda w: _single(w.status)),
    Facet("style", QT_TRANSLATE_NOOP("Facets", "Style"), lambda w: _single(w.style)),
    Facet("group", QT_TRANSLATE_NOOP("Facets", "Group"), lambda w: _single(w.group)),
    Facet("movement_kind", QT_TRANSLATE_NOOP("Facets", "Movement Kind"), lambda w: _single(w.movement.kind)),
    Facet("case_material", QT_TRANSLATE_NOOP("Facets", "Case Material"), lambda w: _single(w.case.material)),
    Facet(
        "lug_width", QT_TRANSLATE_NOOP("Facets", "Lug Width"), _lug_width_values,
        sort_key=lambda v: int(v.split()[0]), translate_values=False,
    ),
    Facet("tags", QT_TRANSLATE_NOOP("Facets", "Tags"), lambda w: list(w.tags), translate_values=False),
]

VALUE_FACETS_BY_KEY: dict[str, Facet] = {f.key: f for f in VALUE_FACETS}


def is_not_worn_90d(watch: Watch, today: date | None = None) -> bool:
    """SPEC.md §4: worn's derived 'Not worn in 90 days' filter facet. A watch
    that has never been worn qualifies too — it is, if anything, the most
    extreme case of not having been worn recently."""
    days = days_since_worn(watch, today)
    return days is None or days >= NOT_WORN_DAYS_THRESHOLD
