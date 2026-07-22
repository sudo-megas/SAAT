from datetime import date, timedelta

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from saat.storage import WatchRecord
from saat.ui.images import cropped_pixmap, first_image
from saat.ui.month_grid import GridDay, month_grid_days
from saat.ui.theme import GILT, PLATE, PLATE_HIGH, RULE, SIZE_SM, SIZE_XS, TEXT, TEXT_MUTED, resolve_fonts
from saat.ui.watch_picker import WatchPicker
from saat.ui.year_view import YearView
from saat.wear import build_worn_index

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SCRIM_HEIGHT = 22
MIN_CELL_SIZE = 72


class _DayCell(QFrame):
    """One calendar day: a watch's primary photo square-cropped and filling
    the cell with the day number over a scrim, or just a muted day number
    when empty. Today carries a gilt hairline border. See SPEC.md §5.5."""

    def __init__(self, grid_day: GridDay, record: WatchRecord | None, is_today: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.grid_day = grid_day
        self.record = record
        self.is_today = is_today
        self.highlighted = False
        self.setMinimumSize(MIN_CELL_SIZE, MIN_CELL_SIZE)

        self._pixmap = None
        if record is not None:
            path = first_image(record)
            if path is not None:
                self._pixmap = cropped_pixmap(path, MIN_CELL_SIZE * 2, MIN_CELL_SIZE * 2)

        self._number_font = QFont(resolve_fonts()["sans_condensed"])
        self._number_font.setPixelSize(SIZE_SM)
        self._number_font.setWeight(QFont.Weight.DemiBold)
        self._info_font = QFont(resolve_fonts()["sans_condensed"])
        self._info_font.setPixelSize(SIZE_XS)

    def set_highlighted(self, value: bool) -> None:
        if value != self.highlighted:
            self.highlighted = value
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        assigned_without_photo = self.grid_day.in_month and self.record is not None and self._pixmap is None

        if not self.grid_day.in_month:
            painter.fillRect(rect, QColor(PLATE))
        elif self._pixmap is not None:
            painter.drawPixmap(rect, self._pixmap, QRect(0, 0, self._pixmap.width(), self._pixmap.height()))
            painter.fillRect(QRect(0, 0, rect.width(), SCRIM_HEIGHT), QColor(0, 0, 0, 130))
        elif assigned_without_photo:
            painter.fillRect(rect, QColor(PLATE_HIGH))  # a watch with no photo yet — SPEC.md §5.2's card placeholder, calendar-sized
        else:
            painter.fillRect(rect, QColor(PLATE))  # truly empty — nothing recorded

        painter.setFont(self._number_font)
        painter.setPen(QColor(TEXT) if self.record is not None else QColor(TEXT_MUTED))
        painter.drawText(QRect(6, 4, rect.width() - 12, SCRIM_HEIGHT), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                          str(self.grid_day.day.day))

        if assigned_without_photo:
            painter.setFont(self._info_font)
            painter.setPen(QColor(TEXT_MUTED))
            info_rect = QRect(6, SCRIM_HEIGHT, rect.width() - 12, rect.height() - SCRIM_HEIGHT - 4)
            painter.drawText(info_rect, Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, self.record.watch.brand)

        if self.highlighted:
            painter.fillRect(rect, QColor(201, 162, 39, 60))

        if self.is_today:
            painter.setPen(QPen(QColor(GILT), 2))
            painter.drawRect(rect.adjusted(1, 1, -2, -2))
        else:
            painter.setPen(QPen(QColor(RULE), 1))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))

        painter.end()


