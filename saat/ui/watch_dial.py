import math
from datetime import datetime, time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from saat.ui import theme

# A compact wristwatch drawing, not a wall clock -- lug blocks top and bottom
# are what make it read as "watch" rather than "generic clock face".
DIAL_DIAMETER = 160
LUG_WIDTH = 56
LUG_HEIGHT = 16
LUG_GAP = 4
MARGIN = 10
TICK_COUNT = 60  # one per minute, five per hour-mark -- same vocabulary as minute_track.py, curved
PINION_RADIUS = 4
HOUR_HAND_FRACTION = 0.5
MINUTE_HAND_FRACTION = 0.78
MIN_TIMER_INTERVAL_MS = 50  # floor so a call landing exactly on a boundary can't re-arm near 0ms and tight-loop

WIDGET_WIDTH = DIAL_DIAMETER + 2 * MARGIN
WIDGET_HEIGHT = LUG_HEIGHT + LUG_GAP + DIAL_DIAMETER + LUG_GAP + LUG_HEIGHT + 2 * MARGIN


def hand_angles(now: time) -> tuple[float, float]:
    """(hour_angle_deg, minute_angle_deg), 0deg = 12 o'clock, clockwise. Pure
    and Qt-free so it's testable against fixed times without an event loop."""
    minute_angle = now.minute * 6.0  # 360 / 60
    hour_angle = (now.hour % 12) * 30.0 + now.minute * 0.5  # 360 / 12, plus drift within the hour
    return hour_angle, minute_angle


def ms_until_next_minute(now: datetime) -> int:
    """Milliseconds until the next minute boundary -- how the dial re-arms its
    single-shot timer so the minute hand moves exactly when the minute
    changes, rather than drifting from a naive fixed 60000ms interval from
    launch."""
    seconds_into_minute = now.second + now.microsecond / 1_000_000
    remaining_ms = (60.0 - seconds_into_minute) * 1000
    return max(round(remaining_ms), MIN_TIMER_INTERVAL_MS)


def _direction(angle_deg: float) -> QPointF:
    theta = math.radians(angle_deg)
    return QPointF(math.sin(theta), -math.cos(theta))


class WatchDialWidget(QWidget):
    """The empty state's centrepiece: a QPainter watch dial showing the real
    current time. Hour and minute hands only -- SPEC.md §6: a sweeping second
    hand would mean repainting forever on an idle screen. The gilt centre
    pinion is the composition's only gilt; everything else is hairline `rule`
    and `text`. Updates on a single-shot QTimer re-armed to the next minute
    boundary each time it fires -- started in showEvent, stopped in
    hideEvent, so it never runs while the empty state isn't the visible
    stack page (confirmed empirically: QStackedWidget.removeWidget() fires a
    real hideEvent, both when this is the only page and when others remain)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(WIDGET_WIDTH, WIDGET_HEIGHT)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_tick)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._arm_timer()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()

    def _arm_timer(self) -> None:
        self._timer.start(ms_until_next_minute(datetime.now()))

    def _on_tick(self) -> None:
        self.update()
        self._arm_timer()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colors = theme.colors()
        painter.fillRect(self.rect(), QColor(colors.plate))

        cx = self.width() / 2
        cy = MARGIN + LUG_HEIGHT + LUG_GAP + DIAL_DIAMETER / 2
        radius = DIAL_DIAMETER / 2
        rule = QColor(colors.rule)

        self._draw_lug_block(painter, cx, MARGIN, rule)
        self._draw_lug_block(painter, cx, cy + radius + LUG_GAP, rule)
        self._draw_chapter_ring(painter, cx, cy, radius, rule)

        hour_angle, minute_angle = hand_angles(datetime.now().time())
        text_color = QColor(colors.text)
        self._draw_hand(painter, cx, cy, hour_angle, radius * HOUR_HAND_FRACTION, text_color, width=3)
        self._draw_hand(painter, cx, cy, minute_angle, radius * MINUTE_HAND_FRACTION, text_color, width=2)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors.gilt))
        painter.drawEllipse(QPointF(cx, cy), PINION_RADIUS, PINION_RADIUS)

        painter.end()

    def _draw_lug_block(self, painter: QPainter, cx: float, top: float, rule: QColor) -> None:
        painter.setPen(QPen(rule, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(cx - LUG_WIDTH / 2, top, LUG_WIDTH, LUG_HEIGHT))

    def _draw_chapter_ring(self, painter: QPainter, cx: float, cy: float, radius: float, rule: QColor) -> None:
        painter.setPen(QPen(rule, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        centre = QPointF(cx, cy)
        painter.drawEllipse(centre, radius, radius)

        for i in range(TICK_COUNT):
            direction = _direction(i * 360 / TICK_COUNT)
            tick_len = 8 if i % 5 == 0 else 4
            painter.drawLine(centre + direction * radius, centre + direction * (radius - tick_len))

    def _draw_hand(self, painter: QPainter, cx: float, cy: float, angle_deg: float, length: float, color: QColor, width: int) -> None:
        centre = QPointF(cx, cy)
        pen = QPen(color, width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(centre, centre + _direction(angle_deg) * length)
