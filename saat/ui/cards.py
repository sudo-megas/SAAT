from PySide6.QtCore import QAbstractAnimation, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from saat.models import Watch
from saat.storage import WatchRecord
from saat.ui.formatting import EM_DASH, fmt_price
from saat.ui import icons, theme
from saat.ui.images import cropped_pixmap, first_image
from saat.ui.maintenance import is_maintenance_due

STAR_FILLED = "★"
STAR_EMPTY = "☆"


def _wishlist_info_text(watch: Watch) -> str:
    """SPEC.md §5.12: Wishlist cards show target price and rating (desire)
    instead of wear information — absent values render as an em-dash, same
    convention as everywhere else (SPEC.md §4), never hidden."""
    if watch.acquisition.target_price is not None:
        price = fmt_price((watch.acquisition.target_price, watch.acquisition.currency or ""))
    else:
        price = EM_DASH
    stars = STAR_FILLED * watch.rating + STAR_EMPTY * (5 - watch.rating) if watch.rating is not None else EM_DASH
    return f"{price}  ·  {stars}"

# SPEC.md §5.1: four to five cards per row on a 1440p (2560px) display.
CARD_WIDTH = 480
IMAGE_HEIGHT = int(CARD_WIDTH * 5 / 4)  # 4:5 portrait crop
TEXT_BLOCK_HEIGHT = 100
CARD_CONTENT_PADDING = 16  # SPEC.md §6: card padding 16
MAINTENANCE_DOT_SIZE = 10
WORE_TODAY_BAR_HEIGHT = 32


