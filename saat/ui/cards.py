import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QCheckBox, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from saat.models import Watch
from saat.storage import WatchRecord
from saat.ui.form_fields import enum_label
from saat.ui.formatting import EM_DASH, fmt_price
from saat.ui import icons, theme
from saat.ui.images import cropped_pixmap, first_image
from saat.ui.maintenance import is_maintenance_due

STAR_FILLED = "★"
STAR_EMPTY = "☆"


def _lerp_color(start: QColor, end: QColor, t: float) -> QColor:
    return QColor(
        round(start.red() + (end.red() - start.red()) * t),
        round(start.green() + (end.green() - start.green()) * t),
        round(start.blue() + (end.blue() - start.blue()) * t),
    )


def _top_rounded_path(rect: QRectF, radius: float) -> QPainterPath:
    """rect, rounded at its top-left/top-right corners only, square at the
    bottom -- for a photo that meets the card's own top corners but sits on
    a plain internal seam (the info block below it) at the bottom."""
    path = QPainterPath()
    path.moveTo(rect.left(), rect.bottom())
    path.lineTo(rect.left(), rect.top() + radius)
    path.quadTo(rect.left(), rect.top(), rect.left() + radius, rect.top())
    path.lineTo(rect.right() - radius, rect.top())
    path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + radius)
    path.lineTo(rect.right(), rect.bottom())
    path.closeSubpath()
    return path


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

# SPEC.md §5.2, milestone 21b: a target width GridView's reflow formula
# aims for -- wider screens get more columns of roughly this size, not
# fewer, bigger cards. WatchCard itself just renders at whatever width
# it's given (the constructor default, and set_render_width() afterward);
# nothing here assumes DEFAULT_CARD_WIDTH is the width actually on
# screen.
DEFAULT_CARD_WIDTH = 210
TEXT_BLOCK_HEIGHT = 120  # bumped from a single-line-title-era 100: the title can now wrap to two lines at a narrow render width
CARD_CONTENT_PADDING = 16  # SPEC.md §6: card padding 16
MAINTENANCE_DOT_SIZE = 10
WORE_TODAY_BAR_HEIGHT = 32
CARD_RADIUS = 4.0  # must match theme.qss's watch-card border-radius: 4px

# theme.qss's watch-card border is 1px at rest, 2px when cursor-focused
# (theme.qss's [cursor-focused="true"] rule) -- but Qt's contentsRect(),
# which QVBoxLayout(self) actually lays children into, is fixed at
# construction/first-polish time and never grows when a later property
# change repaints a wider border (confirmed empirically: set_cursor_focused()
# repolishes the frame but contentsRect() stays put). So every full-bleed
# child below reserves the larger 2px unconditionally, in every state,
# rather than trying to track the live border width -- the alternative
# (re-cropping the photo on every focus toggle) would be both wasteful and
# visibly jumpy. CARD_BORDER_INSET must match that 2px rule's width.
CARD_BORDER_INSET = 2
_QSS_REST_BORDER = 1  # theme.qss's watch-card REST-state border width, already reserved by contentsRect() itself


def _image_height(width: int) -> int:
    return int(width * 5 / 4)  # 4:5 portrait crop, at whatever width the card is currently rendering


