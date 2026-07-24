from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from saat.ui import theme
from saat.ui.theme import SIZE_XS, resolve_fonts

LABEL_HEIGHT = 20
TRACK_HEIGHT = 10
TICK_COUNT = 60  # a literal minute track: one tick per minute, five per second-mark


def draw_minute_track(painter: QPainter, width: int, track_y: int, track_height: int, tick_count: int = TICK_COUNT) -> None:
    """The tick+rule vocabulary itself (SPEC.md §6's minute track): a
    hairline rule at track_y with fine perpendicular ticks above it, longer
    every fifth, the way a dial's chapter ring is printed. Shared by
    MinuteTrackHeader (detail-page spec groups) and calendar_stats.py's
    inter-section divider -- the signature's only two locations. Caller
    owns the painter's pen/brush/antialiasing state before and after."""
    painter.setPen(QPen(QColor(theme.colors().rule), 1))
    painter.drawLine(0, track_y, width, track_y)

    safe_width = max(width, 1)
    for i in range(tick_count + 1):
        x = round(i / tick_count * safe_width)
        tick_height = track_height if i % 5 == 0 else track_height // 2
        painter.drawLine(x, track_y - tick_height, x, track_y)


class MinuteTrackHeader(QWidget):
    """A spec group header sitting on a hairline rule bearing fine ticks, longer
    every fifth, the way a dial's chapter ring is printed. SPEC.md §6 — the
    app's signature flourish; used for the detail page's spec groups, and
    (undecorated, as calendar_stats.py's _StatsSectionDivider) between the
    calendar Stats mode's sections."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title.upper()
        self._font = QFont(resolve_fonts()["sans_condensed"])
        self._font.setPixelSize(SIZE_XS)
        self._font.setWeight(QFont.Weight.DemiBold)
        # Matches the QSS letter-spacing on every other uppercase/overline
        # label (card-overline, detail-overline, spec-row-label) -- this one
        # is QPainter-drawn, so it can't pick that up from a stylesheet.
        self._font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
        self.setFixedHeight(LABEL_HEIGHT + TRACK_HEIGHT)

    def sizeHint(self) -> QSize:
        return QSize(200, LABEL_HEIGHT + TRACK_HEIGHT)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setFont(self._font)
        painter.setPen(QColor(theme.colors().text_muted))
        painter.drawText(0, 0, self.width(), LABEL_HEIGHT, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._title)

        draw_minute_track(painter, self.width(), LABEL_HEIGHT + TRACK_HEIGHT - 1, TRACK_HEIGHT)

        painter.end()
