from datetime import date, timedelta

from PySide6.QtCore import QDate, QEvent, QLocale, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from saat.config import Config
from saat.selection import MODE_WEIGHTED, pick_week
from saat.storage import WatchRecord
from saat.ui.calendar_stats import StatsView
from saat.ui import icons
from saat.ui.images import cropped_pixmap, first_image
from saat.ui.month_grid import GridDay, month_grid_days, week_grid_days
from saat.ui import motion, theme
from saat.ui.theme import SIZE_SM, SIZE_XS, resolve_fonts
from saat.ui.watch_picker import WatchPicker
from saat.ui.year_view import YearView
from saat.wear import build_worn_index

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
        self.focused = False
        self.dimmed = False
        self.proposed = False
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

    def set_focused(self, value: bool) -> None:
        if value != self.focused:
            self.focused = value
            self.update()

    def set_dimmed(self, value: bool) -> None:
        if value != self.dimmed:
            self.dimmed = value
            self.update()

    def set_proposed(self, value: bool) -> None:
        """Milestone 20's week planner: `record` is the proposed pick (not
        yet written anywhere), so paintEvent renders it visibly provisional
        — a dashed ring plus a lighter photo — instead of looking like
        already-logged history (SPEC.md milestone 20 step 14)."""
        if value != self.proposed:
            self.proposed = value
            self.update()

    def _number_color(self, palette: "theme.Palette") -> QColor:
        if self._pixmap is not None:
            return QColor("#E8E4DC")  # fixed warm off-white: sits on the fixed black scrim over the photo, not a themed surface
        if self.record is not None:
            return QColor(palette.text)
        return QColor(palette.text_muted)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        assigned_without_photo = self.grid_day.in_month and self.record is not None and self._pixmap is None

        palette = theme.colors()
        if not self.grid_day.in_month:
            painter.fillRect(rect, QColor(palette.plate))
        elif self._pixmap is not None:
            # Proposed: a lighter photo, so a suggestion never reads as
            # already-worn history at a glance (SPEC.md milestone 20 step 14).
            painter.setOpacity(0.55 if self.proposed else 1.0)
            painter.drawPixmap(rect, self._pixmap, QRect(0, 0, self._pixmap.width(), self._pixmap.height()))
            painter.setOpacity(1.0)
            painter.fillRect(QRect(0, 0, rect.width(), SCRIM_HEIGHT), QColor(0, 0, 0, 130))  # fixed scrim over a photo, not a theme color
        elif assigned_without_photo:
            painter.fillRect(rect, QColor(palette.plate_high))  # a watch with no photo yet — SPEC.md §5.2's card placeholder, calendar-sized
        else:
            painter.fillRect(rect, QColor(palette.plate))  # truly empty — nothing recorded

        if self.dimmed:
            # Rotation click-through emphasis (SPEC.md §5.5): washes this
            # cell's photo/colour content toward the plate so the emphasised
            # watch's days read as the only "live" ones. Drawn before the day
            # number so it stays fully legible — dimming is about the
            # content, not the navigation — and before the drag-highlight/
            # today/focus strokes below so those never look muted.
            dim = QColor(palette.plate)
            dim.setAlpha(170)
            painter.fillRect(rect, dim)

        painter.setFont(self._number_font)
        painter.setPen(self._number_color(palette))
        painter.drawText(QRect(6, 4, rect.width() - 12, SCRIM_HEIGHT), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                          str(self.grid_day.day.day))

        if assigned_without_photo:
            painter.setFont(self._info_font)
            painter.setPen(QColor(palette.text_muted))
            info_rect = QRect(6, SCRIM_HEIGHT, rect.width() - 12, rect.height() - SCRIM_HEIGHT - 4)
            painter.drawText(info_rect, Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, self.record.watch.brand)

        if self.highlighted:
            highlight = QColor(palette.gilt)
            highlight.setAlpha(60)
            painter.fillRect(rect, highlight)

        if self.is_today:
            painter.setPen(QPen(QColor(palette.gilt), 2))
            painter.drawRect(rect.adjusted(1, 1, -2, -2))
        else:
            painter.setPen(QPen(QColor(palette.rule), 1))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))

        if self.focused:
            # Drawn at the cell's outer edge — distinct from (and layers
            # cleanly with) today's inset ring rather than competing for the
            # same pixels when a cell is both today and keyboard-focused.
            painter.setPen(QPen(QColor(palette.gilt), 2))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))

        if self.proposed:
            # Milestone 20's week planner: drawn last, at the outer edge, so
            # a proposed day is unmistakable even when it's also today (whose
            # solid gilt ring sits at a different, inset rect and so stays
            # independently visible) — a dashed stroke, never solid, is what
            # keeps this from ever reading as logged history.
            pen = QPen(QColor(palette.gilt), 2)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect.adjusted(0, 0, -1, -1))

        painter.end()


