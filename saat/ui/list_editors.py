from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from saat.models import LogEntry, Strap, TimingEntry
from saat.ui.form_fields import (
    combo_value,
    date_value,
    double_value,
    fixed_combo,
    int_value,
    optional_date_edit,
    optional_double_spin,
    optional_int_spin,
    set_combo_value,
    set_date_value,
    set_double_value,
    set_int_value,
    suggested_combo,
)

LOG_KIND_OPTIONS = ["Service", "Battery", "Regulation", "Strap Swap", "Note"]
TIMING_POSITION_OPTIONS = ["Dial Up", "Dial Down", "Crown Up", "Crown Down", "Crown Left", "Worn"]
STRAP_MATERIAL_SUGGESTIONS = ["Leather", "Calf Leather", "Nylon", "NATO", "Silicone", "Rubber", "FKM", "Canvas", "Steel Bracelet", "Mesh"]
STRAP_CLASP_SUGGESTIONS = ["Pin Buckle", "Deployant", "Butterfly", "Ratcheting"]


def _remove_button() -> QPushButton:
    button = QPushButton("✕")
    button.setProperty("variant", "link")
    button.setFixedWidth(28)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def _repolish(widget: QWidget) -> None:
    """A checked/checkable state set while a widget is still hidden (e.g. a
    background tab never yet shown) doesn't reliably repaint on its own —
    Qt's style cache needs an explicit nudge, the same issue the gallery
    thumbnail's active state has."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class StringListEditor(QWidget):
    """tags and dial.complications: a free-form (or suggestion-assisted) list
    of strings. See SPEC.md §4."""

    changed = Signal()

    def __init__(self, suggestions: list[str] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        input_row = QHBoxLayout()
        self._input: QComboBox | QLineEdit
        if suggestions:
            self._input = suggested_combo(suggestions, [])
        else:
            self._input = QLineEdit()
        add_button = QPushButton("Add")
        add_button.clicked.connect(self._add_current)
        input_row.addWidget(self._input, 1)
        input_row.addWidget(add_button)
        layout.addLayout(input_row)

        self._rows_layout = QVBoxLayout()
        self._rows_layout.setSpacing(4)
        layout.addLayout(self._rows_layout)

    def _current_text(self) -> str:
        if isinstance(self._input, QComboBox):
            return self._input.currentText().strip()
        return self._input.text().strip()

    def _clear_input(self) -> None:
        if isinstance(self._input, QComboBox):
            self._input.setCurrentText("")
        else:
            self._input.clear()

    def _add_current(self) -> None:
        text = self._current_text()
        if not text or text in self._items:
            return
        self._items.append(text)
        self._clear_input()
        self._render()
        self.changed.emit()

    def _remove(self, item: str) -> None:
        self._items.remove(item)
        self._render()
        self.changed.emit()

    def _render(self) -> None:
        while self._rows_layout.count():
            child = self._rows_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        for item in self._items:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(QLabel(item), 1)
            remove_button = _remove_button()
            remove_button.clicked.connect(lambda checked=False, i=item: self._remove(i))
            row_layout.addWidget(remove_button)
            self._rows_layout.addWidget(row)

    def values(self) -> list[str]:
        return list(self._items)

    def set_values(self, values: list[str]) -> None:
        self._items = list(values)
        self._render()


class StrapRow(QFrame):
    remove_requested = Signal(QFrame)
    changed = Signal()
    fitted_checked = Signal(QFrame)

    def __init__(self, existing_materials: list[str], default_width_mm: int | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "form-list-row")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.material = suggested_combo(STRAP_MATERIAL_SUGGESTIONS, existing_materials)
        self.material.setEditable(True)
        self.colour = QLineEdit()
        self.colour.setPlaceholderText("Colour")
        self.width_mm = optional_int_spin(0, 30, suffix=" mm")
        if default_width_mm is not None:
            set_int_value(self.width_mm, default_width_mm)
        self.clasp = suggested_combo(STRAP_CLASP_SUGGESTIONS, [])
        self.fitted = QPushButton("Fitted")
        self.fitted.setCheckable(True)

        for widget, label in ((self.material, "Material"), (self.colour, None), (self.width_mm, None), (self.clasp, "Clasp")):
            if label:
                layout.addWidget(QLabel(label))
            layout.addWidget(widget)

        layout.addWidget(self.fitted)
        remove_button = _remove_button()
        remove_button.clicked.connect(lambda: self.remove_requested.emit(self))
        layout.addWidget(remove_button)

        self.material.currentTextChanged.connect(lambda _: self.changed.emit())
        self.colour.textChanged.connect(lambda _: self.changed.emit())
        self.width_mm.valueChanged.connect(lambda _: self.changed.emit())
        self.clasp.currentTextChanged.connect(lambda _: self.changed.emit())
        self.fitted.toggled.connect(self._on_fitted_toggled)

        self.image_filename: str | None = None

    def _on_fitted_toggled(self, checked: bool) -> None:
        if checked:
            self.fitted_checked.emit(self)
        self.changed.emit()

    def get_value(self) -> Strap:
        return Strap(
            material=combo_value(self.material),
            colour=self.colour.text().strip() or None,
            width_mm=int_value(self.width_mm),
            clasp=combo_value(self.clasp),
            fitted=self.fitted.isChecked(),
            image=self.image_filename,
        )

    def set_value(self, strap: Strap) -> None:
        set_combo_value(self.material, strap.material)
        self.colour.setText(strap.colour or "")
        set_int_value(self.width_mm, strap.width_mm)
        set_combo_value(self.clasp, strap.clasp)
        self.fitted.setChecked(strap.fitted)
        _repolish(self.fitted)
        self.image_filename = strap.image


class StrapsEditor(QWidget):
    """SPEC.md §4: at most one strap per watch is fitted — the app enforces
    this. New straps default width_mm to the watch's case.lug_width_mm."""

    changed = Signal()

    def __init__(self, existing_materials: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._existing_materials = existing_materials
        self._default_width_mm: int | None = None
        self._rows: list[StrapRow] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout = QVBoxLayout()
        layout.addLayout(self._rows_layout)

        add_button = QPushButton("Add strap")
        add_button.clicked.connect(lambda: self.add_row())
        layout.addWidget(add_button, alignment=Qt.AlignmentFlag.AlignLeft)

    def set_default_width_mm(self, width_mm: int | None) -> None:
        self._default_width_mm = width_mm

    def add_row(self, initial: Strap | None = None) -> StrapRow:
        row = StrapRow(self._existing_materials, None if initial else self._default_width_mm)
        row.remove_requested.connect(self._remove_row)
        row.changed.connect(self.changed.emit)
        row.fitted_checked.connect(self._on_fitted_checked)
        if initial is not None:
            row.set_value(initial)
        self._rows.append(row)
        self._rows_layout.addWidget(row)
        self.changed.emit()
        return row

    def _remove_row(self, row: StrapRow) -> None:
        self._rows.remove(row)
        row.deleteLater()
        self.changed.emit()

    def _on_fitted_checked(self, checked_row: StrapRow) -> None:
        for row in self._rows:
            if row is not checked_row and row.fitted.isChecked():
                row.fitted.setChecked(False)
                _repolish(row.fitted)

    def values(self) -> list[Strap]:
        return [row.get_value() for row in self._rows]

    def set_values(self, straps: list[Strap]) -> None:
        for row in list(self._rows):
            self._remove_row(row)
        for strap in straps:
            self.add_row(initial=strap)

    def rename_image_reference(self, old_name: str, new_name: str | None) -> None:
        for row in self._rows:
            if row.image_filename == old_name:
                row.image_filename = new_name


class LogRow(QFrame):
    remove_requested = Signal(QFrame)
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "form-list-row")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.date = optional_date_edit()
        self.kind = fixed_combo(LOG_KIND_OPTIONS)
        self.note = QLineEdit()
        self.note.setPlaceholderText("Note")

        layout.addWidget(self.date)
        layout.addWidget(self.kind)
        layout.addWidget(self.note, 1)
        remove_button = _remove_button()
        remove_button.clicked.connect(lambda: self.remove_requested.emit(self))
        layout.addWidget(remove_button)

        self.date.dateChanged.connect(lambda _: self.changed.emit())
        self.kind.currentTextChanged.connect(lambda _: self.changed.emit())
        self.note.textChanged.connect(lambda _: self.changed.emit())

    def get_value(self) -> LogEntry:
        return LogEntry(date=date_value(self.date), kind=combo_value(self.kind), note=self.note.text().strip() or None)

    def set_value(self, entry: LogEntry) -> None:
        set_date_value(self.date, entry.date)
        set_combo_value(self.kind, entry.kind)
        self.note.setText(entry.note or "")


