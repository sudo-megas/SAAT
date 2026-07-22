from dataclasses import dataclass, field
from datetime import date

from saat.models import Watch
from saat.ui.facets import VALUE_FACETS, is_not_worn_90d
from saat.ui.search import search_matches

NOT_WORN_FACET_KEY = "not_worn_90d"


@dataclass
class FilterState:
    active_values: dict[str, set[str]] = field(default_factory=dict)
    not_worn_only: bool = False
    query: str = ""

    def is_active(self) -> bool:
        return bool(self.query.strip()) or self.not_worn_only or any(self.active_values.values())


def passes(watch: Watch, state: FilterState, skip: str | None = None, today: date | None = None) -> bool:
    """Whether watch survives every active filter except `skip` — `skip` lets
    a facet's own live count reflect what selecting one more of its values
    would do, without that facet hiding its own other options down to zero
    the moment one value in it is checked. See SPEC.md §5.1 "multi-select"."""
    for facet in VALUE_FACETS:
        if facet.key == skip:
            continue
        selected = state.active_values.get(facet.key)
        if selected and not (set(facet.extract(watch)) & selected):
            return False

    if state.not_worn_only and skip != NOT_WORN_FACET_KEY and not is_not_worn_90d(watch, today):
        return False

    return search_matches(watch, state.query)
