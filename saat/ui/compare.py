from dataclasses import dataclass
from enum import Enum, auto

from saat.models import Watch
from saat.storage import WatchRecord
from saat.ui.columns import COLUMNS, GROUP_ORDER, Column
from saat.ui.formatting import EM_DASH, is_empty, is_numeric_value

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


# --- Milestone 15a: case silhouette ----------------------------------------
#
# Pure logic only — no QPainter, no widgets, unit-tested with no event loop.
# saat.ui.case_silhouette turns this into pixels.

@dataclass(frozen=True)
class SilhouetteEntry:
    """One selected watch's case geometry, ready to draw at a shared scale.
    Only built for watches with a diameter — see build_silhouette_entries.
    lug_to_lug_mm/thickness_mm/lug_width_mm are optional per watch: present,
    that watch's lug blocks / side profile / lug-width-driven block width
    draw; absent, that part alone is skipped for that watch, same scale,
    no fabricated value."""

    record: WatchRecord
    diameter_mm: float
    lug_to_lug_mm: float | None
    thickness_mm: float | None
    lug_width_mm: float | None


def build_silhouette_entries(records: list[WatchRecord]) -> tuple[list[SilhouetteEntry], list[WatchRecord]]:
    """Splits the selection into (drawable, missing_case_data). SPEC.md
    §5.4: 'A watch missing diameter cannot be drawn. Omit it from the
    drawing and name it in the legend as having no case data.'
    case.diameter_mm is the one field a circle cannot be drawn without."""
    entries: list[SilhouetteEntry] = []
    missing: list[WatchRecord] = []
    for r in records:
        if r.watch is None or r.watch.case.diameter_mm is None:
            missing.append(r)
            continue
        c = r.watch.case
        entries.append(SilhouetteEntry(
            record=r,
            diameter_mm=c.diameter_mm,
            lug_to_lug_mm=c.lug_to_lug_mm,
            thickness_mm=c.thickness_mm,
            lug_width_mm=c.lug_width_mm,
        ))
    return entries, missing


def should_show_silhouette(records: list[WatchRecord]) -> bool:
    """SPEC.md §5.4: 'Hide the whole section when fewer than 2 selected
    watches have diameter data.'"""
    entries, _ = build_silhouette_entries(records)
    return len(entries) >= 2


def silhouette_profile_entries(entries: list[SilhouetteEntry]) -> list[SilhouetteEntry]:
    """The subset of already-drawable entries that also qualify for the
    side-profile strip, which additionally needs thickness_mm. A separate,
    usually-smaller drawable set than the top-down view's — a watch can
    have a diameter (drawn up top) without a recorded thickness (absent
    from the strip beneath)."""
    return [e for e in entries if e.thickness_mm is not None]


def _silhouette_extent_mm(entry: SilhouetteEntry) -> float:
    """The furthest point this watch actually draws to — lug-to-lug when
    known (lugs extend past the case), otherwise its diameter, since a
    watch without lug-to-lug draws no lug blocks at all."""
    return entry.lug_to_lug_mm if entry.lug_to_lug_mm is not None else entry.diameter_mm


def silhouette_scale(entries: list[SilhouetteEntry], available_width_px: float) -> float:
    """px-per-mm shared by the whole case silhouette — top view, side
    profile and scale bar alike — sized so the largest drawn extent (see
    _silhouette_extent_mm) fits available_width_px. 0.0 when there's
    nothing to scale against; callers should already have checked
    should_show_silhouette before drawing."""
    if available_width_px <= 0 or not entries:
        return 0.0
    max_extent = max(_silhouette_extent_mm(e) for e in entries)
    return available_width_px / max_extent if max_extent > 0 else 0.0


# --- Milestone 15b: accuracy ranges -----------------------------------------
#
# Pure logic only — no QPainter, no widgets, unit-tested with no event loop.
# saat.ui.accuracy_ranges turns this into pixels.

SEC_PER_MONTH_DIVISOR = 30  # SPEC.md §5.4: "converting sec/month by dividing by 30"


@dataclass(frozen=True)
class AccuracyEntry:
    """One selected watch's accuracy span, normalised to sec/day for the
    shared axis. original_min/original_max/original_unit are kept
    unconverted so the caller can label the watch with what was actually
    entered — SPEC.md §5.4: 'labelled with their ORIGINAL value and unit.'"""

    record: WatchRecord
    min_sec_per_day: float
    max_sec_per_day: float
    original_min: float
    original_max: float
    original_unit: str


def _normalise_to_sec_per_day(min_value: float, max_value: float, unit: str) -> tuple[float, float]:
    if unit == "sec/month":
        return min_value / SEC_PER_MONTH_DIVISOR, max_value / SEC_PER_MONTH_DIVISOR
    return min_value, max_value


