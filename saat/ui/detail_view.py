import calendar as cal
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QPointF, QRect, QUrl, Qt, Signal
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
from saat.sellers import Seller, find_seller
from saat.storage import WatchRecord
from saat.ui.form_fields import enum_label
from saat.ui.formatting import EM_DASH, fmt_accuracy, fmt_bool, fmt_bph, fmt_date, fmt_list, fmt_number, fmt_price, fmt_water_resistance, is_empty
from saat.ui.images import cropped_pixmap, fit_pixmap, list_images
from saat.ui.maintenance import maintenance_due_text
from saat.ui.minute_track import MinuteTrackHeader
from saat.ui.spec_group import SpecRow, build_spec_group, spec_row
from saat.ui.strap_compat import CompatibleStrap, compatible_straps
from saat.ui import icons, theme
from saat.ui.theme import GROUP_SPACING, PAGE_MARGIN, SIZE_XS, resolve_fonts
from saat.ui.wear_stats import days_since_worn, last_worn, longest_streak, times_worn_this_year
from saat.ui.year_view import SlugColorBar

PRIMARY_IMAGE_MAX = (640, 800)
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


def movement_rows(watch: Watch) -> list[SpecRow]:
    m = watch.movement
    # SPEC.md §4: power reserve vs. battery life — show one or the other, driven by kind.
    if m.kind in ("Quartz", "Solar"):
        reserve_row = spec_row(
            QCoreApplication.translate("DetailView", "Battery Life"), m.battery_life_years,
            lambda v: fmt_number(v, "y"), numeric=True,
        )
    else:
        reserve_row = spec_row(
            QCoreApplication.translate("DetailView", "Power Reserve"), m.power_reserve_hours,
            lambda v: fmt_number(v, "h"), numeric=True,
        )

    return [
        spec_row(QCoreApplication.translate("DetailView", "Caliber"), m.caliber),
        spec_row(QCoreApplication.translate("DetailView", "Kind"), m.kind, enum_label),
        reserve_row,
        spec_row(QCoreApplication.translate("DetailView", "Accuracy"), _get_accuracy(m), fmt_accuracy, numeric=True),
        spec_row(QCoreApplication.translate("DetailView", "Jewels"), m.jewels, str, numeric=True),
        spec_row(QCoreApplication.translate("DetailView", "Frequency"), m.bph, fmt_bph, numeric=True),
        spec_row(QCoreApplication.translate("DetailView", "Hacking"), m.hacking, fmt_bool),
        spec_row(QCoreApplication.translate("DetailView", "Handwinding"), m.handwinding, fmt_bool),
        spec_row(QCoreApplication.translate("DetailView", "Origin"), m.origin),
    ]


# --- Case -----------------------------------------------------------

def case_rows(watch: Watch) -> list[SpecRow]:
    c = watch.case
    return [
        spec_row(QCoreApplication.translate("DetailView", "Diameter"), c.diameter_mm, lambda v: fmt_number(v, " mm"), numeric=True),
        spec_row(QCoreApplication.translate("DetailView", "Lug-to-Lug"), c.lug_to_lug_mm, lambda v: fmt_number(v, " mm"), numeric=True),
        spec_row(QCoreApplication.translate("DetailView", "Thickness"), c.thickness_mm, lambda v: fmt_number(v, " mm"), numeric=True),
        spec_row(QCoreApplication.translate("DetailView", "Lug Width"), c.lug_width_mm, lambda v: fmt_number(v, " mm"), numeric=True),
        spec_row(QCoreApplication.translate("DetailView", "Material"), c.material, enum_label),
        spec_row(QCoreApplication.translate("DetailView", "Crystal"), c.crystal, enum_label),
        spec_row(QCoreApplication.translate("DetailView", "Crown"), c.crown, enum_label),
        spec_row(QCoreApplication.translate("DetailView", "Bezel"), c.bezel, enum_label),
        spec_row(QCoreApplication.translate("DetailView", "Caseback"), c.caseback, enum_label),
        spec_row(QCoreApplication.translate("DetailView", "Water Resistance"), c.water_resistance_m, fmt_water_resistance, numeric=True),
        spec_row(QCoreApplication.translate("DetailView", "Weight"), c.weight_g, lambda v: fmt_number(v, " g"), numeric=True),
    ]


# --- Dial -----------------------------------------------------------

