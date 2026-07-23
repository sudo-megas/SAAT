import calendar as cal
from datetime import date, timedelta

from PySide6.QtCore import QPointF, QRect, QUrl, Qt, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from saat.models import LogEntry, Movement, Strap, TimingEntry, Watch
from saat.storage import WatchRecord
from saat.ui.formatting import EM_DASH, fmt_accuracy, fmt_bool, fmt_bph, fmt_date, fmt_list, fmt_number, fmt_price, fmt_water_resistance, is_empty
from saat.ui.images import cropped_pixmap, fit_pixmap, list_images
from saat.ui.maintenance import maintenance_due_text
from saat.ui.minute_track import MinuteTrackHeader
from saat.ui.spec_group import SpecRow, build_spec_group, spec_row
from saat.ui.strap_compat import CompatibleStrap, compatible_straps
from saat.ui import theme
from saat.ui.theme import GROUP_SPACING, PAGE_MARGIN, SIZE_XS, resolve_fonts
from saat.ui.wear_stats import days_since_worn, last_worn, longest_streak, times_worn_this_year

PRIMARY_IMAGE_MAX = (480, 600)
THUMB_SIZE = 72
STRAP_PHOTO_SIZE = 56
MONTH_BLOCK_WIDTH = 56
MONTH_BLOCK_HEIGHT = 20
SPARKLINE_HEIGHT = 48
MIN_SPARKLINE_READINGS = 3


# --- Movement -----------------------------------------------------------

def _get_accuracy(m: Movement):
    if m.accuracy_min is None and m.accuracy_max is None:
        return None
    return (m.accuracy_min, m.accuracy_max, m.accuracy_unit or "sec/day")


def _movement_rows(watch: Watch) -> list[SpecRow]:
    m = watch.movement
    # SPEC.md §4: power reserve vs. battery life — show one or the other, driven by kind.
    if m.kind in ("Quartz", "Solar"):
        reserve_row = spec_row("Battery Life", m.battery_life_years, lambda v: fmt_number(v, "y"), numeric=True)
    else:
        reserve_row = spec_row("Power Reserve", m.power_reserve_hours, lambda v: fmt_number(v, "h"), numeric=True)

    return [
        spec_row("Caliber", m.caliber),
        spec_row("Kind", m.kind),
        reserve_row,
        spec_row("Accuracy", _get_accuracy(m), fmt_accuracy, numeric=True),
        spec_row("Jewels", m.jewels, str, numeric=True),
        spec_row("Frequency", m.bph, fmt_bph, numeric=True),
        spec_row("Hacking", m.hacking, fmt_bool),
        spec_row("Handwinding", m.handwinding, fmt_bool),
        spec_row("Origin", m.origin),
    ]


# --- Case -----------------------------------------------------------

def _case_rows(watch: Watch) -> list[SpecRow]:
    c = watch.case
    return [
        spec_row("Diameter", c.diameter_mm, lambda v: fmt_number(v, " mm"), numeric=True),
        spec_row("Lug-to-Lug", c.lug_to_lug_mm, lambda v: fmt_number(v, " mm"), numeric=True),
        spec_row("Thickness", c.thickness_mm, lambda v: fmt_number(v, " mm"), numeric=True),
        spec_row("Lug Width", c.lug_width_mm, lambda v: fmt_number(v, " mm"), numeric=True),
        spec_row("Material", c.material),
        spec_row("Crystal", c.crystal),
        spec_row("Crown", c.crown),
        spec_row("Bezel", c.bezel),
        spec_row("Caseback", c.caseback),
        spec_row("Water Resistance", c.water_resistance_m, fmt_water_resistance, numeric=True),
        spec_row("Weight", c.weight_g, lambda v: fmt_number(v, " g"), numeric=True),
    ]


# --- Dial -----------------------------------------------------------

def _dial_rows(watch: Watch) -> list[SpecRow]:
    d = watch.dial
    return [
        spec_row("Colour", d.colour),
        spec_row("Material", d.material),
        spec_row("Indices", d.indices),
        spec_row("Lume", d.lume),
        spec_row("Complications", d.complications, fmt_list),
    ]


# --- Acquisition -----------------------------------------------------------

def _url_row(url: str | None) -> SpecRow:
    if is_empty(url):
        return SpecRow("URL", EM_DASH)
    link = QPushButton(url)
    link.setProperty("variant", "link")
    link.setCursor(Qt.CursorShape.PointingHandCursor)
    link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
    return SpecRow("URL", url, widget=link)


