from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from saat.ui import theme
from saat.ui.theme import SIZE_XS, resolve_fonts

LABEL_HEIGHT = 20
TRACK_HEIGHT = 10
TICK_COUNT = 60  # a literal minute track: one tick per minute, five per second-mark


class MinuteTrackHeader(QWidget):
    """A spec group header sitting on a hairline rule bearing fine ticks, longer
    every fifth, the way a dial's chapter ring is printed. SPEC.md §6 — the
    app's one signature flourish; used only for the detail page's spec groups."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title.upper()
        self._font = QFont(resolve_fonts()["sans_condensed"])
        self._font.setPixelSize(SIZE_XS)
        self._font.setWeight(QFont.Weight.DemiBold)
        self.setFixedHeight(LABEL_HEIGHT + TRACK_HEIGHT)

    def sizeHint(self) -> QSize:
        return QSize(200, LABEL_HEIGHT + TRACK_HEIGHT)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setFont(self._font)
        painter.setPen(QColor(theme.colors().text_muted))
        painter.drawText(0, 0, self.width(), LABEL_HEIGHT, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._title)

        rule_color = QColor(theme.colors().rule)
        track_y = LABEL_HEIGHT + TRACK_HEIGHT - 1
        painter.setPen(QPen(rule_color, 1))
        painter.drawLine(0, track_y, self.width(), track_y)

        width = max(self.width(), 1)
        for i in range(TICK_COUNT + 1):
            x = round(i / TICK_COUNT * width)
            tick_height = TRACK_HEIGHT if i % 5 == 0 else TRACK_HEIGHT // 2
            painter.drawLine(x, track_y - tick_height, x, track_y)

        painter.end()
