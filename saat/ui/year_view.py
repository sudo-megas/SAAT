import zlib
from datetime import date

from PySide6.QtCore import QLocale, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPaintEvent, QPainter
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from saat.storage import WatchRecord
from saat.ui import theme
from saat.ui.month_grid import month_grid_days
from saat.ui.theme import SIZE_XS, resolve_fonts

YEAR_CELL_SIZE = 9
YEAR_CELL_GAP = 2
YEAR_MONTH_LABEL_HEIGHT = 16
COLOR_SWATCH_HEIGHT = 4


def slug_chip_saturation_value() -> tuple[int, int]:
    """Saturation/value for slug_color()'s chips against the active palette —
    like gilt/ruby, deepened on a dark plate so every hue clears 3:1. Keyed
    on the active palette's is_dark flag, not a specific palette id: the
    constraint is one-sided per class (a dark palette's chip must beat its
    own plate; a lighter chip always wins there), so one conservative pair
    per class covers every preset in that class rather than needing a
    per-palette override. The dark-bucket value (100, 255) is retuned from
    the original two-palette system's (150, 235), which measured as low as
    1.99:1 against real dark presets (Catppuccin Frappé's surface0) — the
    retuned pair clears 3:1 against every dark preset with real margin
    (worst case 3.84:1, Nord). See test_theme_contrast.py."""
    return (150, 110) if not theme.active_palette().is_dark else (100, 255)


def slug_color(slug: str) -> QColor:
    """One hue per watch, derived deterministically from its slug — SPEC.md
    §5.5's year view. crc32 (not hash()) because str hashing is randomised
    per process, and the same watch must land on the same hue every launch."""
    hue = zlib.crc32(slug.encode("utf-8")) % 360
    saturation, value = slug_chip_saturation_value()
    return QColor.fromHsv(hue, saturation, value)


class SlugColorBar(QWidget):
    """A thin per-watch colour bar, reusing slug_color() — links whatever it
    sits under to the same hue used everywhere else this watch (or its
    comparison against others) is shown: compare-view column headers, and
    now the identity accent on a watch's own detail page (SPEC.md §6:
    identity, never state — never on grid cards or hover, which milestone
    16 already owns)."""

    def __init__(self, slug: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._slug = slug
        self.setFixedHeight(COLOR_SWATCH_HEIGHT)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(slug_color(self._slug))
        painter.drawRect(self.rect())
        painter.end()


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
        # Bare QLocale(), never QLocale.system() -- see i18n.py's
        # install_language(). Read fresh on every paint (not cached), so a
        # language change needs no explicit retranslation here: the next
        # repaint (render() rebuilds every block from scratch) just picks
        # it up, unlike strftime("%B"), which reads the process C locale
        # and is always English regardless of the active UI language.
        painter.drawText(QRect(0, 0, self.width(), YEAR_MONTH_LABEL_HEIGHT),
                          Qt.AlignmentFlag.AlignLeft, QLocale().standaloneMonthName(self._month))

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