def _acquisition_rows(watch: Watch) -> list[SpecRow]:
    a = watch.acquisition
    price = (a.price, a.currency or "") if a.price is not None else None
    return [
        spec_row("Acquired", a.date, fmt_date, numeric=True),
        spec_row("Price", price, fmt_price, numeric=True),
        spec_row("Seller", a.seller),
        _url_row(a.url),
        spec_row("Condition", a.condition),
        spec_row("Box & Papers", a.box_and_papers, fmt_bool),
        spec_row("Warranty Until", a.warranty_until, fmt_date, numeric=True),
    ]


# --- Maintenance -----------------------------------------------------------

def _maintenance_rows(watch: Watch) -> list[SpecRow]:
    m = watch.maintenance
    return [
        spec_row("Service Interval", m.service_interval_years, lambda v: fmt_number(v, " y"), numeric=True),
        spec_row("Battery Due", m.battery_due, fmt_date, numeric=True),
    ]


# --- Straps: small cards with their own photo, fitted one marked ----------

def _build_strap_card(record: WatchRecord, strap: Strap) -> QWidget:
    frame = QFrame()
    frame.setProperty("class", "strap-card")
    row = QHBoxLayout(frame)
    row.setContentsMargins(12, 12, 12, 12)
    row.setSpacing(12)

    photo = QLabel()
    photo.setFixedSize(STRAP_PHOTO_SIZE, STRAP_PHOTO_SIZE)
    photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    pixmap = None
    if strap.image:
        image_path = record.path / "images" / strap.image
        if image_path.exists():
            pixmap = cropped_pixmap(image_path, STRAP_PHOTO_SIZE, STRAP_PHOTO_SIZE)
    if pixmap is not None:
        photo.setPixmap(pixmap)
    else:
        photo.setProperty("class", "strap-photo-placeholder")
    row.addWidget(photo)

    text_col = QVBoxLayout()
    text_col.setSpacing(2)
    title_parts = [p for p in (strap.material, strap.colour) if p]
    title = QLabel(" · ".join(title_parts) if title_parts else EM_DASH)
    title.setProperty("class", "strap-title")
    text_col.addWidget(title)

    detail_parts = []
    if strap.width_mm is not None:
        detail_parts.append(fmt_number(strap.width_mm, " mm"))
    if strap.clasp:
        detail_parts.append(strap.clasp)
    detail = QLabel(" · ".join(detail_parts) if detail_parts else EM_DASH)
    detail.setProperty("muted", True)
    text_col.addWidget(detail)

    row.addLayout(text_col, 1)

    if strap.fitted:
        badge = QLabel("FITTED")
        badge.setProperty("class", "fitted-badge")
        row.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)

    return frame


def _build_straps_group(record: WatchRecord) -> QWidget | None:
    watch = record.watch
    if not watch.straps:
        return None
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addWidget(MinuteTrackHeader("Straps"))
    for strap in watch.straps:
        layout.addWidget(_build_strap_card(record, strap))
    return container


def _build_strap_compat_entry(match: CompatibleStrap) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    owner = QLabel(f"{match.record.watch.brand} {match.record.watch.model}")
    owner.setProperty("muted", True)
    layout.addWidget(owner)
    layout.addWidget(_build_strap_card(match.record, match.strap))
    return container


def _build_strap_compat_group(record: WatchRecord, all_records: list[WatchRecord]) -> QWidget | None:
    """SPEC.md §5.9: straps belonging to other watches that physically fit
    this one. Hidden when there are no matches."""
    matches = compatible_straps(record, all_records)
    if not matches:
        return None
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addWidget(MinuteTrackHeader("Compatible Straps"))
    for match in matches:
        layout.addWidget(_build_strap_compat_entry(match))
    return container


# --- Log: chronological, newest first --------------------------------------

def _build_log_row(entry: LogEntry) -> QWidget:
    row = QWidget()
    layout = QVBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)

    header_parts = [p for p in (fmt_date(entry.date) if entry.date else None, entry.kind) if p]
    header = QLabel(" · ".join(header_parts) if header_parts else EM_DASH)
    header.setProperty("class", "log-entry-header")
    layout.addWidget(header)

    if entry.note:
        note = QLabel(entry.note)
        note.setWordWrap(True)
        note.setProperty("muted", True)
        layout.addWidget(note)

    return row


def _build_log_group(watch: Watch) -> QWidget | None:
    if not watch.log:
        return None
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    layout.addWidget(MinuteTrackHeader("Log"))
    entries = sorted(watch.log, key=lambda e: e.date or date.min, reverse=True)
    for entry in entries:
        layout.addWidget(_build_log_row(entry))
    return container


# --- Timing: a small sparkline once there are 3+ readings, plain rows always

