from collections.abc import Callable
from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox, QHBoxLayout, QSpinBox, QWidget

from saat.models import Watch
from saat.storage import WatchRecord
from saat.ui import theme
from saat.ui.formatting import EM_DASH

SENTINEL_DATE = QDate(1901, 1, 1)  # below any real watch-collection date; means "unset"


def existing_values(records: list[WatchRecord], getter: Callable[[Watch], object]) -> list[str]:
    """Distinct non-empty values already used elsewhere in the collection, for
    an enum* field's suggestion list. See SPEC.md §4."""
    values: set[str] = set()
    for record in records:
        if record.watch is None:
            continue
        value = getter(record.watch)
        if isinstance(value, list):
            values.update(str(v) for v in value if v)
        elif value:
            values.add(str(value))
    return sorted(values)


def suggested_combo(suggestions: list[str], existing: list[str]) -> QComboBox:
    """An enum* field: editable, offering the spec's suggested values plus
    every value already used elsewhere in the collection, plus free text."""
    combo = QComboBox()
    combo.setEditable(True)
    options = list(dict.fromkeys([*suggestions, *existing]))
    combo.addItem("")
    combo.addItems(options)
    return combo


def refresh_combo_options(combo: QComboBox, suggestions: list[str], existing: list[str]) -> None:
    """Repopulates a suggested_combo's dropdown items in place, preserving
    whatever text is currently typed/selected — for when the suggestion
    source (e.g. sellers.toml, after the manage-sellers dialog closes)
    changes while the combo is still open, without disturbing the user's
    current entry."""
    current_text = combo.currentText()
    combo.blockSignals(True)
    combo.clear()
    options = list(dict.fromkeys([*suggestions, *existing]))
    combo.addItem("")
    combo.addItems(options)
    combo.setCurrentText(current_text)
    combo.blockSignals(False)


def fixed_combo(options: list[str], allow_blank: bool = True) -> QComboBox:
    """A plain (non-suggested) enum field: a closed set, no free text."""
    combo = QComboBox()
    if allow_blank:
        combo.addItem("")
    combo.addItems(options)
    return combo


def combo_value(combo: QComboBox) -> str | None:
    text = combo.currentText().strip()
    return text or None


def set_combo_value(combo: QComboBox, value: str | None) -> None:
    combo.setCurrentText(value or "")


def optional_int_spin(minimum: int, maximum: int, suffix: str = "") -> QSpinBox:
    """A spin box whose minimum - 1 is a sentinel meaning "unset", displayed
    as an em-dash — so a real 0 (e.g. rating) is never confused with absent."""
    spin = QSpinBox()
    spin.setRange(minimum - 1, maximum)
    spin.setSpecialValueText(EM_DASH)
    if suffix:
        spin.setSuffix(suffix)
    spin.setValue(minimum - 1)
    return spin


def int_value(spin: QSpinBox) -> int | None:
    return None if spin.value() == spin.minimum() else spin.value()


def set_int_value(spin: QSpinBox, value: int | None) -> None:
    spin.setValue(spin.minimum() if value is None else value)


def optional_double_spin(minimum: float, maximum: float, decimals: int = 1, suffix: str = "") -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    step = 10 ** (-decimals)
    spin.setDecimals(decimals)
    spin.setRange(minimum - step, maximum)
    spin.setSpecialValueText(EM_DASH)
    if suffix:
        spin.setSuffix(suffix)
    spin.setSingleStep(step)
    spin.setValue(minimum - step)
    return spin


def double_value(spin: QDoubleSpinBox) -> float | None:
    return None if spin.value() == spin.minimum() else spin.value()


def set_double_value(spin: QDoubleSpinBox, value: float | None) -> None:
    spin.setValue(spin.minimum() if value is None else value)


def optional_date_edit() -> QDateEdit:
    edit = QDateEdit()
    edit.setCalendarPopup(True)
    edit.setDisplayFormat("dd.MM.yyyy")
    edit.setMinimumDate(SENTINEL_DATE)
    edit.setSpecialValueText(EM_DASH)
    edit.setDate(SENTINEL_DATE)
    _mute_calendar_weekday_colors(edit.calendarWidget())
    return edit


def _mute_calendar_weekday_colors(calendar) -> None:
    """QCalendarWidget assigns each weekday column its own hard-coded
    QTextCharFormat colour (a Qt default, e.g. red weekends) via a model
    role that a stylesheet's `color` property can't reach -- left alone,
    the popup shows a rainbow no matter what theme.qss says. Flatten every
    weekday to the plate palette's one text colour instead."""
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(theme.colors().text))
    for day in (
        Qt.DayOfWeek.Monday, Qt.DayOfWeek.Tuesday, Qt.DayOfWeek.Wednesday,
        Qt.DayOfWeek.Thursday, Qt.DayOfWeek.Friday, Qt.DayOfWeek.Saturday,
        Qt.DayOfWeek.Sunday,
    ):
        calendar.setWeekdayTextFormat(day, fmt)


def date_value(edit: QDateEdit) -> date | None:
    d = edit.date()
    return None if d == SENTINEL_DATE else date(d.year(), d.month(), d.day())


def set_date_value(edit: QDateEdit, value: date | None) -> None:
    edit.setDate(SENTINEL_DATE if value is None else QDate(value.year, value.month, value.day))


def optional_checkbox() -> QCheckBox:
    """A bool | None field (e.g. hacking, box_and_papers): tristate, where
    partially-checked means "unset" rather than false."""
    box = QCheckBox()
    box.setTristate(True)
    box.setCheckState(Qt.CheckState.PartiallyChecked)
    return box


def bool_value(box: QCheckBox) -> bool | None:
    state = box.checkState()
    if state == Qt.CheckState.PartiallyChecked:
        return None
    return state == Qt.CheckState.Checked


def set_bool_value(box: QCheckBox, value: bool | None) -> None:
    if value is None:
        box.setCheckState(Qt.CheckState.PartiallyChecked)
    else:
        box.setCheckState(Qt.CheckState.Checked if value else Qt.CheckState.Unchecked)


class WaterResistanceField(QWidget):
    """case.water_resistance_m: stored in metres always; the form accepts
    bar/atm and converts on entry. See SPEC.md §4."""

    UNIT_FACTORS = {"m": 1, "bar": 10, "atm": 10}
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._value = optional_int_spin(0, 2000)
        self._unit = fixed_combo(["m", "bar", "atm"], allow_blank=False)
        layout.addWidget(self._value)
        layout.addWidget(self._unit)
        self._value.valueChanged.connect(lambda _: self.changed.emit())
        self._unit.currentTextChanged.connect(lambda _: self.changed.emit())

    def value_m(self) -> int | None:
        raw = int_value(self._value)
        return None if raw is None else raw * self.UNIT_FACTORS[self._unit.currentText()]

    def set_value_m(self, value: int | None) -> None:
        set_int_value(self._value, value)
        self._unit.setCurrentText("m")
