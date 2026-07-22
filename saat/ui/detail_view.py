from datetime import date

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QMouseEvent
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
from saat.ui.minute_track import MinuteTrackHeader
from saat.ui.spec_group import SpecRow, build_spec_group, spec_row
from saat.ui.theme import GROUP_SPACING, PAGE_MARGIN

PRIMARY_IMAGE_MAX = (480, 600)
THUMB_SIZE = 72
STRAP_PHOTO_SIZE = 56


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


# --- Timing: sparkline lands in milestone 8; plain readings for now --------

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
    not a modal. See SPEC.md §5.6. Wear stats and the wore-today button land
    in milestone 7."""

    back_requested = Signal()
    edit_requested = Signal(object)
    delete_requested = Signal(object)

    def __init__(self, record: WatchRecord, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

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

        layout.addWidget(_build_header(watch))
        layout.addWidget(ImageGallery(record))

        groups_container = SpecGroupsContainer()
        groups_container.set_groups(self._build_spec_groups(record))
        layout.addWidget(groups_container)

        layout.addWidget(self._build_edit_delete_row(record))

        layout.addStretch()
        self.setWidget(content)

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
            build_spec_group("Acquisition", _acquisition_rows(watch)),
            build_spec_group("Maintenance", _maintenance_rows(watch)),
            _build_log_group(watch),
            _build_timing_group(watch),
            _build_notes_group(watch),
        ]
        return [group for group in candidates if group is not None]
