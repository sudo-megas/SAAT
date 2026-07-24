from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from saat.storage import WatchRecord
from saat.ui import theme
from saat.ui.compare import (
    AccuracyEntry,
    accuracy_axis_bounds,
    build_accuracy_entries,
    should_show_accuracy,
)
from saat.ui.formatting import fmt_accuracy
from saat.ui.theme import SIZE_XS, resolve_fonts
from saat.ui.year_view import slug_color

AXIS_HEIGHT = 14
SPAN_HEIGHT = 6
ZERO_LINE_WIDTH = 2
MIN_SPAN_PX = 2  # a quartz movement's span must stay a *visible* hairline, not round away to nothing


def _section_heading(text: str) -> QLabel:
    """See case_silhouette.py's identical helper — not a spec group, so
    deliberately not a MinuteTrackHeader. Kept local rather than shared
    since it's a single QLabel construction, not worth a cross-module
    import for."""
    heading = QLabel(text.upper())
    heading.setProperty("class", "spec-row-label")
    return heading


class _AccuracyAxis(QWidget):
    """One watch's accuracy span on the shared sec/day axis: a filled bar
    from accuracy_min to accuracy_max in the watch's slug colour, and a
    zero-reference line at the same x on every row (axis_min/axis_max are
    shared across the whole section — see build_accuracy_section), so it
    reads as one implied vertical line down the list. SPEC.md §5.4: no
    compression, clipping or log-scaling — a quartz movement's span is
    *meant* to look like a near-invisible hairline next to a mechanical's
    wide one."""

    def __init__(self, entry: AccuracyEntry, axis_min: float, axis_max: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry = entry
        self._axis_min = axis_min
        self._axis_max = axis_max
        self.setFixedHeight(AXIS_HEIGHT)
        self.setMinimumWidth(160)

    def _x_for(self, value: float, width: int) -> float:
        span = self._axis_max - self._axis_min
        if span <= 0:
            return 0.0
        return (value - self._axis_min) / span * width

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(theme.colors().plate))
        width = self.width()
        mid_y = self.height() // 2

        left_x = round(self._x_for(self._entry.min_sec_per_day, width))
        right_x = round(self._x_for(self._entry.max_sec_per_day, width))
        if right_x - left_x < MIN_SPAN_PX:
            right_x = left_x + MIN_SPAN_PX

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(slug_color(self._entry.record.slug))
        painter.drawRect(QRect(left_x, mid_y - SPAN_HEIGHT // 2, right_x - left_x, SPAN_HEIGHT))

        # Drawn last so it's never obscured by a span that happens to cross it.
        zero_x = round(self._x_for(0.0, width))
        painter.setPen(QPen(QColor(theme.colors().text), ZERO_LINE_WIDTH))
        painter.drawLine(zero_x, 0, zero_x, self.height())

        painter.end()


class _AccuracyRow(QWidget):
    """Watch name and its original accuracy reading (unconverted — SPEC.md
    §5.4) above the shared-scale axis bar."""

    def __init__(self, entry: AccuracyEntry, axis_min: float, axis_max: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        name = QLabel(f"{entry.record.watch.brand} {entry.record.watch.model}")
        name.setProperty("class", "spec-row-value")

        mono_font = QFont(resolve_fonts()["mono"])
        mono_font.setPixelSize(SIZE_XS)
        original = QLabel(fmt_accuracy((entry.original_min, entry.original_max, entry.original_unit)))
        original.setFont(mono_font)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addWidget(name)
        top_row.addStretch()
        top_row.addWidget(original)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)
        layout.addLayout(top_row)
        layout.addWidget(_AccuracyAxis(entry, axis_min, axis_max))


def build_accuracy_section(records: list[WatchRecord]) -> QWidget | None:
    """The whole Commit B visual: one shared-axis span per watch with
    accuracy data. None hides it entirely — SPEC.md §5.4: 'Hide the
    section when fewer than 2 selected watches have accuracy data.'"""
    if not should_show_accuracy(records):
        return None

    entries, _ = build_accuracy_entries(records)
    axis_min, axis_max = accuracy_axis_bounds(entries)

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.addWidget(_section_heading("Accuracy Range"))
    for entry in entries:
        layout.addWidget(_AccuracyRow(entry, axis_min, axis_max))
    return container