def build_accuracy_entries(records: list[WatchRecord]) -> tuple[list[AccuracyEntry], list[WatchRecord]]:
    """Splits the selection into (drawable, missing_accuracy_data). Both
    accuracy_min and accuracy_max are required — a single endpoint isn't
    enough to draw a span — matching movement.accuracy_unit's own default
    of sec/day when unset (see columns.py's _get_accuracy)."""
    entries: list[AccuracyEntry] = []
    missing: list[WatchRecord] = []
    for r in records:
        m = r.watch.movement if r.watch is not None else None
        if m is None or m.accuracy_min is None or m.accuracy_max is None:
            missing.append(r)
            continue
        unit = m.accuracy_unit or "sec/day"
        norm_min, norm_max = _normalise_to_sec_per_day(m.accuracy_min, m.accuracy_max, unit)
        entries.append(AccuracyEntry(
            record=r,
            min_sec_per_day=norm_min,
            max_sec_per_day=norm_max,
            original_min=m.accuracy_min,
            original_max=m.accuracy_max,
            original_unit=unit,
        ))
    return entries, missing


def should_show_accuracy(records: list[WatchRecord]) -> bool:
    """SPEC.md §5.4: 'Hide the section when fewer than 2 selected watches
    have accuracy data.'"""
    entries, _ = build_accuracy_entries(records)
    return len(entries) >= 2


def accuracy_axis_bounds(entries: list[AccuracyEntry]) -> tuple[float, float]:
    """The shared axis span in sec/day. Zero is always folded in, even
    when every watch's own range sits entirely on one side of it — SPEC.md
    §5.4: 'a shared axis with zero marked prominently' means the axis
    itself must always be able to show where zero is, not just watches
    whose span happens to straddle it."""
    if not entries:
        return (0.0, 0.0)
    values = [v for e in entries for v in (e.min_sec_per_day, e.max_sec_per_day)] + [0.0]
    return min(values), max(values)


# --- Milestone 15c: dimension bars -------------------------------------
#
# Pure logic only — no QPainter, no widgets, unit-tested with no event loop.
# saat.ui.dimension_bars turns this into pixels.

@dataclass(frozen=True)
class DimensionBarValue:
    """One watch's slot in a dimension-bar row. magnitude is None when
    this watch has no value for the row's attribute — the caller draws an
    em-dash, never a zero-length bar, for that slot."""

    record: WatchRecord
    magnitude: float | None
    text: str


@dataclass(frozen=True)
class DimensionBarRow:
    """label/values in the same shape as CompareRow; max_magnitude is this
    row's OWN scale reference — SPEC.md §5.4: 'Scale is shared WITHIN a
    row, never across rows,' so each row carries its own, never a scale
    shared with any other row."""

    label: str
    values: list[DimensionBarValue]
    max_magnitude: float


def dimension_bar_columns(is_wishlist: bool) -> list[Column]:
    """Bar-eligible columns for Commit C, minus whichever of price/
    target_price doesn't apply to the active scope — SPEC.md §5.4: 'price
    or target_price depending on the active scope.' Driven entirely by
    columns.py's bar_eligible metadata (which already excludes diameter,
    lug-to-lug and thickness — the silhouette's job, not this one's), not
    a second hardcoded list of keys here."""
    skip_key = "price" if is_wishlist else "target_price"
    return [c for c in COLUMNS if c.bar_eligible and c.key != skip_key]


def _bar_magnitude(column: Column, watch: Watch) -> float | None:
    """The plain numeric magnitude to plot, regardless of whether the
    column's own value is a bare number (weight, lug width, ...) or a
    (amount, currency) tuple (price, target_price) — the same tuple shape
    is_numeric_value() already treats as "numeric" elsewhere in this file."""
    value = column.value(watch)
    if is_empty(value):
        return None
    return float(value[0]) if isinstance(value, tuple) else float(value)


def _bar_value_text(column: Column, watch: Watch, magnitude: float | None) -> str:
    """column.unit, when set, gives a cleaner end-of-bar label than the
    table's own formatter — e.g. water resistance's "200 m" instead of
    "200 m (20 bar)", noise a bar chart doesn't need. Columns without a
    fixed unit (price/target_price: currency varies per watch) fall back
    to the column's normal formatted text."""
    if magnitude is None:
        return EM_DASH
    if column.unit:
        return f"{magnitude:g}{column.unit}"
    return column.text(watch)


def build_dimension_bar_rows(records: list[WatchRecord], is_wishlist: bool = False) -> list[DimensionBarRow]:
    """One row per qualifying numeric attribute (SPEC.md §5.4 Commit C). A
    row appears only when at least 2 selected watches have a value for
    it; a watch without one still gets a slot in that row (as an
    em-dash), rather than the row silently losing a column of alignment."""
    watches = [r.watch for r in records]
    rows: list[DimensionBarRow] = []
    for column in dimension_bar_columns(is_wishlist):
        magnitudes = [_bar_magnitude(column, w) for w in watches]
        if sum(1 for m in magnitudes if m is not None) < 2:
            continue
        values = [
            DimensionBarValue(record=r, magnitude=m, text=_bar_value_text(column, w, m))
            for r, w, m in zip(records, watches, magnitudes)
        ]
        max_magnitude = max((v.magnitude for v in values if v.magnitude is not None), default=0.0)
        rows.append(DimensionBarRow(label=column.label, values=values, max_magnitude=max_magnitude))
    return rows