def _fmt_translated_list(values: list[str]) -> str:
    return fmt_list([enum_label(v) for v in values])


def dial_rows(watch: Watch) -> list[SpecRow]:
    d = watch.dial
    return [
        spec_row(QCoreApplication.translate("DetailView", "Colour"), d.colour),
        spec_row(QCoreApplication.translate("DetailView", "Material"), d.material),
        spec_row(QCoreApplication.translate("DetailView", "Indices"), d.indices, enum_label),
        spec_row(QCoreApplication.translate("DetailView", "Lume"), d.lume),
        spec_row(QCoreApplication.translate("DetailView", "Complications"), d.complications, _fmt_translated_list),
    ]


# --- Acquisition -----------------------------------------------------------

def _url_row(url: str | None) -> SpecRow:
    if is_empty(url):
        return SpecRow(QCoreApplication.translate("DetailView", "URL"), EM_DASH)
    link = QPushButton(url)
    link.setProperty("variant", "link")
    link.setCursor(Qt.CursorShape.PointingHandCursor)
    link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
    return SpecRow(QCoreApplication.translate("DetailView", "URL"), url, widget=link)


def _seller_row(seller_name: str | None, sellers: list[Seller]) -> SpecRow:
    """SPEC.md §3: when the watch's seller string exactly matches a
    sellers.toml entry that has a url, render it as a link — the same
    QDesktopServices hand-off _url_row already uses, not a new mechanism.
    A non-matching or url-less seller renders as plain text, same as any
    other string field."""
    if is_empty(seller_name):
        return SpecRow(QCoreApplication.translate("DetailView", "Seller"), EM_DASH)
    matched = find_seller(sellers, seller_name)
    if matched is None or is_empty(matched.url):
        return SpecRow(QCoreApplication.translate("DetailView", "Seller"), seller_name)
    link = QPushButton(seller_name)
    link.setProperty("variant", "link")
    link.setCursor(Qt.CursorShape.PointingHandCursor)
    link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(matched.url)))
    return SpecRow(QCoreApplication.translate("DetailView", "Seller"), seller_name, widget=link)


def acquisition_rows_plain(watch: Watch) -> list[SpecRow]:
    """Seller and URL as plain text rather than _seller_row/_url_row's
    clickable QPushButton variants -- shared with saat.ui.export's PDF
    renderer (milestone 19), which needs the same field list and order but
    can't embed a clickable widget on a printed page. _acquisition_rows
    below builds on this and swaps in the two link rows for on-screen use.
    Labels are translated here -- safe since _acquisition_rows() below no
    longer inspects row.label to find Seller/URL, it uses the canonical,
    never-translated _ACQUISITION_FIELD_ORDER list instead."""
    a = watch.acquisition
    price = (a.price, a.currency or "") if a.price is not None else None
    target_price = (a.target_price, a.currency or "") if a.target_price is not None else None
    return [
        spec_row(QCoreApplication.translate("DetailView", "Acquired"), a.date, fmt_date, numeric=True),
        spec_row(QCoreApplication.translate("DetailView", "Price"), price, fmt_price, numeric=True),
        spec_row(QCoreApplication.translate("DetailView", "Target Price"), target_price, fmt_price, numeric=True),
        spec_row(QCoreApplication.translate("DetailView", "Target Date"), a.target_date, fmt_date, numeric=True),
        spec_row(QCoreApplication.translate("DetailView", "Seller"), a.seller),
        spec_row(QCoreApplication.translate("DetailView", "URL"), a.url),
        spec_row(QCoreApplication.translate("DetailView", "Condition"), a.condition, enum_label),
        spec_row(QCoreApplication.translate("DetailView", "Box & Papers"), a.box_and_papers, fmt_bool),
        spec_row(QCoreApplication.translate("DetailView", "Warranty Until"), a.warranty_until, fmt_date, numeric=True),
    ]


# Milestone 21: the field order acquisition_rows_plain() builds in, kept as
# its own canonical (never-translated) list so _acquisition_rows() below can
# swap in the clickable Seller/URL rows by *position* rather than by
# inspecting row.label -- once labels are translated, row.label no longer
# equals "Seller"/"URL", so a label-string comparison would silently stop
# matching under any non-English UI and the link rows would never render.
_ACQUISITION_FIELD_ORDER = [
    "Acquired", "Price", "Target Price", "Target Date", "Seller", "URL",
    "Condition", "Box & Papers", "Warranty Until",
]