class _MaintenanceDueDot(QWidget):
    """Small gilt indicator: service overdue or due within 90 days. See
    SPEC.md §4. Absolutely positioned over the card image rather than laid
    out — the image is fixed-size and never reflows, so a one-time move() in
    the parent is simpler than a stacked layout for a single badge."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setProperty("class", "maintenance-due-dot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(MAINTENANCE_DOT_SIZE, MAINTENANCE_DOT_SIZE)


class WatchCard(QFrame):
    """A photo-forward grid card for one watch. See SPEC.md §5.2. Hover
    reveals a compare checkbox (top-left) and a "Wore this today" bar
    (bottom); the maintenance dot (top-right, §4) is independent of hover —
    all three are absolutely positioned over the same fixed-size image, per
    the one overlay layer the card needs rather than three different ones."""

    activated = Signal(object)  # emits the WatchRecord; only for successfully loaded watches
    compare_toggled = Signal(object, bool)  # WatchRecord, checked
    wore_today_requested = Signal(object)  # WatchRecord

    def __init__(self, record: WatchRecord, compare_selected: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "watch-card")
        self.setFixedWidth(CARD_WIDTH)
        self._hovering = False
        self._checkbox: QCheckBox | None = None
        self._wore_today_bar: QWidget | None = None

        # Eased border-colour hover (SPEC.md §6 motion): QSS has no transition
        # primitive, so the rule@->gilt@ hover swap is repainted by hand. The
        # animation only holds a snapshot color while actively running; at
        # rest (the common case) paintEvent reads theme.colors() live, same
        # as every other themed element here, so it self-corrects on a theme
        # toggle without a dedicated refresh hook.
        self._border_color: QColor | None = None
        self._border_animation = QVariantAnimation(self)
        self._border_animation.setDuration(theme.ANIM_DURATION_MS)
        self._border_animation.setEasingCurve(theme.ANIM_EASING)
        self._border_animation.valueChanged.connect(self._on_border_color_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if record.watch is not None:
            layout.addWidget(self._build_image(record, compare_selected))
            layout.addWidget(self._build_info(record))
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self._record = record
        else:
            layout.addWidget(self._build_error(record))
            self._record = None

    @property
    def record(self) -> WatchRecord | None:
        return self._record

    def set_cursor_focused(self, value: bool) -> None:
        if self.property("cursor-focused") != value:
            self.setProperty("cursor-focused", value)
            self.style().unpolish(self)
            self.style().polish(self)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._record is not None and event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.activated.emit(self._record)
        super().mouseReleaseEvent(event)

    def enterEvent(self, event) -> None:
        self._hovering = True
        self._animate_border_to(theme.colors().gilt)
        self._update_overlay_visibility()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovering = False
        self._animate_border_to(theme.colors().rule)
        self._update_overlay_visibility()
        super().leaveEvent(event)

    def _update_overlay_visibility(self) -> None:
        if self._checkbox is not None:
            self._checkbox.setVisible(self._hovering or self._checkbox.isChecked())
        if self._wore_today_bar is not None:
            self._wore_today_bar.setVisible(self._hovering)

    def _animate_border_to(self, target_hex: str) -> None:
        current = self._border_color if self._border_color is not None else QColor(theme.colors().rule)
        self._border_animation.stop()
        self._border_animation.setStartValue(current)
        self._border_animation.setEndValue(QColor(target_hex))
        self._border_animation.start()

    def _on_border_color_changed(self, value: QColor) -> None:
        self._border_color = QColor(value)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        # Cursor-focus (keyboard grid navigation) already draws its own 2px
        # gilt@ border in QSS -- that state wins outright, undiminished by
        # whatever hover border color this card happens to be mid-animating.
        if self.property("cursor-focused"):
            return

        if self._border_animation.state() == QAbstractAnimation.State.Running:
            color = self._border_color if self._border_color is not None else QColor(theme.colors().rule)
        else:
            color = QColor(theme.colors().gilt if self._hovering else theme.colors().rule)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(color)
        pen.setWidthF(1.0)
        painter.setPen(pen)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.drawRoundedRect(rect, 4, 4)

    def _build_image(self, record: WatchRecord, compare_selected: bool) -> QWidget:
        image_path = first_image(record)
        pixmap = cropped_pixmap(image_path, CARD_WIDTH, IMAGE_HEIGHT) if image_path else None

        label = QLabel()
        label.setFixedSize(CARD_WIDTH, IMAGE_HEIGHT)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if pixmap is not None:
            label.setPixmap(pixmap)
        else:
            label.setProperty("class", "card-placeholder")
            watch = record.watch
            diameter = f"{watch.case.diameter_mm:g} mm" if watch.case.diameter_mm else "—"
            lug = f"{watch.case.lug_width_mm} mm lugs" if watch.case.lug_width_mm else "—"
            label.setText(f"{diameter}\n{lug}")

        container = QWidget()
        container.setFixedSize(CARD_WIDTH, IMAGE_HEIGHT)
        label.setParent(container)
        label.move(0, 0)

        # SPEC.md §5.12: a non-Owned watch (Wishlist, Incoming, Sold,
        # Gifted) is never worn and has no maintenance to track yet — both
        # overlays are Owned-only, regardless of which scope this card is
        # currently being rendered in.
        is_owned = record.watch.status == "Owned"

        if is_owned and is_maintenance_due(record.watch):
            dot = _MaintenanceDueDot(container)
            dot.move(CARD_WIDTH - MAINTENANCE_DOT_SIZE - CARD_CONTENT_PADDING, CARD_CONTENT_PADDING)
            dot.show()

        self._checkbox = QCheckBox("Compare", container)
        self._checkbox.setProperty("class", "card-compare-checkbox")
        self._checkbox.setChecked(compare_selected)
        self._checkbox.move(CARD_CONTENT_PADDING, CARD_CONTENT_PADDING)
        self._checkbox.toggled.connect(lambda checked: self.compare_toggled.emit(record, checked))
        self._checkbox.toggled.connect(lambda _checked: self._update_overlay_visibility())
        self._checkbox.setVisible(compare_selected)

        if is_owned:
            self._wore_today_bar = QPushButton("Wore this today", container)
            self._wore_today_bar.setProperty("class", "card-wore-today-bar")
            # Fixed light icon colour, matching the class's own fixed dark
            # scrim (theme.qss) — this overlay sits on an arbitrary photo,
            # not the app's plate, so it doesn't follow the theme toggle.
            self._wore_today_bar.setIcon(icons.icon("wore-today", "#E8E4DC"))
            self._wore_today_bar.setFixedSize(CARD_WIDTH, WORE_TODAY_BAR_HEIGHT)
            self._wore_today_bar.move(0, IMAGE_HEIGHT - WORE_TODAY_BAR_HEIGHT)
            self._wore_today_bar.clicked.connect(lambda: self.wore_today_requested.emit(record))
            self._wore_today_bar.setVisible(False)
        elif record.watch.status == "Wishlist":
            # Same slot the Wore-today bar occupies for an Owned watch, but
            # always visible rather than hover-only — it's information, not
            # an action — and showing target price + rating instead of a
            # wear affordance that doesn't apply pre-purchase.
            info_bar = QLabel(_wishlist_info_text(record.watch), container)
            info_bar.setProperty("class", "card-wishlist-info-bar")
            info_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info_bar.setFixedSize(CARD_WIDTH, WORE_TODAY_BAR_HEIGHT)
            info_bar.move(0, IMAGE_HEIGHT - WORE_TODAY_BAR_HEIGHT)
            info_bar.show()

        return container

    def _build_info(self, record: WatchRecord) -> QWidget:
        watch = record.watch
        container = QWidget()
        container.setFixedHeight(TEXT_BLOCK_HEIGHT)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(CARD_CONTENT_PADDING, CARD_CONTENT_PADDING, CARD_CONTENT_PADDING, CARD_CONTENT_PADDING)
        layout.setSpacing(4)

        overline = QLabel(watch.brand.upper())
        overline.setProperty("class", "card-overline")

        title = QLabel(watch.model)
        title.setProperty("class", "card-title")
        title.setWordWrap(True)

        meta_parts = [p for p in (watch.style, watch.movement.kind) if p]
        meta = QLabel(" · ".join(meta_parts) if meta_parts else "—")
        meta.setProperty("muted", True)
        meta.setProperty("class", "card-meta")

        layout.addWidget(overline)
        layout.addWidget(title)
        layout.addWidget(meta)
        return container

    def _build_error(self, record: WatchRecord) -> QWidget:
        container = QWidget()
        container.setFixedHeight(IMAGE_HEIGHT + TEXT_BLOCK_HEIGHT)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(CARD_CONTENT_PADDING, CARD_CONTENT_PADDING, CARD_CONTENT_PADDING, CARD_CONTENT_PADDING)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        badge = QLabel(f"⚠ Couldn't load {record.slug}")
        badge.setProperty("class", "card-error-badge")
        badge.setWordWrap(True)

        detail = QLabel(record.load_error or "")
        detail.setProperty("muted", True)
        detail.setWordWrap(True)

        layout.addWidget(badge)
        layout.addWidget(detail)
        return container
