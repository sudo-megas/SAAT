from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QT_TRANSLATE_NOOP

from saat.models import Strap, Watch
from saat.ui.form_fields import enum_label
from saat.ui.formatting import (
    EM_DASH,
    fmt_accuracy,
    fmt_bool,
    fmt_bph,
    fmt_date,
    fmt_list,
    fmt_number,
    fmt_price,
    fmt_water_resistance,
    is_empty,
    is_numeric_value,
)
from saat.ui.wear_stats import days_since_worn

# Group names and Column.label below are QT_TRANSLATE_NOOP-marked -- same
# reason as watch_form.py's enum lists: lupdate can't see a translated value
# reached via a loop/dict variable, only a literal typed at the call site.
# Values stay canonical English at runtime; table_view.py/top_bar.py/
# sidebar.py/compare.py render the actual translated label via
# QCoreApplication.translate("Columns", value) at their own call sites.
GROUP_ORDER = [
    QT_TRANSLATE_NOOP("Columns", "Identity"),
    QT_TRANSLATE_NOOP("Columns", "Movement"),
    QT_TRANSLATE_NOOP("Columns", "Case"),
    QT_TRANSLATE_NOOP("Columns", "Dial"),
    QT_TRANSLATE_NOOP("Columns", "Straps"),
    QT_TRANSLATE_NOOP("Columns", "Acquisition"),
]


def _fitted_strap(watch: Watch) -> Strap | None:
    return next((s for s in watch.straps if s.fitted), None)


def _fitted_attr(watch: Watch, attr: str):
    strap = _fitted_strap(watch)
    return getattr(strap, attr) if strap else None


def _get_price(watch: Watch):
    if watch.acquisition.price is None:
        return None
    return (watch.acquisition.price, watch.acquisition.currency or "")


def _get_target_price(watch: Watch):
    if watch.acquisition.target_price is None:
        return None
    return (watch.acquisition.target_price, watch.acquisition.currency or "")


_NEVER_WORN_SORT_DAYS = 10**6  # sorts ahead of any real day count — "least worn" ever


def _least_worn_key(watch: Watch) -> int:
    days = days_since_worn(watch)
    return -(days if days is not None else _NEVER_WORN_SORT_DAYS)


def _get_accuracy(watch: Watch):
    m = watch.movement
    if m.accuracy_min is None and m.accuracy_max is None:
        return None
    return (m.accuracy_min, m.accuracy_max, m.accuracy_unit or "sec/day")


@dataclass
class Column:
    key: str
    label: str
    group: str
    getter: Callable[[Watch], Any]
    formatter: Callable[[Any], str] = str
    # Milestone 15c: compare view's dimension bars (saat/ui/compare.py's
    # dimension_bar_columns) read bar_eligible instead of a second,
    # hardcoded list of keys living in compare.py. unit is a plain suffix
    # (leading space included, e.g. " g") for that bar's end-of-bar label —
    # cleaner than the table's own formatter for columns like water
    # resistance, whose "(N bar)" parenthetical is noise on a bar chart.
    unit: str = ""
    bar_eligible: bool = False
    # Set on columns whose raw value is a canonical enum* value (one of the
    # QT_TRANSLATE_NOOP lists in watch_form.py/list_editors.py) rather than
    # free text or a number -- "translation happens only at display time"
    # applies to every display surface, table cells included, not only the
    # edit-time combo box. sort_key()/value() below stay on the untranslated
    # getter() result regardless, so sort order never depends on UI language.
    translate_values: bool = False

    def value(self, watch: Watch) -> Any:
        return self.getter(watch)

    def text(self, watch: Watch) -> str:
        value = self.getter(watch)
        if is_empty(value):
            return EM_DASH
        if self.translate_values:
            value = [enum_label(v) for v in value] if isinstance(value, list) else enum_label(value)
        return self.formatter(value)