class LogEditor(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[LogRow] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout = QVBoxLayout()
        layout.addLayout(self._rows_layout)
        add_button = QPushButton("Add log entry")
        add_button.clicked.connect(lambda: self.add_row())
        layout.addWidget(add_button, alignment=Qt.AlignmentFlag.AlignLeft)

    def add_row(self, initial: LogEntry | None = None) -> LogRow:
        row = LogRow()
        row.remove_requested.connect(self._remove_row)
        row.changed.connect(self.changed.emit)
        if initial is not None:
            row.set_value(initial)
        self._rows.append(row)
        self._rows_layout.addWidget(row)
        self.changed.emit()
        return row

    def _remove_row(self, row: LogRow) -> None:
        self._rows.remove(row)
        row.deleteLater()
        self.changed.emit()

    def values(self) -> list[LogEntry]:
        return [row.get_value() for row in self._rows]

    def set_values(self, entries: list[LogEntry]) -> None:
        for row in list(self._rows):
            self._remove_row(row)
        for entry in entries:
            self.add_row(initial=entry)


class TimingRow(QFrame):
    remove_requested = Signal(QFrame)
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "form-list-row")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.date = optional_date_edit()
        self.deviation_sec = optional_double_spin(-999, 999, decimals=1, suffix=" sec")
        self.position = fixed_combo(TIMING_POSITION_OPTIONS)

        layout.addWidget(self.date)
        layout.addWidget(self.deviation_sec)
        layout.addWidget(self.position, 1)
        remove_button = _remove_button()
        remove_button.clicked.connect(lambda: self.remove_requested.emit(self))
        layout.addWidget(remove_button)

        self.date.dateChanged.connect(lambda _: self.changed.emit())
        self.deviation_sec.valueChanged.connect(lambda _: self.changed.emit())
        self.position.currentTextChanged.connect(lambda _: self.changed.emit())

    def get_value(self) -> TimingEntry:
        return TimingEntry(date=date_value(self.date), deviation_sec=double_value(self.deviation_sec), position=combo_value(self.position))

    def set_value(self, entry: TimingEntry) -> None:
        set_date_value(self.date, entry.date)
        set_double_value(self.deviation_sec, entry.deviation_sec)
        set_combo_value(self.position, entry.position)


class TimingEditor(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[TimingRow] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout = QVBoxLayout()
        layout.addLayout(self._rows_layout)
        add_button = QPushButton("Add timing reading")
        add_button.clicked.connect(lambda: self.add_row())
        layout.addWidget(add_button, alignment=Qt.AlignmentFlag.AlignLeft)

    def add_row(self, initial: TimingEntry | None = None) -> TimingRow:
        row = TimingRow()
        row.remove_requested.connect(self._remove_row)
        row.changed.connect(self.changed.emit)
        if initial is not None:
            row.set_value(initial)
        self._rows.append(row)
        self._rows_layout.addWidget(row)
        self.changed.emit()
        return row

    def _remove_row(self, row: TimingRow) -> None:
        self._rows.remove(row)
        row.deleteLater()
        self.changed.emit()

    def values(self) -> list[TimingEntry]:
        return [row.get_value() for row in self._rows]

    def set_values(self, entries: list[TimingEntry]) -> None:
        for row in list(self._rows):
            self._remove_row(row)
        for entry in entries:
            self.add_row(initial=entry)