class _CardPhoto(QLabel):
    """The card's real photo, corner-clipped to CARD_RADIUS at the top two
    corners only (the bottom edge abuts the info block below -- an internal
    seam, not an outer corner), plus a 1px hairline in rule@ just inside the
    clip. QSS border-radius doesn't clip a QLabel's own pixmap contents (a
    Qt limitation, not a stylesheet gap) -- this bakes the clip into
    paintEvent instead."""

    def __init__(self, pixmap: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = pixmap
        self.setFixedSize(pixmap.size())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setClipPath(_top_rounded_path(QRectF(self.rect()), CARD_RADIUS))
        painter.drawPixmap(0, 0, self._pixmap)
        painter.setClipping(False)

        pen = QPen(QColor(theme.colors().rule))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        inset_rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.drawPath(_top_rounded_path(inset_rect, max(CARD_RADIUS - 0.5, 0.0)))
        painter.end()


class _CardPlaceholder(QLabel):
    """No photo yet: SPEC.md §5.2's placeholder tile, gaining a partial tick
    arc behind the case dimensions -- the minute-track vocabulary borrowed
    for card craft (SPEC.md §6's data-visualisation idiom), not the formal
    signature itself, which stays at exactly its two named locations. Evokes
    a dial's chapter ring even with nothing yet to photograph."""

    def __init__(self, text: str, size: QSize, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "card-placeholder")
        self.setFixedSize(size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText(text)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw_tick_arc(painter)
        painter.end()
        super().paintEvent(event)  # QSS background fill + this label's own centred text, on top of the arc

    def _draw_tick_arc(self, painter: QPainter) -> None:
        # Circle's centre sits well above the visible tile; what shows is a
        # shallow slice of its underside, bowing through the middle of the
        # tile behind the case-dimension text -- the same "chapter ring"
        # read as the minute track, just curved. Direction is outward from
        # this off-screen centre (radially down-and-out), the curved
        # equivalent of the straight track's perpendicular ticks.
        center = QPointF(self.width() / 2, -self.height() * 0.35)
        radius = self.height() * 0.9
        span_degrees = 58
        tick_count = 28

        rule = QColor(theme.colors().rule)
        painter.setPen(QPen(rule, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        arc_path = QPainterPath()
        arc_steps = 48
        for i in range(arc_steps + 1):
            theta = math.radians(-span_degrees / 2 + span_degrees * i / arc_steps)
            point = center + QPointF(math.sin(theta), math.cos(theta)) * radius
            if i == 0:
                arc_path.moveTo(point)
            else:
                arc_path.lineTo(point)
        painter.drawPath(arc_path)

        for i in range(tick_count + 1):
            theta = math.radians(-span_degrees / 2 + span_degrees * i / tick_count)
            direction = QPointF(math.sin(theta), math.cos(theta))
            tick_len = 12 if i % 4 == 0 else 6
            outer = center + direction * radius
            inner = center + direction * (radius - tick_len)
            painter.drawLine(outer, inner)


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

    def __init__(
        self,
        record: WatchRecord,
        compare_selected: bool = False,
        parent: QWidget | None = None,
        render_width: int = DEFAULT_CARD_WIDTH,
    ) -> None:
        super().__init__(parent)
        self.setProperty("class", "watch-card")
        self.setProperty("compare-selected", compare_selected)
        self._render_width = render_width
        self.setFixedWidth(render_width)
        self._hovering = False
        self._checkbox: QCheckBox | None = None
        self._wore_today_bar: QWidget | None = None
        self._wishlist_info_bar: QWidget | None = None
        self._maintenance_dot: _MaintenanceDueDot | None = None
        # Set by _build_image() for a real record, left None for an error
        # card (no image to show) -- set_render_width() branches on this
        # rather than on record.watch, since it's the more direct "was
        # _build_image() ever called for this card" signal.
        self._image_container: QWidget | None = None
        self._photo_label: QLabel | None = None
        self._image_path = None

        # Eased hover lift (SPEC.md §6 motion): QSS has no transition
        # primitive, so border colour and background wash are both repainted
        # by hand, driven by one 0..1 progress float rather than two
        # independently-animated colours. paintEvent always recomputes the
        # actual rule@/gilt@/plate@/plate-high@ values live from the CURRENT
        # theme -- only the progress fraction is cached -- so it self-corrects
        # on a theme toggle without a dedicated refresh hook.
        self._hover_progress = 0.0
        self._hover_animation = QVariantAnimation(self)
        self._hover_animation.setDuration(theme.ANIM_DURATION_MS)
        self._hover_animation.setEasingCurve(theme.ANIM_EASING)
        self._hover_animation.valueChanged.connect(self._on_hover_progress_changed)

        layout = QVBoxLayout(self)
        # contentsRect() already reserves _QSS_REST_BORDER (1px); top up to
        # the full CARD_BORDER_INSET (2px) so full-bleed children never
        # overflow past the border in either the rest or cursor-focused
        # state (see CARD_BORDER_INSET's comment above). Bottom stays 0 --
        # the card's own height isn't pre-fixed the way its width is (no
        # setFixedHeight on WatchCard itself), so it grows to fit its
        # children instead of clipping them; there's no bottom-edge overflow
        # to guard against.
        extra_inset = CARD_BORDER_INSET - _QSS_REST_BORDER
        layout.setContentsMargins(extra_inset, extra_inset, extra_inset, 0)
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
        self._animate_hover_to(1.0)
        self._update_overlay_visibility()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovering = False
        self._animate_hover_to(0.0)
        self._update_overlay_visibility()
        super().leaveEvent(event)

    def _update_overlay_visibility(self) -> None:
        if self._checkbox is not None:
            self._checkbox.setVisible(self._hovering or self._checkbox.isChecked())
        if self._wore_today_bar is not None:
            self._wore_today_bar.setVisible(self._hovering)

    def _set_compare_selected(self, value: bool) -> None:
        if self.property("compare-selected") != value:
            self.setProperty("compare-selected", value)
            self.update()

    def _animate_hover_to(self, target: float) -> None:
        self._hover_animation.stop()
        self._hover_animation.setStartValue(self._hover_progress)
        self._hover_animation.setEndValue(target)
        self._hover_animation.start()

    def _on_hover_progress_changed(self, value: float) -> None:
        self._hover_progress = float(value)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        palette = theme.colors()
        cursor_focused = bool(self.property("cursor-focused"))
        compare_selected = bool(self.property("compare-selected"))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Hover's background wash is only ever visible in the text-block
        # strip below the photo -- the photo/placeholder above is opaque and
        # fully covers the frame's own background, which is exactly right,
        # since hover shouldn't tint an actual photograph. Compare-selection
        # does NOT get a wash of its own: a gilt@ tint visible enough to read
        # as distinct fails text_muted's contrast floor in both themes (see
        # tests/test_theme_contrast.py's CardHoverAndSelectionContrastTests)
        # -- its 2px border and the ever-visible checkbox carry that job
        # instead, neither of which sits behind text.
        if not compare_selected and self._hover_progress > 0.0:
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(self.rect()), CARD_RADIUS, CARD_RADIUS)
            painter.setClipPath(clip)
            wash = QColor(palette.plate_high)
            wash.setAlpha(round(255 * self._hover_progress))
            painter.fillRect(self.rect(), wash)
            painter.setClipping(False)

        # Border precedence: cursor-focus (QSS's own 2px gilt@, drawn for
        # that property already) wins outright and undiminished by anything
        # below; compare-selected is its own static, non-eased treatment,
        # visually distinct from hover's animated one; hover/rest eases
        # continuously between rule@ and gilt@ via _hover_progress.
        if not cursor_focused:
            if compare_selected:
                color = QColor(palette.gilt)
                width = 2.0
            else:
                color = _lerp_color(QColor(palette.rule), QColor(palette.gilt), self._hover_progress)
                width = 1.0
            pen = QPen(color)
            pen.setWidthF(width)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            rect = QRectF(self.rect()).adjusted(width / 2, width / 2, -width / 2, -width / 2)
            painter.drawRoundedRect(rect, CARD_RADIUS, CARD_RADIUS)

        painter.end()

    def _build_image(self, record: WatchRecord, compare_selected: bool) -> QWidget:
        width = self._render_width - 2 * CARD_BORDER_INSET
        image_height = _image_height(width)
        self._image_path = first_image(record)
        pixmap = cropped_pixmap(self._image_path, width, image_height) if self._image_path else None

        if pixmap is not None:
            label: QLabel = _CardPhoto(pixmap)
        else:
            label = _CardPlaceholder(self._placeholder_text(record.watch), QSize(width, image_height))
        self._photo_label = label

        container = QWidget()
        container.setFixedSize(width, image_height)
        self._image_container = container
        label.setParent(container)
        label.move(0, 0)

        # SPEC.md §5.12: a non-Owned watch (Wishlist, Incoming, Sold,
        # Gifted) is never worn and has no maintenance to track yet — both
        # overlays are Owned-only, regardless of which scope this card is
        # currently being rendered in.
        is_owned = record.watch.status == "Owned"

        if is_owned and is_maintenance_due(record.watch):
            self._maintenance_dot = _MaintenanceDueDot(container)
            self._maintenance_dot.move(width - MAINTENANCE_DOT_SIZE - CARD_CONTENT_PADDING, CARD_CONTENT_PADDING)
            self._maintenance_dot.show()

        self._checkbox = QCheckBox(self.tr("Compare"), container)
        self._checkbox.setProperty("class", "card-compare-checkbox")
        self._checkbox.setChecked(compare_selected)
        self._checkbox.move(CARD_CONTENT_PADDING, CARD_CONTENT_PADDING)
        self._checkbox.toggled.connect(lambda checked: self.compare_toggled.emit(record, checked))
        self._checkbox.toggled.connect(lambda _checked: self._update_overlay_visibility())
        self._checkbox.toggled.connect(self._set_compare_selected)
        self._checkbox.setVisible(compare_selected)

        if is_owned:
            self._wore_today_bar = QPushButton(self.tr("Wore this today"), container)
            self._wore_today_bar.setProperty("class", "card-wore-today-bar")
            # Fixed light icon colour, matching the class's own fixed dark
            # scrim (theme.qss) — this overlay sits on an arbitrary photo,
            # not the app's plate, so it doesn't follow the theme toggle.
            self._wore_today_bar.setIcon(icons.icon("wore-today", "#E8E4DC"))
            self._wore_today_bar.setFixedSize(width, WORE_TODAY_BAR_HEIGHT)
            self._wore_today_bar.move(0, image_height - WORE_TODAY_BAR_HEIGHT)
            self._wore_today_bar.clicked.connect(lambda: self.wore_today_requested.emit(record))
            self._wore_today_bar.setVisible(False)
        elif record.watch.status == "Wishlist":
            # Same slot the Wore-today bar occupies for an Owned watch, but
            # always visible rather than hover-only — it's information, not
            # an action — and showing target price + rating instead of a
            # wear affordance that doesn't apply pre-purchase.
            self._wishlist_info_bar = QLabel(_wishlist_info_text(record.watch), container)
            self._wishlist_info_bar.setProperty("class", "card-wishlist-info-bar")
            self._wishlist_info_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._wishlist_info_bar.setFixedSize(width, WORE_TODAY_BAR_HEIGHT)
            self._wishlist_info_bar.move(0, image_height - WORE_TODAY_BAR_HEIGHT)
            self._wishlist_info_bar.show()

        return container

    def _placeholder_text(self, watch: Watch) -> str:
        diameter = f"{watch.case.diameter_mm:g} mm" if watch.case.diameter_mm else "—"
        lug = self.tr("{value:g} mm lugs").format(value=watch.case.lug_width_mm) if watch.case.lug_width_mm else "—"
        return f"{diameter}\n{lug}"

    def set_render_width(self, width: int) -> None:
        """Called by GridView._relayout() on every already-existing card
        when the reflow formula's computed width changes for the current
        layout pass -- cards are reused/repositioned across a resize, not
        recreated (set_records() is the only thing that recreates them),
        so hover/animation state and widget-tree churn stay put across a
        pure window resize."""
        if width == self._render_width:
            return
        self._render_width = width
        self.setFixedWidth(width)

        if self._image_container is None:
            # An error card: _build_image() was never called, there's no
            # image/overlay geometry to redo -- only the frame width above
            # (shared by every card) applies to it.
            return

        content_width = width - 2 * CARD_BORDER_INSET
        image_height = _image_height(content_width)
        self._image_container.setFixedSize(content_width, image_height)

        old_label = self._photo_label
        pixmap = cropped_pixmap(self._image_path, content_width, image_height) if self._image_path else None
        if pixmap is not None:
            new_label: QLabel = _CardPhoto(pixmap)
        else:
            new_label = _CardPlaceholder(self._placeholder_text(self._record.watch), QSize(content_width, image_height))
        new_label.setParent(self._image_container)
        new_label.move(0, 0)
        new_label.lower()  # overlays (checkbox/dot/bars) were parented after the original label -- keep them on top
        new_label.show()
        self._photo_label = new_label
        if old_label is not None:
            old_label.setParent(None)
            old_label.deleteLater()

        if self._maintenance_dot is not None:
            self._maintenance_dot.move(content_width - MAINTENANCE_DOT_SIZE - CARD_CONTENT_PADDING, CARD_CONTENT_PADDING)

        if self._wore_today_bar is not None:
            self._wore_today_bar.setFixedSize(content_width, WORE_TODAY_BAR_HEIGHT)
            self._wore_today_bar.move(0, image_height - WORE_TODAY_BAR_HEIGHT)

        if self._wishlist_info_bar is not None:
            self._wishlist_info_bar.setFixedSize(content_width, WORE_TODAY_BAR_HEIGHT)
            self._wishlist_info_bar.move(0, image_height - WORE_TODAY_BAR_HEIGHT)

        self.updateGeometry()  # forces Qt to recompute the cached sizeHint() the parent FlowLayout reads

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

        meta_parts = [enum_label(p) for p in (watch.style, watch.movement.kind) if p]
        meta = QLabel(" · ".join(meta_parts) if meta_parts else "—")
        meta.setProperty("muted", True)
        meta.setProperty("class", "card-meta")

        layout.addWidget(overline)
        layout.addWidget(title)
        layout.addWidget(meta)
        return container

    def _build_error(self, record: WatchRecord) -> QWidget:
        container = QWidget()
        # Sized to match a real card's initial height at this same
        # construction-time render_width, so it sits at a consistent row
        # height alongside photo cards in the grid. Unlike a photo card,
        # this height is never revisited by set_render_width() (an error
        # card has no _image_container to resize) -- a real, accepted, and
        # narrow gap: only the frame width stays in sync after a resize,
        # not this height, for a card type rare enough (a corrupt
        # watch.toml) that it isn't worth the extra bookkeeping.
        container.setFixedHeight(_image_height(self._render_width - 2 * CARD_BORDER_INSET) + TEXT_BLOCK_HEIGHT)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(CARD_CONTENT_PADDING, CARD_CONTENT_PADDING, CARD_CONTENT_PADDING, CARD_CONTENT_PADDING)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        badge = QLabel(self.tr("⚠ Couldn't load {slug}").format(slug=record.slug))
        badge.setProperty("class", "card-error-badge")
        badge.setWordWrap(True)

        detail = QLabel(record.load_error or "")
        detail.setProperty("muted", True)
        detail.setWordWrap(True)

        layout.addWidget(badge)
        layout.addWidget(detail)
        return container