class _TimingSparkline(QWidget):
    """Deviation_sec over time, oldest to newest, with a zero-reference line
    — how a mechanical owner sees at a glance whether a watch runs fast, slow,
    or drifted after a service. Only built with >=3 dated+valued readings;
    see _build_timing_group(). SPEC.md §4."""

    def __init__(self, entries: list[TimingEntry], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        dated = [e for e in entries if e.date is not None and e.deviation_sec is not None]
        self._values = [e.deviation_sec for e in sorted(dated, key=lambda e: e.date)]
        self.setFixedHeight(SPARKLINE_HEIGHT)
        self.setMinimumWidth(160)

    def paintEvent(self, event: QPaintEvent) -> None:
        if len(self._values) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = theme.colors()

        span_values = self._values + [0.0]  # zero is always in range so the reference line stays on-widget
        low, high = min(span_values), max(span_values)
        span = (high - low) or 1.0

        w, h = self.width(), self.height()
        pad = 4

        def y_for(value: float) -> float:
            return (h - pad) - ((value - low) / span) * (h - 2 * pad)

        zero_y = y_for(0.0)
        painter.setPen(QPen(QColor(palette.rule), 1))
        painter.drawLine(QPointF(0, zero_y), QPointF(w, zero_y))

        points = [
            QPointF(i / (len(self._values) - 1) * w, y_for(value))
            for i, value in enumerate(self._values)
        ]
        painter.setPen(QPen(QColor(palette.gilt), 1.5))
        for start, end in zip(points, points[1:]):
            painter.drawLine(start, end)

        painter.end()


def _build_timing_row(entry: TimingEntry) -> QWidget:
    parts = [p for p in (
        fmt_date(entry.date) if entry.date else None,
        f"{entry.deviation_sec:+g} sec" if entry.deviation_sec is not None else None,
        entry.position,
    ) if p]
    label = QLabel(" · ".join(parts) if parts else EM_DASH)
    label.setProperty("class", "timing-row")
    return label


def _build_timing_group(watch: Watch) -> QWidget | None:
    if not watch.timing:
        return None
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.addWidget(MinuteTrackHeader("Timing"))

    valid_readings = [e for e in watch.timing if e.date is not None and e.deviation_sec is not None]
    if len(valid_readings) >= MIN_SPARKLINE_READINGS:
        layout.addWidget(_TimingSparkline(watch.timing))

    entries = sorted(watch.timing, key=lambda e: e.date or date.min, reverse=True)
    for entry in entries:
        layout.addWidget(_build_timing_row(entry))
    return container


# --- Notes -----------------------------------------------------------

def _build_notes_group(watch: Watch) -> QWidget | None:
    if is_empty(watch.notes) or not watch.notes.strip():
        return None
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addWidget(MinuteTrackHeader("Notes"))
    label = QLabel(watch.notes)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    layout.addWidget(label)
    return container


# --- Image gallery -----------------------------------------------------------

class _Thumbnail(QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class ImageGallery(QWidget):
    """Large primary image, thumbnail strip beneath, click to promote. See
    SPEC.md §5.6. Promotion is session-only — persisting image order is an
    add/edit-form concern (milestone 5)."""

    def __init__(self, record: WatchRecord, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._images = list_images(record)
        self._record = record
        self._current = 0
        self._thumb_labels: list[QLabel] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._primary = QLabel()
        self._primary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._primary, alignment=Qt.AlignmentFlag.AlignLeft)

        if len(self._images) > 1:
            strip = QHBoxLayout()
            strip.setSpacing(8)
            for index, path in enumerate(self._images):
                thumb = _Thumbnail()
                thumb.setProperty("class", "gallery-thumb")
                thumb.setFixedSize(THUMB_SIZE, THUMB_SIZE)
                thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
                thumb.setCursor(Qt.CursorShape.PointingHandCursor)
                pixmap = cropped_pixmap(path, THUMB_SIZE, THUMB_SIZE)
                if pixmap is not None:
                    thumb.setPixmap(pixmap)
                thumb.clicked.connect(lambda i=index: self._promote(i))
                self._thumb_labels.append(thumb)
                strip.addWidget(thumb)
            strip.addStretch()
            layout.addLayout(strip)

        self._render_primary(watch=record.watch)

    def _promote(self, index: int) -> None:
        self._current = index
        self._render_primary(watch=self._record.watch)

    def _render_primary(self, watch: Watch) -> None:
        max_w, max_h = PRIMARY_IMAGE_MAX
        self._primary.setFixedSize(max_w, max_h)

        if self._images:
            pixmap = fit_pixmap(self._images[self._current], max_w, max_h)
        else:
            pixmap = None

        if pixmap is not None:
            self._primary.setPixmap(pixmap)
        else:
            self._primary.clear()
            self._primary.setProperty("class", "detail-image-placeholder")
            diameter = fmt_number(watch.case.diameter_mm, " mm") if watch.case.diameter_mm is not None else EM_DASH
            lug = fmt_number(watch.case.lug_width_mm, " mm lugs") if watch.case.lug_width_mm is not None else EM_DASH
            self._primary.setText(f"{diameter}\n{lug}")

        for i, thumb in enumerate(self._thumb_labels):
            thumb.setProperty("active", i == self._current)
            thumb.style().unpolish(thumb)
            thumb.style().polish(thumb)


# --- Two-column responsive group layout -------------------------------------

class SpecGroupsContainer(QWidget):
    """Spec groups, two columns on a wide window, one when narrow. See
    SPEC.md §5.6."""

    MIN_GROUP_WIDTH = 420

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(GROUP_SPACING)
        self._layout.setVerticalSpacing(GROUP_SPACING)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._groups: list[QWidget] = []

    def set_groups(self, groups: list[QWidget]) -> None:
        for group in self._groups:
            self._layout.removeWidget(group)
        self._groups = groups
        for group in groups:
            group.setParent(self)
        self._relayout()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self) -> None:
        if not self._groups:
            return
        for group in self._groups:
            self._layout.removeWidget(group)

        columns = 2 if self.width() >= 2 * self.MIN_GROUP_WIDTH + GROUP_SPACING else 1
        self._layout.setColumnStretch(0, 1)
        self._layout.setColumnStretch(1, 1 if columns == 2 else 0)

        for index, group in enumerate(self._groups):
            row, col = divmod(index, columns)
            self._layout.addWidget(group, row, col)


# --- Header: identity fields not covered by a spec group --------------------

# --- Wear -----------------------------------------------------------

def _wear_stats_text(watch: Watch) -> str:
    last = last_worn(watch)
    days = days_since_worn(watch)
    times = times_worn_this_year(watch)
    streak = longest_streak(watch)
    return (
        f"Last worn {fmt_date(last)}  ·  {days} day{'s' if days != 1 else ''} ago  ·  "
        f"Worn {times} time{'s' if times != 1 else ''} this year  ·  "
        f"Longest streak {streak} day{'s' if streak != 1 else ''}"
    )


class _TwelveMonthStrip(QWidget):
    """This watch's worn days over the trailing twelve months, one compact
    block per month — a density strip, not a navigable calendar. Only built
    when there's at least one worn date; see build_wear_section(). See
    SPEC.md §5.6."""

    def __init__(self, worn: list[date], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worn = set(worn)

        months = []
        year, month = date.today().year, date.today().month
        for _ in range(12):
            months.append((year, month))
            month -= 1
            if month == 0:
                month, year = 12, year - 1
        self._months = list(reversed(months))

        self._label_font = QFont(resolve_fonts()["sans_condensed"])
        self._label_font.setPixelSize(SIZE_XS)
        self.setFixedHeight(MONTH_BLOCK_HEIGHT + 16)
        self.setMinimumWidth(MONTH_BLOCK_WIDTH * 12 + 4 * 11)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self._label_font)

        x = 0
        for year, month in self._months:
            days_in_month = cal.monthrange(year, month)[1]
            block = QRect(x, 0, MONTH_BLOCK_WIDTH, MONTH_BLOCK_HEIGHT)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(theme.colors().rule))
            painter.drawRect(block)

            painter.setPen(QColor(theme.colors().gilt))
            for day in range(1, days_in_month + 1):
                if date(year, month, day) in self._worn:
                    tick_x = x + round((day - 0.5) / days_in_month * MONTH_BLOCK_WIDTH)
                    painter.drawLine(tick_x, 2, tick_x, MONTH_BLOCK_HEIGHT - 2)

            painter.setPen(QColor(theme.colors().text_muted))
            painter.drawText(QRect(x, MONTH_BLOCK_HEIGHT, MONTH_BLOCK_WIDTH, 16),
                              Qt.AlignmentFlag.AlignHCenter, date(year, month, 1).strftime("%b"))
            x += MONTH_BLOCK_WIDTH + 4

        painter.end()