class _MonthGrid(QWidget):
    """Renders one month's cells and turns mouse interaction into a date
    range: a plain click is a range of one day, a drag spans anchor to the
    cell currently under the cursor. Tracked here (not per-cell) so the drag
    highlight can be driven from one mouse-move handler via childAt()."""

    range_chosen = Signal(list)  # list[date], in chronological order

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setSpacing(2)
        self._cells: dict[date, _DayCell] = {}
        self._drag_anchor: date | None = None

    def render(self, year: int, month: int, worn_index: dict[date, WatchRecord]) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cells = {}

        today = date.today()
        days = month_grid_days(year, month)
        for i, label in enumerate(WEEKDAY_LABELS):
            heading = QLabel(label)
            heading.setProperty("class", "spec-row-label")
            heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._layout.addWidget(heading, 0, i)

        for index, grid_day in enumerate(days):
            row, col = divmod(index, 7)
            cell = _DayCell(grid_day, worn_index.get(grid_day.day), grid_day.day == today)
            self._layout.addWidget(cell, row + 1, col)
            self._cells[grid_day.day] = cell

        for col in range(7):
            self._layout.setColumnStretch(col, 1)
        for row in range(1, (len(days) // 7) + 1):
            self._layout.setRowStretch(row, 1)

    def _day_at(self, pos) -> date | None:
        child = self.childAt(pos)
        if isinstance(child, _DayCell) and child.grid_day.in_month:
            return child.grid_day.day
        return None

    def mousePressEvent(self, event) -> None:
        day = self._day_at(event.pos())
        if day is not None:
            self._drag_anchor = day
            self._apply_highlight(day, day)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_anchor is None:
            return
        day = self._day_at(event.pos())
        if day is not None:
            self._apply_highlight(self._drag_anchor, day)

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_anchor is None:
            return
        day = self._day_at(event.pos()) or self._drag_anchor
        start, end = sorted((self._drag_anchor, day))
        self._drag_anchor = None
        self._clear_highlight()
        span = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        self.range_chosen.emit(span)

    def _apply_highlight(self, anchor: date, current: date) -> None:
        start, end = sorted((anchor, current))
        for day, cell in self._cells.items():
            cell.set_highlighted(start <= day <= end)

    def _clear_highlight(self) -> None:
        for cell in self._cells.values():
            cell.set_highlighted(False)


class CalendarView(QWidget):
    """Month grid with drag-range assignment. See SPEC.md §5.5. Year view and
    the detail-page wear strip reuse month_grid_days()/build_worn_index()."""

    assign_requested = Signal(list, object)  # list[date], WatchRecord
    clear_requested = Signal(list)  # list[date]

    def __init__(self, records: list[WatchRecord], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        today = date.today()
        self._year = today.year
        self._month = today.month
        self._records = records
        self._worn_index = build_worn_index(records)
        self._year_view_active = False

        self._month_label = QLabel()
        self._month_label.setProperty("class", "detail-title")
        prev_button = QPushButton("‹")
        prev_button.clicked.connect(self._go_previous)
        next_button = QPushButton("›")
        next_button.clicked.connect(self._go_next)
        self._year_view_button = QPushButton("Year view")
        self._year_view_button.setCheckable(True)
        self._year_view_button.clicked.connect(self._toggle_year_view)

        header = QHBoxLayout()
        header.addWidget(prev_button)
        header.addWidget(self._month_label)
        header.addWidget(next_button)
        header.addStretch()
        header.addWidget(self._year_view_button)

        self._grid = _MonthGrid()
        self._grid.range_chosen.connect(self._on_range_chosen)

        self._footer_label = QLabel()
        self._footer_label.setProperty("muted", True)

        month_content = QWidget()
        month_layout = QVBoxLayout(month_content)
        month_layout.setContentsMargins(0, 0, 0, 0)
        month_layout.setSpacing(16)
        month_layout.addWidget(self._grid, stretch=1)
        month_layout.addWidget(self._footer_label)

        self._year_view = YearView()
        self._year_view.month_clicked.connect(self._jump_to_month)

        self._content_stack = QStackedWidget()
        self._content_stack.addWidget(month_content)
        self._content_stack.addWidget(self._year_view)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addLayout(header)
        layout.addWidget(self._content_stack, stretch=1)

        self._render()

    def set_records(self, records: list[WatchRecord]) -> None:
        """Refreshes wear data without touching which month is on screen —
        the whole point of drag-range backfill is not losing your place."""
        self._records = records
        self._worn_index = build_worn_index(records)
        self._render()

    def _go_previous(self) -> None:
        if self._year_view_active:
            self._year -= 1
        else:
            self._month -= 1
            if self._month == 0:
                self._month = 12
                self._year -= 1
        self._render()

    def _go_next(self) -> None:
        if self._year_view_active:
            self._year += 1
        else:
            self._month += 1
            if self._month == 13:
                self._month = 1
                self._year += 1
        self._render()

    def _toggle_year_view(self) -> None:
        self._year_view_active = self._year_view_button.isChecked()
        self._content_stack.setCurrentWidget(self._year_view if self._year_view_active else self._content_stack.widget(0))
        self._render()

    def _jump_to_month(self, month: int) -> None:
        self._month = month
        self._year_view_active = False
        self._year_view_button.setChecked(False)
        self._content_stack.setCurrentIndex(0)
        self._render()

    def _render(self) -> None:
        if self._year_view_active:
            self._month_label.setText(str(self._year))
            self._year_view.render(self._year, self._worn_index)
        else:
            self._month_label.setText(date(self._year, self._month, 1).strftime("%B %Y"))
            self._grid.render(self._year, self._month, self._worn_index)
            self._footer_label.setText(self._footer_text())

    def _footer_text(self) -> str:
        in_month = {d: r for d, r in self._worn_index.items() if d.year == self._year and d.month == self._month}
        days_recorded = len(in_month)
        distinct_worn = {r.slug for r in in_month.values()}
        valid_count = len([r for r in self._records if r.watch is not None])
        not_worn = max(valid_count - len(distinct_worn), 0)
        return f"{days_recorded} days recorded  ·  {len(distinct_worn)} watches worn  ·  {not_worn} not worn this month"

    def _on_range_chosen(self, dates: list[date]) -> None:
        current = self._worn_index.get(dates[0]) if len(dates) == 1 else None
        picker = WatchPicker(self._records, current=current, parent=self)
        if picker.exec() != QDialog.DialogCode.Accepted:
            return
        if picker.was_cleared():
            self.clear_requested.emit(dates)
        else:
            self.assign_requested.emit(dates, picker.chosen_record())