COLUMNS: list[Column] = [
    # Identity
    Column("brand", QT_TRANSLATE_NOOP("Columns", "Brand"), "Identity", lambda w: w.brand),
    Column("model", QT_TRANSLATE_NOOP("Columns", "Model"), "Identity", lambda w: w.model),
    Column("reference", QT_TRANSLATE_NOOP("Columns", "Reference"), "Identity", lambda w: w.reference),
    Column("nickname", QT_TRANSLATE_NOOP("Columns", "Nickname"), "Identity", lambda w: w.nickname),
    Column("group", QT_TRANSLATE_NOOP("Columns", "Group"), "Identity", lambda w: w.group, translate_values=True),
    Column("style", QT_TRANSLATE_NOOP("Columns", "Style"), "Identity", lambda w: w.style, translate_values=True),
    Column("status", QT_TRANSLATE_NOOP("Columns", "Status"), "Identity", lambda w: w.status, translate_values=True),
    Column("storage", QT_TRANSLATE_NOOP("Columns", "Storage"), "Identity", lambda w: w.storage),
    Column("rating", QT_TRANSLATE_NOOP("Columns", "Rating"), "Identity", lambda w: w.rating),
    Column("tags", QT_TRANSLATE_NOOP("Columns", "Tags"), "Identity", lambda w: w.tags, fmt_list),
    # Movement
    Column("caliber", QT_TRANSLATE_NOOP("Columns", "Caliber"), "Movement", lambda w: w.movement.caliber),
    Column("movement_kind", QT_TRANSLATE_NOOP("Columns", "Movement"), "Movement", lambda w: w.movement.kind, translate_values=True),
    Column("power_reserve_hours", QT_TRANSLATE_NOOP("Columns", "Power Reserve"), "Movement", lambda w: w.movement.power_reserve_hours, lambda v: fmt_number(v, "h"), unit="h", bar_eligible=True),
    Column("battery_life_years", QT_TRANSLATE_NOOP("Columns", "Battery Life"), "Movement", lambda w: w.movement.battery_life_years, lambda v: fmt_number(v, "y")),
    Column("accuracy", QT_TRANSLATE_NOOP("Columns", "Accuracy"), "Movement", _get_accuracy, fmt_accuracy),
    Column("jewels", QT_TRANSLATE_NOOP("Columns", "Jewels"), "Movement", lambda w: w.movement.jewels),
    Column("bph", QT_TRANSLATE_NOOP("Columns", "Frequency"), "Movement", lambda w: w.movement.bph, fmt_bph),
    Column("hacking", QT_TRANSLATE_NOOP("Columns", "Hacking"), "Movement", lambda w: w.movement.hacking, fmt_bool),
    Column("handwinding", QT_TRANSLATE_NOOP("Columns", "Handwinding"), "Movement", lambda w: w.movement.handwinding, fmt_bool),
    Column("origin", QT_TRANSLATE_NOOP("Columns", "Origin"), "Movement", lambda w: w.movement.origin),
    # Case
    Column("diameter_mm", QT_TRANSLATE_NOOP("Columns", "Diameter"), "Case", lambda w: w.case.diameter_mm, lambda v: fmt_number(v, " mm")),
    Column("lug_to_lug_mm", QT_TRANSLATE_NOOP("Columns", "Lug-to-Lug"), "Case", lambda w: w.case.lug_to_lug_mm, lambda v: fmt_number(v, " mm")),
    Column("thickness_mm", QT_TRANSLATE_NOOP("Columns", "Thickness"), "Case", lambda w: w.case.thickness_mm, lambda v: fmt_number(v, " mm")),
    Column("lug_width_mm", QT_TRANSLATE_NOOP("Columns", "Lug Width"), "Case", lambda w: w.case.lug_width_mm, lambda v: fmt_number(v, " mm"), unit=" mm", bar_eligible=True),
    Column("case_material", QT_TRANSLATE_NOOP("Columns", "Material"), "Case", lambda w: w.case.material, translate_values=True),
    Column("crystal", QT_TRANSLATE_NOOP("Columns", "Crystal"), "Case", lambda w: w.case.crystal, translate_values=True),
    Column("crown", QT_TRANSLATE_NOOP("Columns", "Crown"), "Case", lambda w: w.case.crown, translate_values=True),
    Column("bezel", QT_TRANSLATE_NOOP("Columns", "Bezel"), "Case", lambda w: w.case.bezel, translate_values=True),
    Column("caseback", QT_TRANSLATE_NOOP("Columns", "Caseback"), "Case", lambda w: w.case.caseback, translate_values=True),
    Column("water_resistance_m", QT_TRANSLATE_NOOP("Columns", "Water Resistance"), "Case", lambda w: w.case.water_resistance_m, fmt_water_resistance, unit=" m", bar_eligible=True),
    Column("weight_g", QT_TRANSLATE_NOOP("Columns", "Weight"), "Case", lambda w: w.case.weight_g, lambda v: fmt_number(v, " g"), unit=" g", bar_eligible=True),
    # Dial
    Column("dial_colour", QT_TRANSLATE_NOOP("Columns", "Colour"), "Dial", lambda w: w.dial.colour),
    Column("dial_material", QT_TRANSLATE_NOOP("Columns", "Material"), "Dial", lambda w: w.dial.material),
    Column("indices", QT_TRANSLATE_NOOP("Columns", "Indices"), "Dial", lambda w: w.dial.indices, translate_values=True),
    Column("lume", QT_TRANSLATE_NOOP("Columns", "Lume"), "Dial", lambda w: w.dial.lume),
    Column("complications", QT_TRANSLATE_NOOP("Columns", "Complications"), "Dial", lambda w: w.dial.complications, fmt_list, translate_values=True),
    # Straps (the currently fitted one)
    Column("strap_material", QT_TRANSLATE_NOOP("Columns", "Strap Material"), "Straps", lambda w: _fitted_attr(w, "material"), translate_values=True),
    Column("strap_colour", QT_TRANSLATE_NOOP("Columns", "Strap Colour"), "Straps", lambda w: _fitted_attr(w, "colour")),
    Column("strap_width_mm", QT_TRANSLATE_NOOP("Columns", "Strap Width"), "Straps", lambda w: _fitted_attr(w, "width_mm"), lambda v: fmt_number(v, " mm")),
    Column("strap_clasp", QT_TRANSLATE_NOOP("Columns", "Clasp"), "Straps", lambda w: _fitted_attr(w, "clasp"), translate_values=True),
    # Acquisition
    Column("acquired_date", QT_TRANSLATE_NOOP("Columns", "Acquired"), "Acquisition", lambda w: w.acquisition.date, fmt_date),
    Column("price", QT_TRANSLATE_NOOP("Columns", "Price"), "Acquisition", _get_price, fmt_price, bar_eligible=True),
    Column("target_price", QT_TRANSLATE_NOOP("Columns", "Target Price"), "Acquisition", _get_target_price, fmt_price, bar_eligible=True),
    Column("target_date", QT_TRANSLATE_NOOP("Columns", "Target Date"), "Acquisition", lambda w: w.acquisition.target_date, fmt_date),
    Column("seller", QT_TRANSLATE_NOOP("Columns", "Seller"), "Acquisition", lambda w: w.acquisition.seller),
    Column("condition", QT_TRANSLATE_NOOP("Columns", "Condition"), "Acquisition", lambda w: w.acquisition.condition, translate_values=True),
    Column("box_and_papers", QT_TRANSLATE_NOOP("Columns", "Box & Papers"), "Acquisition", lambda w: w.acquisition.box_and_papers, fmt_bool),
    Column("warranty_until", QT_TRANSLATE_NOOP("Columns", "Warranty Until"), "Acquisition", lambda w: w.acquisition.warranty_until, fmt_date),
    # "Derived" is deliberately not in GROUP_ORDER: sort-only, never a table
    # column or preset. SPEC.md §4's "Least worn" sort option. Never shown
    # as a group heading, so its own label doesn't need translation --
    # wrapped anyway for consistency and in case that ever changes.
    Column("least_worn", QT_TRANSLATE_NOOP("Columns", "Least Worn"), "Derived", _least_worn_key),
]