def _acquisition_rows(watch: Watch, sellers: list[Seller] | None = None) -> list[SpecRow]:
    a = watch.acquisition
    rows = acquisition_rows_plain(watch)
    for i, field in enumerate(_ACQUISITION_FIELD_ORDER):
        if field == "Seller":
            rows[i] = _seller_row(a.seller, sellers or [])
        elif field == "URL":
            rows[i] = _url_row(a.url)
    return rows


# --- Maintenance -----------------------------------------------------------

def maintenance_rows(watch: Watch) -> list[SpecRow]:
    m = watch.maintenance
    return [
        spec_row(QCoreApplication.translate("DetailView", "Service Interval"), m.service_interval_years, lambda v: fmt_number(v, " y"), numeric=True),
        spec_row(QCoreApplication.translate("DetailView", "Battery Due"), m.battery_due, fmt_date, numeric=True),
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
    title_parts = [p for p in (enum_label(strap.material) if strap.material else None, strap.colour) if p]
    title = QLabel(" · ".join(title_parts) if title_parts else EM_DASH)
    title.setProperty("class", "strap-title")
    text_col.addWidget(title)

    detail_parts = []
    if strap.width_mm is not None:
        detail_parts.append(fmt_number(strap.width_mm, " mm"))
    if strap.clasp:
        detail_parts.append(enum_label(strap.clasp))
    detail = QLabel(" · ".join(detail_parts) if detail_parts else EM_DASH)
    detail.setProperty("muted", True)
    text_col.addWidget(detail)

    row.addLayout(text_col, 1)

    if strap.fitted:
        # .upper() would be redundant here since the source text is already
        # uppercase -- no Commit C casing concern for this one literal.
        badge = QLabel(QCoreApplication.translate("DetailView", "FITTED"))
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
    layout.addWidget(MinuteTrackHeader(QCoreApplication.translate("DetailView", "Straps")))
    for strap in watch.straps:
        layout.addWidget(_build_strap_card(record, strap))
    return container


def _build_strap_compat_entry(match: CompatibleStrap) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    owner = QLabel(f"{match.record.watch.brand} {match.record.watch.model}")  # user data, not translatable
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
    layout.addWidget(MinuteTrackHeader(QCoreApplication.translate("DetailView", "Compatible Straps")))
    for match in matches:
        layout.addWidget(_build_strap_compat_entry(match))
    return container


# --- Log: chronological, newest first --------------------------------------

def _build_log_row(entry: LogEntry) -> QWidget:
    row = QWidget()
    layout = QVBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)

    header_parts = [p for p in (fmt_date(entry.date) if entry.date else None, enum_label(entry.kind) if entry.kind else None) if p]
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
    layout.addWidget(MinuteTrackHeader(QCoreApplication.translate("DetailView", "Log")))
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
        enum_label(entry.position) if entry.position else None,
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
    layout.addWidget(MinuteTrackHeader(QCoreApplication.translate("DetailView", "Timing")))

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
    layout.addWidget(MinuteTrackHeader(QCoreApplication.translate("DetailView", "Notes")))
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
    """Large primary image, thumbnail strip beneath. Clicking either opens
    the full-screen viewer (image_viewer.py) at that photo — choosing a
    different photo as primary is now exclusively an edit-form action
    (SPEC.md §5.7's Images tab), not a read-only detail-view gesture. See
    SPEC.md §5.6."""

    image_activated = Signal(int)

    def __init__(self, record: WatchRecord, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._images = list_images(record)
        self._record = record

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._primary = _Thumbnail()
        self._primary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._primary.setCursor(Qt.CursorShape.PointingHandCursor)
        self._primary.clicked.connect(lambda: self._activate(0))
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
                thumb.clicked.connect(lambda i=index: self._activate(i))
                strip.addWidget(thumb)
            strip.addStretch()
            layout.addLayout(strip)

        self._render_primary(watch=record.watch)

    @property
    def images(self) -> list[Path]:
        return self._images

    def _activate(self, index: int) -> None:
        if self._images:
            self.image_activated.emit(index)

    def _render_primary(self, watch: Watch) -> None:
        max_w, max_h = PRIMARY_IMAGE_MAX
        self._primary.setFixedSize(max_w, max_h)

        pixmap = fit_pixmap(self._images[0], max_w, max_h) if self._images else None

        if pixmap is not None:
            self._primary.setPixmap(pixmap)
        else:
            self._primary.clear()
            self._primary.setProperty("class", "detail-image-placeholder")
            diameter = fmt_number(watch.case.diameter_mm, " mm") if watch.case.diameter_mm is not None else EM_DASH
            lug = fmt_number(watch.case.lug_width_mm, " mm lugs") if watch.case.lug_width_mm is not None else EM_DASH
            self._primary.setText(f"{diameter}\n{lug}")


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
    # Milestone 21 Commit C, not this sweep: three hand-rolled English-only
    # plurals in one string -- needs Qt's %n mechanism (and, since this
    # builds a single QLabel from several counts at once, likely restructured
    # into several self.tr("%n ...", "", n) pieces joined together, not one
    # template string with three independent %n slots).
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
            # Milestone 21 Commit C, not this sweep: strftime("%b") reads the
            # process C locale (always English here, since nothing calls
            # locale.setlocale()) -- replaced by explicit
            # QLocale(<active language>).standaloneMonthName(month,
            # QLocale.FormatType.ShortFormat), never QLocale.system().
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


def _build_header(record: WatchRecord) -> QWidget:
    watch = record.watch
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

    # SPEC.md §6: one hairline identity-colour accent per detail page, this
    # watch's slug_color() -- the same hue the compare view and year view
    # already use for it, just marking identity here rather than linking it
    # to other watches. Identity, never state: unrelated to grid cards or
    # hover, which milestone 16 already owns.
    layout.addWidget(SlugColorBar(record.slug))

    meta_parts = []
    if watch.reference:
        meta_parts.append(QCoreApplication.translate("DetailView", "Ref. {reference}").format(reference=watch.reference))
    # "Translation happens only at display time" applies to every display
    # surface, not only the edit-time combo box -- same enum_label() used by
    # table cells (columns.py) and PDF export.
    if watch.style:
        meta_parts.append(enum_label(watch.style))
    if watch.group:
        meta_parts.append(enum_label(watch.group))
    meta_parts.append(enum_label(watch.status))
    if watch.storage:
        meta_parts.append(QCoreApplication.translate("DetailView", "Storage: {storage}").format(storage=watch.storage))
    if watch.rating is not None:
        meta_parts.append("★" * watch.rating + "☆" * (5 - watch.rating))
    meta = QLabel(" · ".join(meta_parts))
    meta.setProperty("class", "detail-meta")
    meta.setWordWrap(True)
    layout.addWidget(meta)

    if watch.tags:
        tags = QLabel(QCoreApplication.translate("DetailView", "Tags: {tags}").format(tags=fmt_list(watch.tags)))
        tags.setProperty("muted", True)
        tags.setWordWrap(True)
        layout.addWidget(tags)

    if watch.serial:
        serial = QLabel(QCoreApplication.translate("DetailView", "Serial {serial}").format(serial=watch.serial))
        serial.setProperty("muted", True)
        layout.addWidget(serial)

    return container


# --- Hero: primary image composed with the brand/model header --------------

HERO_TEXT_MIN_WIDTH = 320
HERO_TEXT_MAX_WIDTH = 560  # a composed measure, not a column stretched edge-to-edge on a wide window
HERO_TWO_COLUMN_THRESHOLD = PRIMARY_IMAGE_MAX[0] + GROUP_SPACING + HERO_TEXT_MIN_WIDTH


class HeroSection(QWidget):
    """The detail page's opening composition: the primary photo as the
    page's subject, composed beside the brand/model header rather than
    stacked above it as a separate, generic block — image on the left, the
    text column vertically centred beside it, once there's room for both;
    image on top, text beneath, when narrower. Same resize-driven idiom
    SpecGroupsContainer already uses for its own column switch, just with
    this section's own threshold. See SPEC.md §5.6."""

    def __init__(self, record: WatchRecord, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.gallery = ImageGallery(record)
        self._header = _build_header(record)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(GROUP_SPACING)
        self._layout.setVerticalSpacing(GROUP_SPACING)
        self._columns: int | None = None
        self._relayout()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self) -> None:
        columns = 2 if self.width() >= HERO_TWO_COLUMN_THRESHOLD else 1
        if columns == self._columns:
            return
        self._columns = columns

        self._layout.removeWidget(self.gallery)
        self._layout.removeWidget(self._header)
        if columns == 2:
            self._header.setMaximumWidth(HERO_TEXT_MAX_WIDTH)
            self._layout.addWidget(self.gallery, 0, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            self._layout.addWidget(self._header, 0, 1, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self._layout.setColumnStretch(0, 0)
            self._layout.setColumnStretch(1, 1)
        else:
            self._header.setMaximumWidth(16777215)  # Qt's own QWIDGETSIZE_MAX -- lift the two-column cap back off
            self._layout.addWidget(self.gallery, 0, 0, Qt.AlignmentFlag.AlignLeft)
            self._layout.addWidget(self._header, 1, 0)
            self._layout.setColumnStretch(0, 1)
            self._layout.setColumnStretch(1, 0)


class DetailView(QScrollArea):
    """A watch's detail page: opens in the main area with a back affordance,
    not a modal. See SPEC.md §5.6."""

    back_requested = Signal()
    edit_requested = Signal(object)
    delete_requested = Signal(object)
    wore_today_requested = Signal(object)
    move_to_owned_requested = Signal(object)
    image_viewer_requested = Signal(object, int)  # list[Path], start index

    def __init__(
        self,
        record: WatchRecord,
        all_records: list[WatchRecord] | None = None,
        parent: QWidget | None = None,
        sellers: list[Seller] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._record = record
        self._all_records = all_records if all_records is not None else [record]
        self._sellers = sellers or []
        watch = record.watch

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        layout.setSpacing(GROUP_SPACING)

        back_button = QPushButton(self.tr("Back"))
        back_button.setObjectName("back-button")
        back_button.setProperty("variant", "link")
        back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        icons.set_icon(back_button, "back")
        back_button.clicked.connect(self.back_requested.emit)
        layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignLeft)

        maintenance_text = maintenance_due_text(watch)
        if maintenance_text is not None:
            maintenance_line = QLabel(maintenance_text)
            maintenance_line.setObjectName("maintenance-due-line")
            maintenance_line.setProperty("class", "maintenance-due-line")
            layout.addWidget(maintenance_line)

        hero = HeroSection(record)
        hero.gallery.image_activated.connect(lambda index: self.image_viewer_requested.emit(hero.gallery.images, index))
        layout.addWidget(hero)

        wear_section = build_wear_section(watch)
        if wear_section is not None:
            layout.addWidget(wear_section)

        wore_today_button = QPushButton(self.tr("Wore this today"))
        icons.set_icon(wore_today_button, "wore-today")
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

        if record.watch.status == "Wishlist":
            # SPEC.md §5.12: one action, no dialog — not "primary"-styled,
            # since SPEC.md §5.1 reserves that weight for "Add watch" alone.
            mark_owned_button = QPushButton(self.tr("Mark as Owned"))
            mark_owned_button.clicked.connect(lambda: self.move_to_owned_requested.emit(record))
            row_layout.addWidget(mark_owned_button)

        edit_button = QPushButton(self.tr("Edit"))
        icons.set_icon(edit_button, "edit")
        edit_button.clicked.connect(lambda: self.edit_requested.emit(record))
        row_layout.addWidget(edit_button)

        delete_button = QPushButton(self.tr("Delete"))
        delete_button.setProperty("variant", "destructive")
        icons.set_icon(delete_button, "delete", color_role="text")
        delete_button.clicked.connect(lambda: self.delete_requested.emit(record))
        row_layout.addWidget(delete_button)

        return row

    def _build_spec_groups(self, record: WatchRecord) -> list[QWidget]:
        watch = record.watch
        # These group titles are a separate, independently-maintained set
        # from columns.py's GROUP_ORDER (registered under context "Columns")
        # -- same English words in places, but translating one does not
        # cover the other, so each gets its own "DetailView"-context entry.
        candidates = [
            build_spec_group(self.tr("Movement"), movement_rows(watch)),
            build_spec_group(self.tr("Case"), case_rows(watch)),
            build_spec_group(self.tr("Dial"), dial_rows(watch)),
            _build_straps_group(record),
            _build_strap_compat_group(record, self._all_records),
            build_spec_group(self.tr("Acquisition"), _acquisition_rows(watch, self._sellers)),
            build_spec_group(self.tr("Maintenance"), maintenance_rows(watch)),
            _build_log_group(watch),
            _build_timing_group(watch),
            _build_notes_group(watch),
        ]
        return [group for group in candidates if group is not None]
