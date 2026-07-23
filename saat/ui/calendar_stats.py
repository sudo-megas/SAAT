from datetime import date

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from saat.storage import WatchRecord
from saat.ui.month_grid import WEEKDAY_LABELS
from saat.ui import theme
from saat.ui.theme import GROUP_SPACING, SIZE_SM, resolve_fonts
from saat.ui.year_view import slug_color
from saat.wear import (
    PERIOD_ALL_TIME,
    PERIOD_MONTH,
    PERIOD_YEAR,
    PeriodStats,
    compute_period_stats,
)

PERIOD_LABELS = {
    PERIOD_MONTH: "This month",
    PERIOD_YEAR: "This year",
    PERIOD_ALL_TIME: "All time",
}

BAR_HEIGHT = 6
BAR_WIDGET_HEIGHT = 12
CHIP_SIZE = 16


def _display_name(record: WatchRecord) -> str:
    return f"{record.watch.brand} {record.watch.model}"


def _section_heading(text: str) -> QLabel:
    """Matches sidebar.py's facet-group headings — plain, muted, condensed,
    uppercase. Stats mode's sections are NOT spec groups, so they deliberately
    do not use MinuteTrackHeader: SPEC.md §6 reserves that for the detail
    page, "the app's only flourish... used only for the detail view's spec
    groups"."""
    heading = QLabel(text.upper())
    heading.setProperty("class", "spec-row-label")
    heading.setObjectName("statsSectionHeading")  # distinguishes a section heading from other spec-row-label text (e.g. weekday letters), for tests
    return heading


