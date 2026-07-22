from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from saat.models import Strap, Watch
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

GROUP_ORDER = ["Identity", "Movement", "Case", "Dial", "Straps", "Acquisition"]


def _fitted_strap(watch: Watch) -> Strap | None:
    return next((s for s in watch.straps if s.fitted), None)


def _fitted_attr(watch: Watch, attr: str):
    strap = _fitted_strap(watch)
    return getattr(strap, attr) if strap else None


def _get_price(watch: Watch):
    if watch.acquisition.price is None:
        return None
    return (watch.acquisition.price, watch.acquisition.currency or "")


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

    def value(self, watch: Watch) -> Any:
        return self.getter(watch)

    def text(self, watch: Watch) -> str:
        value = self.getter(watch)
        return EM_DASH if is_empty(value) else self.formatter(value)


COLUMNS: list[Column] = [
    # Identity
    Column("brand", "Brand", "Identity", lambda w: w.brand),
    Column("model", "Model", "Identity", lambda w: w.model),
    Column("reference", "Reference", "Identity", lambda w: w.reference),
    Column("nickname", "Nickname", "Identity", lambda w: w.nickname),
    Column("group", "Group", "Identity", lambda w: w.group),
    Column("style", "Style", "Identity", lambda w: w.style),
    Column("status", "Status", "Identity", lambda w: w.status),
    Column("storage", "Storage", "Identity", lambda w: w.storage),
    Column("rating", "Rating", "Identity", lambda w: w.rating),
    Column("tags", "Tags", "Identity", lambda w: w.tags, fmt_list),
    # Movement
    Column("caliber", "Caliber", "Movement", lambda w: w.movement.caliber),
    Column("movement_kind", "Movement", "Movement", lambda w: w.movement.kind),
    Column("power_reserve_hours", "Power Reserve", "Movement", lambda w: w.movement.power_reserve_hours, lambda v: fmt_number(v, "h")),
    Column("battery_life_years", "Battery Life", "Movement", lambda w: w.movement.battery_life_years, lambda v: fmt_number(v, "y")),
    Column("accuracy", "Accuracy", "Movement", _get_accuracy, fmt_accuracy),
    Column("jewels", "Jewels", "Movement", lambda w: w.movement.jewels),
    Column("bph", "Frequency", "Movement", lambda w: w.movement.bph, fmt_bph),
    Column("hacking", "Hacking", "Movement", lambda w: w.movement.hacking, fmt_bool),
    Column("handwinding", "Handwinding", "Movement", lambda w: w.movement.handwinding, fmt_bool),
    Column("origin", "Origin", "Movement", lambda w: w.movement.origin),
    # Case
    Column("diameter_mm", "Diameter", "Case", lambda w: w.case.diameter_mm, lambda v: fmt_number(v, " mm")),
    Column("lug_to_lug_mm", "Lug-to-Lug", "Case", lambda w: w.case.lug_to_lug_mm, lambda v: fmt_number(v, " mm")),
    Column("thickness_mm", "Thickness", "Case", lambda w: w.case.thickness_mm, lambda v: fmt_number(v, " mm")),
    Column("lug_width_mm", "Lug Width", "Case", lambda w: w.case.lug_width_mm, lambda v: fmt_number(v, " mm")),
    Column("case_material", "Material", "Case", lambda w: w.case.material),
    Column("crystal", "Crystal", "Case", lambda w: w.case.crystal),
    Column("crown", "Crown", "Case", lambda w: w.case.crown),
    Column("bezel", "Bezel", "Case", lambda w: w.case.bezel),
    Column("caseback", "Caseback", "Case", lambda w: w.case.caseback),
    Column("water_resistance_m", "Water Resistance", "Case", lambda w: w.case.water_resistance_m, fmt_water_resistance),
    Column("weight_g", "Weight", "Case", lambda w: w.case.weight_g, lambda v: fmt_number(v, " g")),
    # Dial
    Column("dial_colour", "Colour", "Dial", lambda w: w.dial.colour),
    Column("dial_material", "Material", "Dial", lambda w: w.dial.material),
    Column("indices", "Indices", "Dial", lambda w: w.dial.indices),
    Column("lume", "Lume", "Dial", lambda w: w.dial.lume),
    Column("complications", "Complications", "Dial", lambda w: w.dial.complications, fmt_list),
    # Straps (the currently fitted one)
    Column("strap_material", "Strap Material", "Straps", lambda w: _fitted_attr(w, "material")),
    Column("strap_colour", "Strap Colour", "Straps", lambda w: _fitted_attr(w, "colour")),
    Column("strap_width_mm", "Strap Width", "Straps", lambda w: _fitted_attr(w, "width_mm"), lambda v: fmt_number(v, " mm")),
    Column("strap_clasp", "Clasp", "Straps", lambda w: _fitted_attr(w, "clasp")),
    # Acquisition
    Column("acquired_date", "Acquired", "Acquisition", lambda w: w.acquisition.date, fmt_date),
    Column("price", "Price", "Acquisition", _get_price, fmt_price),
    Column("seller", "Seller", "Acquisition", lambda w: w.acquisition.seller),
    Column("condition", "Condition", "Acquisition", lambda w: w.acquisition.condition),
    Column("box_and_papers", "Box & Papers", "Acquisition", lambda w: w.acquisition.box_and_papers, fmt_bool),
    Column("warranty_until", "Warranty Until", "Acquisition", lambda w: w.acquisition.warranty_until, fmt_date),
    # "Derived" is deliberately not in GROUP_ORDER: sort-only, never a table
    # column or preset. SPEC.md §4's "Least worn" sort option.
    Column("least_worn", "Least Worn", "Derived", _least_worn_key),
]

COLUMNS_BY_KEY: dict[str, Column] = {c.key: c for c in COLUMNS}

DEFAULT_COLUMN_KEYS = [
    "brand", "model", "style", "movement_kind",
    "diameter_mm", "lug_width_mm", "water_resistance_m", "acquired_date",
]

COLUMN_PRESETS: dict[str, list[str]] = {
    group: [c.key for c in COLUMNS if c.group == group] for group in GROUP_ORDER
}

SORT_OPTIONS = ["brand", "model", "rating", "acquired_date", "least_worn"]


def sort_key(key: str) -> Callable[[Watch], tuple]:
    column = COLUMNS_BY_KEY[key]

    def key_func(watch: Watch) -> tuple:
        value = column.value(watch)
        return (value is None, value if value is not None else 0)

    return key_func
