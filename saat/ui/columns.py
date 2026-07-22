from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from saat.models import Strap, Watch

EM_DASH = "—"

GROUP_ORDER = ["Identity", "Movement", "Case", "Dial", "Straps", "Acquisition"]


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def is_numeric_value(value: Any) -> bool:
    """True for values that should render in Plex Mono: diameters, bph, accuracy,
    prices, dates. False for bool (renders as Yes/No text, not a figure)."""
    if isinstance(value, bool):
        return False
    return isinstance(value, (int, float, date, tuple))


def _fmt_number(value: float, unit: str = "") -> str:
    text = str(int(value)) if float(value).is_integer() else f"{value:g}"
    return f"{text}{unit}"


def _fmt_date(value) -> str:
    return value.strftime("%d.%m.%Y")


def _fmt_list(value: list) -> str:
    return ", ".join(str(v) for v in value)


def _fmt_bool(value: bool) -> str:
    return "Yes" if value else "No"


def _fmt_water_resistance(value: int) -> str:
    # tomlkit's Integer/Float wrapper types don't collapse round() to a plain
    # int the way builtin float does, so cast explicitly or "20.0 bar" leaks
    # into a real table cell for every watch loaded from disk.
    return f"{value} m ({round(int(value) / 10)} bar)"


def _fmt_bph(value: int) -> str:
    return f"{value} bph ({value / 7200:g} Hz)"


def _fmt_price(value: tuple[float, str]) -> str:
    price, currency = value
    return f"{price:,.2f} {currency}".strip()


def _fmt_accuracy(value: tuple[float | None, float | None, str]) -> str:
    lo, hi, unit = value
    signed = lambda n: "?" if n is None else f"{n:+g}"
    return f"{signed(lo)}/{signed(hi)} {unit}"


def _fitted_strap(watch: Watch) -> Strap | None:
    return next((s for s in watch.straps if s.fitted), None)


def _fitted_attr(watch: Watch, attr: str):
    strap = _fitted_strap(watch)
    return getattr(strap, attr) if strap else None


def _get_price(watch: Watch):
    if watch.acquisition.price is None:
        return None
    return (watch.acquisition.price, watch.acquisition.currency or "")


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
        return EM_DASH if _is_empty(value) else self.formatter(value)


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
    Column("tags", "Tags", "Identity", lambda w: w.tags, _fmt_list),
    # Movement
    Column("caliber", "Caliber", "Movement", lambda w: w.movement.caliber),
    Column("movement_kind", "Movement", "Movement", lambda w: w.movement.kind),
    Column("power_reserve_hours", "Power Reserve", "Movement", lambda w: w.movement.power_reserve_hours, lambda v: _fmt_number(v, "h")),
    Column("battery_life_years", "Battery Life", "Movement", lambda w: w.movement.battery_life_years, lambda v: _fmt_number(v, "y")),
    Column("accuracy", "Accuracy", "Movement", _get_accuracy, _fmt_accuracy),
    Column("jewels", "Jewels", "Movement", lambda w: w.movement.jewels),
    Column("bph", "Frequency", "Movement", lambda w: w.movement.bph, _fmt_bph),
    Column("hacking", "Hacking", "Movement", lambda w: w.movement.hacking, _fmt_bool),
    Column("handwinding", "Handwinding", "Movement", lambda w: w.movement.handwinding, _fmt_bool),
    Column("origin", "Origin", "Movement", lambda w: w.movement.origin),
    # Case
    Column("diameter_mm", "Diameter", "Case", lambda w: w.case.diameter_mm, lambda v: _fmt_number(v, " mm")),
    Column("lug_to_lug_mm", "Lug-to-Lug", "Case", lambda w: w.case.lug_to_lug_mm, lambda v: _fmt_number(v, " mm")),
    Column("thickness_mm", "Thickness", "Case", lambda w: w.case.thickness_mm, lambda v: _fmt_number(v, " mm")),
    Column("lug_width_mm", "Lug Width", "Case", lambda w: w.case.lug_width_mm, lambda v: _fmt_number(v, " mm")),
    Column("case_material", "Material", "Case", lambda w: w.case.material),
    Column("crystal", "Crystal", "Case", lambda w: w.case.crystal),
    Column("crown", "Crown", "Case", lambda w: w.case.crown),
    Column("bezel", "Bezel", "Case", lambda w: w.case.bezel),
    Column("caseback", "Caseback", "Case", lambda w: w.case.caseback),
    Column("water_resistance_m", "Water Resistance", "Case", lambda w: w.case.water_resistance_m, _fmt_water_resistance),
    Column("weight_g", "Weight", "Case", lambda w: w.case.weight_g, lambda v: _fmt_number(v, " g")),
    # Dial
    Column("dial_colour", "Colour", "Dial", lambda w: w.dial.colour),
    Column("dial_material", "Material", "Dial", lambda w: w.dial.material),
    Column("indices", "Indices", "Dial", lambda w: w.dial.indices),
    Column("lume", "Lume", "Dial", lambda w: w.dial.lume),
    Column("complications", "Complications", "Dial", lambda w: w.dial.complications, _fmt_list),
    # Straps (the currently fitted one)
    Column("strap_material", "Strap Material", "Straps", lambda w: _fitted_attr(w, "material")),
    Column("strap_colour", "Strap Colour", "Straps", lambda w: _fitted_attr(w, "colour")),
    Column("strap_width_mm", "Strap Width", "Straps", lambda w: _fitted_attr(w, "width_mm"), lambda v: _fmt_number(v, " mm")),
    Column("strap_clasp", "Clasp", "Straps", lambda w: _fitted_attr(w, "clasp")),
    # Acquisition
    Column("acquired_date", "Acquired", "Acquisition", lambda w: w.acquisition.date, _fmt_date),
    Column("price", "Price", "Acquisition", _get_price, _fmt_price),
    Column("seller", "Seller", "Acquisition", lambda w: w.acquisition.seller),
    Column("condition", "Condition", "Acquisition", lambda w: w.acquisition.condition),
    Column("box_and_papers", "Box & Papers", "Acquisition", lambda w: w.acquisition.box_and_papers, _fmt_bool),
    Column("warranty_until", "Warranty Until", "Acquisition", lambda w: w.acquisition.warranty_until, _fmt_date),
]

COLUMNS_BY_KEY: dict[str, Column] = {c.key: c for c in COLUMNS}

DEFAULT_COLUMN_KEYS = [
    "brand", "model", "style", "movement_kind",
    "diameter_mm", "lug_width_mm", "water_resistance_m", "acquired_date",
]

COLUMN_PRESETS: dict[str, list[str]] = {
    group: [c.key for c in COLUMNS if c.group == group] for group in GROUP_ORDER
}

SORT_OPTIONS = ["brand", "model", "rating", "acquired_date"]


def sort_key(key: str) -> Callable[[Watch], tuple]:
    column = COLUMNS_BY_KEY[key]

    def key_func(watch: Watch) -> tuple:
        value = column.value(watch)
        return (value is None, value if value is not None else 0)

    return key_func
