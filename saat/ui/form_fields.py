from collections.abc import Callable
from datetime import date

from PySide6.QtCore import QCoreApplication, QDate, QLocale, Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox, QHBoxLayout, QSpinBox, QWidget

from saat.models import Watch
from saat.storage import WatchRecord
from saat.ui import theme
from saat.ui.formatting import EM_DASH

SENTINEL_DATE = QDate(1901, 1, 1)  # below any real watch-collection date; means "unset"

# Context shared by every enum*-suggestion/option list (watch_form.py,
# list_editors.py) -- QT_TRANSLATE_NOOP-marked at definition, looked up here
# by value. One context so translators work through one list rather than
# seventeen fragmented ones.
ENUM_CHOICES_CONTEXT = "EnumChoices"


def enum_label(value: str) -> str:
    """Translated display label for a canonical enum* value -- the read-side
    counterpart to the combo boxes' write-side split (combo_value()/
    set_combo_value()). Use anywhere an enum* field (see the QT_TRANSLATE_NOOP
    lists in watch_form.py/list_editors.py) is *displayed* outside a combo
    box: table cells, detail-page rows, PDF export, compare view. "Translation
    happens only at display time" applies to every display surface, not only
    the edit-time combo -- never call this on brand/model/nickname/seller/
    tags/notes or any other free-typed, non-enum field."""
    return QCoreApplication.translate(ENUM_CHOICES_CONTEXT, value)


def existing_values(records: list[WatchRecord], getter: Callable[[Watch], object]) -> list[str]:
    """Distinct non-empty values already used elsewhere in the collection, for
    an enum* field's suggestion list. See SPEC.md §4. Always canonical
    English (read straight from disk) -- never translated."""
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


def _populate_enum_items(combo: QComboBox, suggestions: list[str], existing: list[str], translate: bool) -> None:
    """Shared item-building for suggested_combo/refresh_combo_options:
    canonical value always in itemData (what combo_value()/set_combo_value()
    read/write), translated label only for values that are actual `enum*`
    suggestions -- and only when `translate` is set (seller names are
    proper nouns harvested from sellers.toml, not fixed vocabulary, so they
    pass through `suggestions` too but must never be translated). `existing`
    values are harvested from disk (already canonical English) and are
    never translated either way -- and dedup happens on the canonical
    value, before labels are built, so a suggestion and an on-disk value
    that are the same thing never render as two items under different
    labels."""
    canonical = list(dict.fromkeys([*suggestions, *existing]))
    suggestion_set = set(suggestions)
    combo.addItem("", "")
    for value in canonical:
        label = enum_label(value) if translate and value in suggestion_set else value
        combo.addItem(label, value)


def suggested_combo(suggestions: list[str], existing: list[str], translate: bool = True) -> QComboBox:
    """An enum* field: editable, offering the spec's suggested values plus
    every value already used elsewhere in the collection, plus free text.
    Item text is the translated display label; item data (and whatever
    combo_value() returns) is always the canonical English value. Pass
    `translate=False` when `suggestions` are proper nouns rather than fixed
    enum vocabulary (e.g. seller names) -- never eligible for translation."""
    combo = QComboBox()
    combo.setEditable(True)
    _populate_enum_items(combo, suggestions, existing, translate)
    return combo


def refresh_combo_options(
    combo: QComboBox, suggestions: list[str], existing: list[str], translate: bool = True
) -> None:
    """Repopulates a suggested_combo's dropdown items in place, preserving
    whatever text is currently typed/selected — for when the suggestion
    source (e.g. sellers.toml, after the manage-sellers dialog closes)
    changes while the combo is still open, without disturbing the user's
    current entry."""
    current_text = combo.currentText()
    combo.blockSignals(True)
    combo.clear()
    _populate_enum_items(combo, suggestions, existing, translate)
    combo.setCurrentText(current_text)
    combo.blockSignals(False)


def fixed_combo(options: list[str], allow_blank: bool = True, translate: bool = True) -> QComboBox:
    """A plain (non-suggested) enum field: a closed set, no free text. Item
    text is the translated label and item data is the canonical value when
    `translate` is set (the default, for real enum* fields); pass
    `translate=False` for closed sets that aren't translatable words at all
    (e.g. WaterResistanceField's "m"/"bar"/"atm" unit abbreviations), which
    keeps plain addItems() behaviour."""
    combo = QComboBox()
    if allow_blank:
        combo.addItem("", "")
    if translate:
        for value in options:
            combo.addItem(enum_label(value), value)
    else:
        combo.addItems(options)
    return combo


def retranslate_combo(combo: QComboBox) -> None:
    """Relabels a suggested_combo()/fixed_combo()-built combo's items with
    freshly translated display text on a language change. setItemText()
    only changes what's displayed -- it never touches itemData or which
    index is selected -- so there's none of the "preserve the selection
    across a rebuild" problem top_bar.py's sort/preset combos have: nothing
    here is cleared and rebuilt, only relabeled in place. Reads each item's
    own itemData rather than needing the original suggestions/existing
    lists threaded back in from whatever built the combo, so any widget
    holding a combo reference can call this directly with no extra state
    of its own. A suggested_combo's free-typed text (no matching item,
    currentIndex() == -1) is untouched either way, correctly -- free text
    is never enum vocabulary."""
    for i in range(combo.count()):
        data = combo.itemData(i)
        if data:
            combo.setItemText(i, enum_label(data))


def combo_value(combo: QComboBox) -> str | None:
    data = combo.currentData()
    if data is not None and data != "":
        return data
    text = combo.currentText().strip()
    return text or None


def set_combo_value(combo: QComboBox, value: str | None) -> None:
    index = combo.findData(value) if value else -1
    if index >= 0:
        combo.setCurrentIndex(index)
    else:
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
    # QWidget.locale() is a fixed value captured once, not re-derived from
    # QLocale.setDefault() on every access (unlike a bare QLocale() call
    # elsewhere) -- verified empirically. Set explicitly so the popup's
    # month/weekday names match the language active when this field is
    # built, same construction-time-only scope as the weekday colour
    # muting just above (neither is live-refreshed on a later theme or
    # language change -- these fields don't outlive the dialog they're on).
    edit.calendarWidget().setLocale(QLocale())
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
        self._unit = fixed_combo(["m", "bar", "atm"], allow_blank=False, translate=False)
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