class _MonthGrid(QWidget):
    """Renders one month's cells and turns mouse interaction into a date
    range: a plain click is a range of one day, a drag spans anchor to the
    cell currently under the cursor. Tracked here (not per-cell) so the drag
    highlight can be driven from one mouse-move handler via childAt()."""

    range_chosen = Signal(list)  # list[date], in chronological order

    _ARROW_DELTAS = {
        Qt.Key.Key_Left: timedelta(days=-1),
        Qt.Key.Key_Right: timedelta(days=1),
        Qt.Key.Key_Up: timedelta(days=-7),
        Qt.Key.Key_Down: timedelta(days=7),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._layout = QGridLayout(self)
        self._layout.setSpacing(2)
        self._cells: dict[date, _DayCell] = {}
        self._drag_anchor: date | None = None
        self._focused_day: date | None = None

    def render(
        self,
        days: list[GridDay],
        record_by_day: dict[date, WatchRecord],
        emphasized_slug: str | None = None,
    ) -> None:
        """`days` is whatever shape the caller wants — a whole padded month
        (month_grid_days()) or a bare week (week_grid_days(), milestone 20's
        Week mode). This widget has no opinion on which; its interaction
        logic (click, drag-range, arrow keys, focus) is generic over
        dict[date, _DayCell] and just lays out exactly len(days) cells,
        seven per row — for a 7-day week that's one row, for a change of
        zero lines here."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cells = {}

        today = date.today()
        locale = QLocale()
        for i in range(7):
            # QLocale.dayName() is 1=Monday..7=Sunday, matching this grid's
            # Monday-first column order (SPEC.md §5.5).
            heading = QLabel(locale.dayName(i + 1, QLocale.FormatType.ShortFormat))
            heading.setProperty("class", "spec-row-label")
            heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._layout.addWidget(heading, 0, i)

        for index, grid_day in enumerate(days):
            row, col = divmod(index, 7)
            cell = _DayCell(grid_day, record_by_day.get(grid_day.day), grid_day.day == today)
            self._layout.addWidget(cell, row + 1, col)
            self._cells[grid_day.day] = cell

        for col in range(7):
            self._layout.setColumnStretch(col, 1)
        for row in range(1, (len(days) // 7) + 1):
            self._layout.setRowStretch(row, 1)

        # Cells are rebuilt every render() (month navigation, a wear edit,
        # switching out of year view) — default the keyboard cursor to today
        # when it's on screen, else the 1st, rather than trying to carry a
        # date across a grid that no longer has it.
        if today in self._cells and self._cells[today].grid_day.in_month:
            self._focused_day = today
        else:
            in_month_days = sorted(d for d, cell in self._cells.items() if cell.grid_day.in_month)
            self._focused_day = in_month_days[0] if in_month_days else None
        self._apply_focus()
        self.apply_emphasis(emphasized_slug)

    def apply_emphasis(self, emphasized_slug: str | None) -> None:
        """Click-through from Stats mode's Rotation list (SPEC.md §5.5): the
        emphasised watch's cells render at full strength, everything else
        dims — including cells with no watch at all. A post-render pass, the
        same shape as _apply_focus(), so it survives cell rebuilds without
        CalendarView having to thread it through every render() call site."""
        for cell in self._cells.values():
            cell.set_dimmed(emphasized_slug is not None and (cell.record is None or cell.record.slug != emphasized_slug))

    def apply_proposed(self, proposed_days: frozenset[date]) -> None:
        """Milestone 20's week planner: marks which currently-rendered days
        carry a not-yet-written proposal. A post-render pass, the same
        shape as apply_emphasis() — only the Week mode ever calls this."""
        for day, cell in self._cells.items():
            cell.set_proposed(day in proposed_days)

    def _day_at(self, pos) -> date | None:
        child = self.childAt(pos)
        if isinstance(child, _DayCell) and child.grid_day.in_month:
            return child.grid_day.day
        return None

    def _apply_focus(self) -> None:
        has_focus = self.hasFocus()
        for day, cell in self._cells.items():
            cell.set_focused(has_focus and day == self._focused_day)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self._apply_focus()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self._apply_focus()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in self._ARROW_DELTAS and self._focused_day is not None:
            candidate = self._focused_day + self._ARROW_DELTAS[key]
            cell = self._cells.get(candidate)
            if cell is not None and cell.grid_day.in_month:
                self._focused_day = candidate
                self._apply_focus()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._focused_day is not None:
            self.range_chosen.emit([self._focused_day])
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        day = self._day_at(event.pos())
        if day is not None:
            self._drag_anchor = day
            self._focused_day = day
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self._apply_highlight(day, day)
            self._apply_focus()

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


_MODE_MONTH = "month"
_MODE_YEAR = "year"
_MODE_STATS = "stats"
_MODE_WEEK = "week"


class CalendarView(QWidget):
    """Month, Year, Stats and Week modes over one collection's wear
    history. See SPEC.md §5.5. Year view and the detail-page wear strip
    reuse month_grid_days()/build_worn_index(). `config` is optional and
    read-only here — only Week mode's roll uses it (to match the today
    picker's persisted Random/Weighted preference, saat.config.Config.
    picker_mode()); every other mode ignores it entirely, so the many
    existing call sites that construct this without a config keep working
    unchanged."""

    assign_requested = Signal(list, object)  # list[date], WatchRecord
    clear_requested = Signal(list)  # list[date]

    def __init__(
        self, records: list[WatchRecord], config: Config | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        today = date.today()
        self._year = today.year
        self._month = today.month
        self._week_anchor = today
        self._config = config
        self._records = records
        self._worn_index = build_worn_index(records)
        self._mode = _MODE_MONTH
        self._emphasized_slug: str | None = None
        self._week_proposal: dict[date, WatchRecord] | None = None

        self._prev_button = QPushButton()
        self._prev_button.setToolTip(self.tr("Previous month"))
        icons.set_icon(self._prev_button, "prev-month")
        self._prev_button.clicked.connect(self._go_previous)
        self._next_button = QPushButton()
        self._next_button.setToolTip(self.tr("Next month"))
        icons.set_icon(self._next_button, "next-month")
        self._next_button.clicked.connect(self._go_next)
        self._today_button = QPushButton(self.tr("Today"))
        icons.set_icon(self._today_button, "today")
        self._today_button.clicked.connect(self._go_today)

        self._month_combo = QComboBox()
        # Filled by _retranslate() below (bare QLocale(), never
        # QLocale.system() -- see i18n.py's install_language()) rather than
        # calendar.month_name, which reads the process C locale and is
        # always English since nothing calls locale.setlocale(). setItemText()
        # in _retranslate() preserves currentIndex across a language change,
        # same as retranslate_combo() (form_fields.py).
        self._month_combo.addItems([""] * 12)
        self._month_combo.currentIndexChanged.connect(self._on_month_combo_changed)
        self._year_spinbox = QSpinBox()
        self._year_spinbox.setRange(1900, 2100)
        self._year_spinbox.valueChanged.connect(self._on_year_spinbox_changed)
        self._week_range_label = QLabel()
        self._week_range_label.setProperty("class", "spec-row-label")

        self._month_button = QPushButton(self.tr("Month"))
        self._week_button = QPushButton(self.tr("Week"))
        self._year_button = QPushButton(self.tr("Year"))
        self._stats_button = QPushButton(self.tr("Stats"))
        for button, mode, icon_name in (
            (self._month_button, _MODE_MONTH, "calendar"),
            (self._week_button, _MODE_WEEK, "week"),
            (self._year_button, _MODE_YEAR, "year"),
            (self._stats_button, _MODE_STATS, "stats"),
        ):
            button.setCheckable(True)
            icons.set_checkable_icon(button, icon_name)
            button.clicked.connect(lambda _checked, m=mode: self._set_mode(m))

        header = QHBoxLayout()
        header.addWidget(self._prev_button)
        header.addWidget(self._month_combo)
        header.addWidget(self._year_spinbox)
        header.addWidget(self._week_range_label)
        header.addWidget(self._next_button)
        header.addWidget(self._today_button)
        header.addStretch()
        header.addWidget(self._month_button)
        header.addWidget(self._week_button)
        header.addWidget(self._year_button)
        header.addWidget(self._stats_button)

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

        self._stats_view = StatsView()
        self._stats_view.watch_clicked.connect(self._on_rotation_clicked)

        self._week_grid = _MonthGrid()
        self._week_grid.range_chosen.connect(self._on_week_range_chosen)

        self._roll_week_button = QPushButton(self.tr("Roll the week"))
        self._roll_week_button.clicked.connect(self._on_roll_week)
        self._week_dismiss_button = QPushButton(self.tr("Dismiss"))
        self._week_dismiss_button.clicked.connect(self._on_dismiss_week)
        self._week_accept_all_button = QPushButton(self.tr("Accept all"))
        self._week_accept_all_button.setProperty("variant", "primary")
        self._week_accept_all_button.clicked.connect(self._on_accept_week)

        week_actions = QHBoxLayout()
        week_actions.addWidget(self._roll_week_button)
        week_actions.addStretch()
        week_actions.addWidget(self._week_dismiss_button)
        week_actions.addWidget(self._week_accept_all_button)

        week_content = QWidget()
        week_layout = QVBoxLayout(week_content)
        week_layout.setContentsMargins(0, 0, 0, 0)
        week_layout.setSpacing(16)
        week_layout.addWidget(self._week_grid, stretch=1)
        week_layout.addLayout(week_actions)

        self._content_stack = QStackedWidget()
        self._content_stack.addWidget(month_content)
        self._content_stack.addWidget(self._year_view)
        self._content_stack.addWidget(self._stats_view)
        self._content_stack.addWidget(week_content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addLayout(header)
        layout.addWidget(self._content_stack, stretch=1)

        self._update_mode_buttons()
        self._retranslate()
        self._render()

    def _retranslate(self) -> None:
        self._prev_button.setToolTip(self.tr("Previous month"))
        self._next_button.setToolTip(self.tr("Next month"))
        self._today_button.setText(self.tr("Today"))
        for i in range(12):
            self._month_combo.setItemText(i, QLocale().standaloneMonthName(i + 1))
        self._month_button.setText(self.tr("Month"))
        self._week_button.setText(self.tr("Week"))
        self._year_button.setText(self.tr("Year"))
        self._stats_button.setText(self.tr("Stats"))
        self._roll_week_button.setText(self.tr("Roll the week"))
        self._week_dismiss_button.setText(self.tr("Dismiss"))
        self._week_accept_all_button.setText(self.tr("Accept all"))
        # _grid/_week_grid's weekday headers, _footer_label, and
        # _week_range_label all live inside _render()/_render_week()'s
        # from-scratch construction -- re-running it (below) is the
        # retranslation for those, the same "already a full rebuild
        # function" pattern used elsewhere this session. _stats_view
        # catches LanguageChange independently (it propagates to the whole
        # widget tree) -- _year_view has no static text of its own; its
        # only locale-dependent content (month names) is painted fresh
        # every time _render() below calls self._year_view.render(), which
        # happens whenever Year mode is actually on screen (immediately if
        # active now, else lazily on the next switch to it -- same as
        # _grid/_week_grid, invisible either way since QStackedWidget
        # never paints a widget that isn't current).
        self._render()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)

    def set_records(self, records: list[WatchRecord]) -> None:
        """Refreshes wear data without touching which month is on screen —
        the whole point of drag-range backfill is not losing your place."""
        self._records = records
        self._worn_index = build_worn_index(records)
        self._render()

    def focus_grid(self) -> None:
        self._grid.setFocus(Qt.FocusReason.OtherFocusReason)

    def clear_emphasis(self) -> None:
        """Escape, routed through CollectionView/MainWindow — a no-op if
        nothing is currently emphasised. SPEC.md §5.5's click-through clears
        on mode change (see _set_mode) or Escape; this is the Escape half."""
        if self._emphasized_slug is None:
            return
        self._emphasized_slug = None
        motion.fade_transition(self._content_stack.currentWidget(), self._render)

    def _go_previous(self) -> None:
        if self._mode == _MODE_YEAR:
            self._year -= 1
        elif self._mode == _MODE_WEEK:
            self._week_anchor -= timedelta(days=7)
            self._week_proposal = None  # a proposal belongs to the week it was rolled for, not wherever navigation lands next
        else:
            self._month -= 1
            if self._month == 0:
                self._month = 12
                self._year -= 1
        motion.fade_transition(self._content_stack.currentWidget(), self._render)

    def _go_next(self) -> None:
        if self._mode == _MODE_YEAR:
            self._year += 1
        elif self._mode == _MODE_WEEK:
            self._week_anchor += timedelta(days=7)
            self._week_proposal = None
        else:
            self._month += 1
            if self._month == 13:
                self._month = 1
                self._year += 1
        motion.fade_transition(self._content_stack.currentWidget(), self._render)

    def _go_today(self) -> None:
        today = date.today()
        self._year = today.year
        if self._mode == _MODE_MONTH:
            self._month = today.month
        elif self._mode == _MODE_WEEK:
            self._week_anchor = today
            self._week_proposal = None
        motion.fade_transition(self._content_stack.currentWidget(), self._render)

    def _on_month_combo_changed(self, index: int) -> None:
        month = index + 1
        if index >= 0 and month != self._month:
            self._month = month
            motion.fade_transition(self._content_stack.currentWidget(), self._render)

    def _on_year_spinbox_changed(self, value: int) -> None:
        if value != self._year:
            self._year = value
            motion.fade_transition(self._content_stack.currentWidget(), self._render)

    def _set_mode(self, mode: str) -> None:
        self._emphasized_slug = None  # SPEC.md §5.5: any mode change clears click-through emphasis
        if self._mode == _MODE_WEEK and mode != _MODE_WEEK:
            self._week_proposal = None  # leaving Week mode -- a stale proposal for a hidden screen serves no purpose
        self._mode = mode
        self._update_mode_buttons()

        def _switch_and_render() -> None:
            self._content_stack.setCurrentIndex({_MODE_MONTH: 0, _MODE_YEAR: 1, _MODE_STATS: 2, _MODE_WEEK: 3}[mode])
            self._render()

        motion.fade_transition(self._content_stack, _switch_and_render)

    def _update_mode_buttons(self) -> None:
        self._month_button.setChecked(self._mode == _MODE_MONTH)
        self._year_button.setChecked(self._mode == _MODE_YEAR)
        self._stats_button.setChecked(self._mode == _MODE_STATS)
        self._week_button.setChecked(self._mode == _MODE_WEEK)

    def _jump_to_month(self, month: int) -> None:
        self._month = month
        self._set_mode(_MODE_MONTH)

    def _on_rotation_clicked(self, slug: str) -> None:
        """Stats mode's Rotation click-through (SPEC.md §5.5): switch to
        Month mode, then emphasise — in that order, since _set_mode() itself
        unconditionally clears any emphasis as part of "mode change clears
        it", and this mode change is the one time that must not erase the
        emphasis it's meant to establish."""
        self._set_mode(_MODE_MONTH)
        self._emphasized_slug = slug
        self._render()

    def _update_header_visibility(self) -> None:
        is_stats = self._mode == _MODE_STATS
        is_week = self._mode == _MODE_WEEK
        for widget in (self._prev_button, self._next_button, self._today_button):
            widget.setVisible(not is_stats)
        self._year_spinbox.setVisible(not is_stats and not is_week)
        self._month_combo.setVisible(self._mode == _MODE_MONTH)
        self._week_range_label.setVisible(is_week)

    def _render(self) -> None:
        self._update_header_visibility()
        if self._mode == _MODE_STATS:
            self._stats_view.render(self._records, date.today())
            return

        if self._mode == _MODE_WEEK:
            self._render_week()
            return

        self._year_spinbox.blockSignals(True)
        self._year_spinbox.setValue(self._year)
        self._year_spinbox.blockSignals(False)

        if self._mode == _MODE_YEAR:
            self._year_view.render(self._year, self._worn_index)
        else:
            self._month_combo.blockSignals(True)
            self._month_combo.setCurrentIndex(self._month - 1)
            self._month_combo.blockSignals(False)

            self._grid.render(month_grid_days(self._year, self._month), self._worn_index, self._emphasized_slug)
            self._footer_label.setText(self._footer_text())

    def _render_week(self) -> None:
        days = week_grid_days(self._week_anchor)
        record_by_day = dict(self._worn_index)
        if self._week_proposal:
            for day, record in self._week_proposal.items():
                # Real, already-logged wear always wins over a stale
                # proposal — never let the display suggest overwriting it.
                record_by_day.setdefault(day, record)
        self._week_grid.render(days, record_by_day, emphasized_slug=None)
        proposed_days = frozenset(self._week_proposal) if self._week_proposal else frozenset()
        self._week_grid.apply_proposed(proposed_days)

        start, end = days[0].day, days[-1].day
        locale = QLocale()
        start_text = locale.toString(QDate(start.year, start.month, start.day), "MMM d")
        end_text = locale.toString(QDate(end.year, end.month, end.day), "MMM d, yyyy")
        self._week_range_label.setText(f"{start_text} – {end_text}")

        has_proposal = bool(self._week_proposal)
        self._week_accept_all_button.setVisible(has_proposal)
        self._week_dismiss_button.setVisible(has_proposal)

    def _footer_text(self) -> str:
        in_month = {d: r for d, r in self._worn_index.items() if d.year == self._year and d.month == self._month}
        days_recorded = len(in_month)
        distinct_worn = {r.slug for r in in_month.values()}
        valid_count = len([r for r in self._records if r.watch is not None])
        not_worn = max(valid_count - len(distinct_worn), 0)
        # Two separate translated literals per counted noun, not Qt's %n
        # mechanism -- see the matching comment in calendar_stats.py's
        # _build_coverage_section(). "not worn this month" has no counted
        # noun of its own (matches the pre-Commit-C English wording), so it
        # needs no singular/plural branch, just the count substituted in.
        days_text = (
            self.tr("1 day recorded") if days_recorded == 1
            else self.tr("{count} days recorded").format(count=days_recorded)
        )
        watches_text = (
            self.tr("1 watch worn") if len(distinct_worn) == 1
            else self.tr("{count} watches worn").format(count=len(distinct_worn))
        )
        not_worn_text = self.tr("{count} not worn this month").format(count=not_worn)
        return f"{days_text}  ·  {watches_text}  ·  {not_worn_text}"

    def _on_range_chosen(self, dates: list[date]) -> None:
        current = self._worn_index.get(dates[0]) if len(dates) == 1 else None
        # SPEC.md §5.12: only Owned watches can be worn — offering a
        # Wishlist/Incoming/Sold/Gifted watch here would let the picker
        # "succeed" while build_worn_index() silently drops the assignment.
        assignable = [r for r in self._records if r.watch is not None and r.watch.status == "Owned"]
        picker = WatchPicker(assignable, current=current, parent=self)
        if picker.exec() != QDialog.DialogCode.Accepted:
            return
        if picker.was_cleared():
            self.clear_requested.emit(dates)
        else:
            self.assign_requested.emit(dates, picker.chosen_record())

    def _on_week_range_chosen(self, dates: list[date]) -> None:
        """Milestone 20: a single click on a still-proposed day accepts
        just that day; every other case (a drag range, an already-logged
        day, an empty non-proposed day) falls through to the exact same
        WatchPicker flow the month grid already uses — SPEC.md milestone 20
        step 14's "every day remains individually editable afterwards
        through the normal calendar interaction"."""
        if len(dates) == 1 and self._week_proposal is not None and dates[0] in self._week_proposal:
            day = dates[0]
            record = self._week_proposal.pop(day)
            if day not in self._worn_index:
                self.assign_requested.emit([day], record)
            # else: became real since the roll -- drop the stale proposal
            # silently rather than overwriting what's actually there now.
            self._render()
            return
        self._on_range_chosen(dates)

    def _on_roll_week(self) -> None:
        """Proposes a pick for every currently-empty, not-yet-past day in
        the displayed week (SPEC.md milestone 20 steps 13/15) — writes
        nothing on its own. Silently does nothing with zero owned watches,
        the same empty-collection guard the today picker's UI applies
        before ever calling into saat.selection."""
        mode = (self._config.picker_mode() if self._config is not None else None) or MODE_WEIGHTED
        try:
            full_week = pick_week(self._records, self._week_anchor, mode)
        except ValueError:
            return
        today = date.today()
        self._week_proposal = {
            day: record for day, record in full_week.items() if day not in self._worn_index and day >= today
        }
        self._render()

    def _on_accept_week(self) -> None:
        """Writes every still-empty proposed day through the same
        assign_requested path the calendar's own picker uses — never a new
        write. Re-validated against current wear data right before writing,
        not the roll's stale snapshot: assign_worn() would silently steal a
        day from whoever now owns it, which is exactly the overwrite SPEC.md
        milestone 20 step 13 forbids if something got logged for one of
        these days after the roll."""
        if not self._week_proposal:
            return
        still_empty = {day: record for day, record in self._week_proposal.items() if day not in self._worn_index}
        self._week_proposal = None
        for day, record in still_empty.items():
            self.assign_requested.emit([day], record)
        self._render()

    def _on_dismiss_week(self) -> None:
        self._week_proposal = None
        self._render()
