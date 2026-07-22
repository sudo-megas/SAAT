from datetime import date
from typing import Any

EM_DASH = "—"


def is_empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def is_numeric_value(value: Any) -> bool:
    """True for values that should render in Plex Mono: diameters, bph, accuracy,
    prices, dates. False for bool (renders as Yes/No text, not a figure)."""
    if isinstance(value, bool):
        return False
    return isinstance(value, (int, float, date, tuple))


def fmt_number(value: float, unit: str = "") -> str:
    text = str(int(value)) if float(value).is_integer() else f"{value:g}"
    return f"{text}{unit}"


def fmt_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def fmt_list(value: list) -> str:
    return ", ".join(str(v) for v in value)


def fmt_bool(value: bool) -> str:
    return "Yes" if value else "No"


def fmt_water_resistance(value: int) -> str:
    # tomlkit's Integer/Float wrapper types don't collapse round() to a plain
    # int the way builtin float does, so cast explicitly or "20.0 bar" leaks
    # into a real table cell for every watch loaded from disk.
    return f"{value} m ({round(int(value) / 10)} bar)"


def fmt_bph(value: int) -> str:
    return f"{value} bph ({value / 7200:g} Hz)"


def fmt_price(value: tuple[float, str]) -> str:
    price, currency = value
    return f"{price:,.2f} {currency}".strip()


def fmt_accuracy(value: tuple[float | None, float | None, str]) -> str:
    lo, hi, unit = value
    signed = lambda n: "?" if n is None else f"{n:+g}"
    return f"{signed(lo)}/{signed(hi)} {unit}"
