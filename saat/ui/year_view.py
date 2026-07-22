import zlib
from datetime import date

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from saat.storage import WatchRecord
from saat.ui import theme
from saat.ui.month_grid import month_grid_days
from saat.ui.theme import SIZE_XS, resolve_fonts

YEAR_CELL_SIZE = 9
YEAR_CELL_GAP = 2
YEAR_MONTH_LABEL_HEIGHT = 16


def slug_chip_saturation_value() -> tuple[int, int]:
    """Saturation/value for slug_color()'s chips in the active mode — like
    gilt/ruby, deepened in light mode so every hue clears 3:1 against its
    plate. The worst case (yellow, hue≈60) measured at 1.5:1 with a single
    fixed value shared across modes. See test_theme_contrast.py."""
    return (150, 110) if theme.current_mode() == theme.MODE_LIGHT else (150, 235)


def slug_color(slug: str) -> QColor:
    """One hue per watch, derived deterministically from its slug — SPEC.md
    §5.5's year view. crc32 (not hash()) because str hashing is randomised
    per process, and the same watch must land on the same hue every launch."""
    hue = zlib.crc32(slug.encode("utf-8")) % 360
    saturation, value = slug_chip_saturation_value()
    return QColor.fromHsv(hue, saturation, value)


class _YearMonthBlock(QWidget):
    """One compact month grid for year view: colour chips instead of photos.
    Purely a glance-level overview — no click/drag editing here, that's the
    month view's job."""

    clicked = Signal(int)  # 1-12

    def __init__(self, year: int, month: int, worn_index: dict[date, WatchRecord], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._year = year
        self._month = month
        self._days = month_grid_days(year, month)
        self._worn_index = worn_index
        self._label_font = QFont(resolve_fonts()["sans_condensed"])
        self._label_font.setPixelSize(SIZE_XS)

        rows = len(self._days) // 7
        width = 7 * YEAR_CELL_SIZE + 6 * YEAR_CELL_GAP
        height = YEAR_MONTH_LABEL_HEIGHT + rows * YEAR_CELL_SIZE + (rows - 1) * YEAR_CELL_GAP
        self.setFixedSize(width, height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit(self._month)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setFont(self._label_font)
        painter.setPen(QColor(theme.colors().text_muted))
        painter.drawText(QRect(0, 0, self.width(), YEAR_MONTH_LABEL_HEIGHT),
                          Qt.AlignmentFlag.AlignLeft, date(self._year, self._month, 1).strftime("%B"))

        painter.setPen(Qt.PenStyle.NoPen)
        for index, grid_day in enumerate(self._days):
            row, col = divmod(index, 7)
            x = col * (YEAR_CELL_SIZE + YEAR_CELL_GAP)
            y = YEAR_MONTH_LABEL_HEIGHT + row * (YEAR_CELL_SIZE + YEAR_CELL_GAP)

            if not grid_day.in_month:
                continue
            record = self._worn_index.get(grid_day.day)
            if record is not None:
                painter.setBrush(slug_color(record.slug))
            else:
                painter.setBrush(QColor(theme.colors().rule))
            painter.drawRect(QRect(x, y, YEAR_CELL_SIZE, YEAR_CELL_SIZE))

        painter.end()


class YearView(QWidget):
    """Twelve compact month grids for one year. See SPEC.md §5.5."""

    month_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setSpacing(24)

    def render(self, year: int, worn_index: dict[date, WatchRecord]) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for month in range(1, 13):
            row, col = divmod(month - 1, 4)
            block = _YearMonthBlock(year, month, worn_index)
            block.clicked.connect(self.month_clicked.emit)
            self._layout.addWidget(block, row, col)