COLUMNS_BY_KEY: dict[str, Column] = {c.key: c for c in COLUMNS}

DEFAULT_COLUMN_KEYS = [
    "brand", "model", "style", "movement_kind",
    "diameter_mm", "lug_width_mm", "water_resistance_m", "acquired_date",
]

# SPEC.md §5.12: Wishlist scope's table default — wear/spec columns don't
# apply pre-purchase, target price and desire (rating) do.
DEFAULT_WISHLIST_COLUMN_KEYS = ["brand", "model", "target_price", "rating", "seller"]

COLUMN_PRESETS: dict[str, list[str]] = {
    group: [c.key for c in COLUMNS if c.group == group] for group in GROUP_ORDER
}

SORT_OPTIONS = ["brand", "model", "rating", "acquired_date", "least_worn"]

# SPEC.md §5.12: a separate, smaller list for Wishlist scope — least_worn and
# acquired_date are meaningless for a watch that hasn't been bought yet.
WISHLIST_SORT_OPTIONS = ["brand", "model", "rating", "target_price"]


def sort_key(key: str) -> Callable[[Watch], tuple]:
    column = COLUMNS_BY_KEY[key]

    def key_func(watch: Watch) -> tuple:
        value = column.value(watch)
        return (value is None, value if value is not None else 0)

    return key_func