def build_wear_section(watch: Watch) -> QWidget | None:
    """None hides the whole stats-line-plus-strip section for a never-worn
    watch — SPEC.md §5.6 says the strip is "hidden when it has never been
    worn," and a stats line of all-absent figures would be exactly the noise
    the rest of the app goes out of its way to stay silent about."""
    if not watch.worn:
        return None

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    stats = QLabel(_wear_stats_text(watch))
    stats.setProperty("muted", True)
    layout.addWidget(stats)
    layout.addWidget(_TwelveMonthStrip(watch.worn))

    return container


def _build_header(watch: Watch) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    overline = QLabel(watch.brand.upper())
    overline.setProperty("class", "detail-overline")
    layout.addWidget(overline)

    title_text = watch.model
    if watch.nickname:
        title_text += f'  "{watch.nickname}"'
    title = QLabel(title_text)
    title.setProperty("class", "detail-title")
    title.setWordWrap(True)
    layout.addWidget(title)

    meta_parts = []
    if watch.reference:
        meta_parts.append(f"Ref. {watch.reference}")
    if watch.style:
        meta_parts.append(watch.style)
    if watch.group:
        meta_parts.append(watch.group)
    meta_parts.append(watch.status)
    if watch.storage:
        meta_parts.append(f"Storage: {watch.storage}")
    if watch.rating is not None:
        meta_parts.append("★" * watch.rating + "☆" * (5 - watch.rating))
    meta = QLabel(" · ".join(meta_parts))
    meta.setProperty("class", "detail-meta")
    meta.setWordWrap(True)
    layout.addWidget(meta)

    if watch.tags:
        tags = QLabel("Tags: " + fmt_list(watch.tags))
        tags.setProperty("muted", True)
        tags.setWordWrap(True)
        layout.addWidget(tags)

    if watch.serial:
        serial = QLabel(f"Serial {watch.serial}")
        serial.setProperty("muted", True)
        layout.addWidget(serial)

    return container


