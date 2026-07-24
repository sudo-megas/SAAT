from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPaintEvent
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from saat.storage import WatchRecord
from saat.ui import theme
from saat.ui.compare import DimensionBarRow, DimensionBarValue, build_dimension_bar_rows
from saat.ui.theme import SIZE_XS, resolve_fonts
from saat.ui.year_view import slug_color

CELL_HEIGHT = 20
BAR_HEIGHT = 8
TEXT_GAP = 8
MIN_BAR_PX = 2  # a real, positive value must stay visible, not round away to indistinguishable-from-missing


def _mono_font() -> QFont:
    font = QFont(resolve_fonts()["mono"])
    font.setPixelSize(SIZE_XS)
    return font


def _section_heading(text: str) -> QLabel:
    """See case_silhouette.py's identical helper — not a spec group, so
    deliberately not a MinuteTrackHeader."""
    heading = QLabel(text.upper())
    heading.setProperty("class", "spec-row-label")
    return heading


class _DimensionBarCell(QWidget):
    """One watch's bar in one dimension row. reserved_text_width is fixed
    per ROW (the widest value text among that row's watches), so every
    cell's bar track is the same pixel width — SPEC.md §5.4: 'Scale is
    shared WITHIN a row.' A missing value draws no bar at all, just its
    em-dash, never a zero-length bar."""

    def __init__(
        self, value: DimensionBarValue, max_magnitude: float, reserved_text_width: float, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._value = value
        self._max_magnitude = max_magnitude
        self._reserved = reserved_text_width
        self.setFixedHeight(CELL_HEIGHT)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(theme.colors().plate))
        palette = theme.colors()
        track_width = max(self.width() - self._reserved - TEXT_GAP, 0)

        if self._value.magnitude is not None and self._max_magnitude > 0:
            fill_width = round(self._value.magnitude / self._max_magnitude * track_width)
            if self._value.magnitude > 0 and fill_width < MIN_BAR_PX:
                fill_width = MIN_BAR_PX
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(slug_color(self._value.record.slug))
            painter.drawRect(QRect(0, (self.height() - BAR_HEIGHT) // 2, fill_width, BAR_HEIGHT))

        painter.setFont(_mono_font())
        painter.setPen(QColor(palette.text if self._value.magnitude is not None else palette.text_muted))
        text_rect = QRect(round(track_width) + TEXT_GAP, 0, self.width(), self.height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._value.text)

        painter.end()


def _reserved_text_width(row: DimensionBarRow, metrics: QFontMetrics) -> float:
    return max((metrics.horizontalAdvance(v.text) for v in row.values), default=0)


def build_dimension_bars_section(records: list[WatchRecord], is_wishlist: bool = False) -> QWidget | None:
    """The whole Commit C visual: one row per qualifying numeric
    attribute, one bar per watch, in the same column order as the compare
    table beneath. None hides it entirely when no attribute qualifies —
    SPEC.md §5.4: 'Rows hide themselves when fewer than 2 watches have
    the value,' applied here at the whole-section level once every row
    has already failed that test."""
    rows = build_dimension_bar_rows(records, is_wishlist)
    if not rows:
        return None

    container = QWidget()
    outer = QVBoxLayout(container)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(8)
    outer.addWidget(_section_heading("Dimensions"))

    grid_widget = QWidget()
    grid = QGridLayout(grid_widget)
    grid.setHorizontalSpacing(24)
    grid.setVerticalSpacing(6)
    num_columns = len(records) + 1
    for col in range(1, num_columns):
        grid.setColumnStretch(col, 1)

    metrics = QFontMetrics(_mono_font())
    for row_index, row in enumerate(rows):
        label = QLabel(row.label)
        label.setProperty("class", "spec-row-label")
        grid.addWidget(label, row_index, 0, Qt.AlignmentFlag.AlignVCenter)

        reserved = _reserved_text_width(row, metrics)
        for col, value in enumerate(row.values, start=1):
            grid.addWidget(_DimensionBarCell(value, row.max_magnitude, reserved), row_index, col)

    outer.addWidget(grid_widget)
    return container