def _figure_row(label: str, value: str) -> QWidget:
    """A label/value pair for a plain monospace figure (Coverage, deltas,
    streaks) — the same label+value-mono pairing spec_group.py uses for
    detail-page rows, without the minute-track header those rows sit under."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    label_widget = QLabel(label)
    label_widget.setProperty("class", "spec-row-label")
    value_widget = QLabel(value)
    value_widget.setProperty("class", "spec-row-value-mono")
    layout.addWidget(label_widget)
    layout.addStretch()
    layout.addWidget(value_widget)
    return row


class _RotationBar(QWidget):
    """The hairline bar + even-split tick for one Rotation row. Track in
    --rule, fill in --gilt — the same track/fill relationship
    minute_track.py's hairline+tick drawing already establishes. `scale`
    is shared across every row in the list (see StatsView._bar_scale), so
    the tick lands at an identical x-offset on every bar — "a tick on every
    bar at the even-split mark" reads as one implied vertical reference
    line down the whole Rotation list. No antialiasing: these are
    axis-aligned rectangles and a 1px vertical line, so AA would only risk
    blended edge pixels that make pixel-sampled tests non-deterministic."""

    def __init__(
        self, days_worn: int, scale: float, even_split: float | None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._days_worn = days_worn
        self._scale = scale
        self._even_split = even_split
        self.setFixedHeight(BAR_WIDGET_HEIGHT)
        self.setMinimumWidth(120)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        palette = theme.colors()
        width = self.width()
        bar_top = (BAR_WIDGET_HEIGHT - BAR_HEIGHT) // 2

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(palette.rule))
        painter.drawRect(QRect(0, bar_top, width, BAR_HEIGHT))

        if self._scale > 0 and self._days_worn > 0:
            fill_width = round((self._days_worn / self._scale) * width)
            painter.setBrush(QColor(palette.gilt))
            painter.drawRect(QRect(0, bar_top, fill_width, BAR_HEIGHT))

        if self._even_split is not None and self._scale > 0:
            tick_x = round((self._even_split / self._scale) * width)
            painter.setPen(QPen(QColor(palette.text_muted), 1))
            painter.drawLine(tick_x, 0, tick_x, BAR_WIDGET_HEIGHT)

        painter.end()


class _RotationRow(QWidget):
    """One Rotation entry: brand/model label, the hairline bar+tick, and a
    monospace count/share. The whole row is clickable (mouse-event pattern
    from year_view.py's _YearMonthBlock), emitting `clicked` with this row's
    slug — SPEC.md §5.5's click-through into Month mode."""

    clicked = Signal(str)  # slug

    def __init__(
        self,
        record: WatchRecord,
        days_worn: int,
        share: float,
        scale: float,
        even_split: float | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._slug = record.slug
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        label = QLabel(_display_name(record))
        label.setProperty("class", "spec-row-value")

        mono_font = QFont(resolve_fonts()["mono"])
        mono_font.setPixelSize(SIZE_SM)
        count_label = QLabel(f"{days_worn:d}  ({share:.0%})")
        count_label.setFont(mono_font)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addWidget(label)
        top_row.addStretch()
        top_row.addWidget(count_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)
        layout.addLayout(top_row)
        layout.addWidget(_RotationBar(days_worn, scale, even_split))

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit(self._slug)
        super().mouseReleaseEvent(event)


class _ChipSwatch(QWidget):
    """A single flat colour chip — slug_color(slug) when a watch owns this
    weekday, --rule (a plain, unowned hairline colour) otherwise. No new
    colour logic: this reuses year_view.py's slug_color directly."""

    def __init__(self, record: WatchRecord | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._record = record
        self.setFixedSize(CHIP_SIZE, CHIP_SIZE)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(slug_color(self._record.slug) if self._record is not None else QColor(theme.colors().rule))
        painter.drawRect(self.rect())
        painter.end()


class _WeekdayCell(QWidget):
    def __init__(self, label: str, record: WatchRecord | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        text = QLabel(label.upper())
        text.setProperty("class", "spec-row-label")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text)
        layout.addWidget(_ChipSwatch(record), alignment=Qt.AlignmentFlag.AlignHCenter)


def _bar_scale(stats: PeriodStats) -> float:
    """The shared denominator every Rotation bar and the even-split tick
    plot against. The longest bar (or the even-split reference, whichever
    is larger) reaches the full width, rather than every bar clustering in
    a sliver at the low end of `period_days` for a long period like This
    year or All time — a fixed 0..period_days axis is honest but unreadable
    once a single watch's days are a small fraction of a long period."""
    max_days_worn = max((days_worn for _, days_worn, _ in stats.rotation), default=0)
    return max(max_days_worn, stats.even_split or 0)


class StatsView(QWidget):
    """Calendar Stats mode: rotation, coverage, streaks over a chosen
    period. See SPEC.md §5.5. Self-contained — owns its own period
    selector and recomputes from the last-given records, so CalendarView
    never needs to know which period is active."""

    watch_clicked = Signal(str)  # slug

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._records: list[WatchRecord] = []
        self._today: date | None = None
        self._period = PERIOD_MONTH

        self._period_buttons: dict[str, QPushButton] = {}
        period_row = QHBoxLayout()
        period_row.setContentsMargins(0, 0, 0, 0)
        for period in (PERIOD_MONTH, PERIOD_YEAR, PERIOD_ALL_TIME):
            button = QPushButton(PERIOD_LABELS[period])
            button.setCheckable(True)
            button.clicked.connect(lambda _checked, p=period: self._set_period(p))
            self._period_buttons[period] = button
            period_row.addWidget(button)
        period_row.addStretch()

        self._empty_message = QLabel()
        self._empty_message.setProperty("muted", True)
        self._empty_message.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._sections_container = QWidget()
        self._sections_layout = QVBoxLayout(self._sections_container)
        self._sections_layout.setContentsMargins(0, 0, 0, 0)
        self._sections_layout.setSpacing(GROUP_SPACING)
        self._sections_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self._sections_container)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addLayout(period_row)
        layout.addWidget(self._empty_message)
        layout.addWidget(scroll, stretch=1)

        self._update_period_buttons()

    def render(self, records: list[WatchRecord], today: date | None = None) -> None:
        self._records = records
        self._today = today
        self._rebuild()

    def _set_period(self, period: str) -> None:
        self._period = period
        self._update_period_buttons()
        self._rebuild()

    def _update_period_buttons(self) -> None:
        for period, button in self._period_buttons.items():
            button.setChecked(period == self._period)

    def _rebuild(self) -> None:
        stats = compute_period_stats(self._records, self._period, self._today)

        while self._sections_layout.count():
            item = self._sections_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if stats.watch_count == 0:
            self._empty_message.setText("No watches to show stats for.")
            self._empty_message.setVisible(True)
            self._sections_container.setVisible(False)
            return

        self._empty_message.setVisible(False)
        self._sections_container.setVisible(True)

        for section in (
            self._build_rotation_section(stats),
            self._build_not_worn_section(stats),
            self._build_coverage_section(stats),
            self._build_weekday_section(stats),
            self._build_streaks_section(stats),
        ):
            if section is not None:
                self._sections_layout.addWidget(section)
        self._sections_layout.addStretch()

    def _build_rotation_section(self, stats: PeriodStats) -> QWidget | None:
        if not stats.rotation:
            return None
        scale = _bar_scale(stats)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(_section_heading("Rotation"))
        for record, days_worn, share in stats.rotation:
            row = _RotationRow(record, days_worn, share, scale, stats.even_split)
            row.clicked.connect(self.watch_clicked.emit)
            layout.addWidget(row)
        return container

    def _build_not_worn_section(self, stats: PeriodStats) -> QWidget | None:
        if not stats.not_worn:
            return None
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(_section_heading("Not worn in this period"))
        for record in stats.not_worn:
            label = QLabel(_display_name(record))
            label.setProperty("class", "spec-row-value")
            layout.addWidget(label)
        return container

    def _build_coverage_section(self, stats: PeriodStats) -> QWidget | None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(_section_heading("Coverage"))

        coverage_pct = stats.days_recorded / stats.period_days if stats.period_days else 0.0
        layout.addWidget(_figure_row("Days recorded", f"{stats.days_recorded} / {stats.period_days} ({coverage_pct:.0%})"))

        if stats.deltas is not None:
            days_delta, watches_delta = stats.deltas
            layout.addWidget(_figure_row("Vs. last period", f"{days_delta:+d} days · {watches_delta:+d} watches"))
        return container

    def _build_weekday_section(self, stats: PeriodStats) -> QWidget | None:
        if all(record is None for record in stats.weekday_most_worn.values()):
            return None
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(_section_heading("Weekday"))

        strip = QHBoxLayout()
        strip.setContentsMargins(0, 0, 0, 0)
        for weekday, label in enumerate(WEEKDAY_LABELS):
            strip.addWidget(_WeekdayCell(label, stats.weekday_most_worn.get(weekday)))
        strip.addStretch()
        layout.addLayout(strip)
        return container

    def _build_streaks_section(self, stats: PeriodStats) -> QWidget | None:
        # run_length == 0 iff nothing was ever recorded in the period (any
        # recorded day gives a run of at least 1) — the one condition where
        # this section has nothing to say. It is NOT "run == 0 and gap == 0":
        # when nothing is recorded the gap equals the whole period, not zero,
        # so that compound condition could never actually hide the section.
        run_length, run_record = stats.longest_run
        if run_length == 0:
            return None

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(_section_heading("Streaks"))

        if run_length > 0:
            days_word = "day" if run_length == 1 else "days"
            layout.addWidget(_figure_row("Longest run", f"{run_length} {days_word} · {_display_name(run_record)}"))
        if stats.longest_gap > 0:
            days_word = "day" if stats.longest_gap == 1 else "days"
            layout.addWidget(_figure_row("Longest gap", f"{stats.longest_gap} {days_word}"))
        return container
