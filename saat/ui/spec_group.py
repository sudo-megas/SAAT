from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from saat.ui.formatting import EM_DASH, is_empty
from saat.ui.minute_track import MinuteTrackHeader


@dataclass
class SpecRow:
    label: str
    text: str = EM_DASH
    numeric: bool = False
    widget: QWidget | None = None  # overrides the value label, e.g. a clickable URL


def spec_row(label: str, value: Any, formatter: Callable[[Any], str] = str, numeric: bool = False) -> SpecRow:
    """Build a row the way Column.text() renders a table cell: em-dash for an
    absent value, the formatted value otherwise. See SPEC.md §4."""
    if is_empty(value):
        return SpecRow(label, EM_DASH)
    return SpecRow(label, formatter(value), numeric=numeric)


class SpecGroup(QWidget):
    """A titled section on the detail page: minute-track header plus label/value
    rows. See SPEC.md §5.6 and §6. Built through build_spec_group()."""

    def __init__(self, title: str, rows: list[SpecRow], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(MinuteTrackHeader(title))

        grid = QGridLayout()
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        for i, row in enumerate(rows):
            label_widget = QLabel(row.label)
            label_widget.setProperty("class", "spec-row-label")
            grid.addWidget(label_widget, i, 0, Qt.AlignmentFlag.AlignTop)

            if row.widget is not None:
                grid.addWidget(row.widget, i, 1, Qt.AlignmentFlag.AlignTop)
            else:
                value_widget = QLabel(row.text)
                value_widget.setProperty("class", "spec-row-value-mono" if row.numeric else "spec-row-value")
                value_widget.setWordWrap(True)
                grid.addWidget(value_widget, i, 1, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(grid)


def build_spec_group(title: str, rows: list[SpecRow]) -> SpecGroup | None:
    """None hides the whole group when every field is absent — SPEC.md §5.6.
    Otherwise every row renders, em-dash included: a shown row is never itself
    hidden (§4)."""
    if all(row.text == EM_DASH for row in rows):
        return None
    return SpecGroup(title, rows)