class DetailView(QScrollArea):
    """A watch's detail page: opens in the main area with a back affordance,
    not a modal. See SPEC.md §5.6."""

    back_requested = Signal()
    edit_requested = Signal(object)
    delete_requested = Signal(object)
    wore_today_requested = Signal(object)

    def __init__(self, record: WatchRecord, all_records: list[WatchRecord] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._record = record
        self._all_records = all_records if all_records is not None else [record]
        watch = record.watch

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        layout.setSpacing(GROUP_SPACING)

        back_button = QPushButton("← Back")
        back_button.setObjectName("back-button")
        back_button.setProperty("variant", "link")
        back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        back_button.clicked.connect(self.back_requested.emit)
        layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignLeft)

        maintenance_text = maintenance_due_text(watch)
        if maintenance_text is not None:
            maintenance_line = QLabel(maintenance_text)
            maintenance_line.setObjectName("maintenance-due-line")
            maintenance_line.setProperty("class", "maintenance-due-line")
            layout.addWidget(maintenance_line)

        layout.addWidget(_build_header(watch))
        layout.addWidget(ImageGallery(record))

        wear_section = build_wear_section(watch)
        if wear_section is not None:
            layout.addWidget(wear_section)

        wore_today_button = QPushButton("Wore this today")
        wore_today_button.clicked.connect(lambda: self.wore_today_requested.emit(record))
        layout.addWidget(wore_today_button, alignment=Qt.AlignmentFlag.AlignLeft)

        groups_container = SpecGroupsContainer()
        groups_container.set_groups(self._build_spec_groups(record))
        layout.addWidget(groups_container)

        layout.addWidget(self._build_edit_delete_row(record))

        layout.addStretch()
        self.setWidget(content)

    @property
    def record(self) -> WatchRecord:
        return self._record

    def _build_edit_delete_row(self, record: WatchRecord) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addStretch()

        edit_button = QPushButton("Edit")
        edit_button.clicked.connect(lambda: self.edit_requested.emit(record))
        row_layout.addWidget(edit_button)

        delete_button = QPushButton("Delete")
        delete_button.setProperty("variant", "destructive")
        delete_button.clicked.connect(lambda: self.delete_requested.emit(record))
        row_layout.addWidget(delete_button)

        return row

    def _build_spec_groups(self, record: WatchRecord) -> list[QWidget]:
        watch = record.watch
        candidates = [
            build_spec_group("Movement", _movement_rows(watch)),
            build_spec_group("Case", _case_rows(watch)),
            build_spec_group("Dial", _dial_rows(watch)),
            _build_straps_group(record),
            _build_strap_compat_group(record, self._all_records),
            build_spec_group("Acquisition", _acquisition_rows(watch)),
            build_spec_group("Maintenance", _maintenance_rows(watch)),
            _build_log_group(watch),
            _build_timing_group(watch),
            _build_notes_group(watch),
        ]
        return [group for group in candidates if group is not None]
