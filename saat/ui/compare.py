from dataclasses import dataclass
from enum import Enum, auto

from saat.storage import WatchRecord
from saat.ui.columns import COLUMNS, GROUP_ORDER
from saat.ui.formatting import is_empty, is_numeric_value

MIN_COMPARE = 2
MAX_COMPARE = 4


class RowContrast(Enum):
    DIMMED = auto()   # every selected watch has a value, and they all agree
    DIFFERS = auto()  # some present some absent, or present-and-disagreeing


@dataclass(frozen=True)
class CompareRow:
    label: str
    values: list[str]  # one per record, in the same order as the records passed in
    contrast: RowContrast
    numeric: bool = False


@dataclass(frozen=True)
class CompareGroup:
    title: str
    rows: list[CompareRow]


def build_compare_groups(records: list[WatchRecord]) -> list[CompareGroup]:
    """Watches as columns, attributes as rows, grouped in the model's order —
    built directly on saat.ui.columns.COLUMNS/GROUP_ORDER so this isn't a
    second implementation of the table view's data access. SPEC.md §5.4.
    Rows where no selected watch has a value are dropped entirely; the
    caller decides how DIMMED vs DIFFERS rows are styled."""
    watches = [r.watch for r in records]
    groups = []
    for group_name in GROUP_ORDER:
        rows = []
        for column in COLUMNS:
            if column.group != group_name:
                continue
            raw_values = [column.value(w) for w in watches]
            if all(is_empty(v) for v in raw_values):
                continue
            texts = [column.text(w) for w in watches]
            contrast = RowContrast.DIMMED if _all_present_and_equal(raw_values) else RowContrast.DIFFERS
            numeric = any(is_numeric_value(v) for v in raw_values)
            rows.append(CompareRow(label=column.label, values=texts, contrast=contrast, numeric=numeric))
        if rows:
            groups.append(CompareGroup(title=group_name, rows=rows))
    return groups


def _all_present_and_equal(values: list) -> bool:
    if any(is_empty(v) for v in values):
        return False
    first = values[0]
    return all(v == first for v in values[1:])
