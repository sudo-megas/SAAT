from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QCheckBox, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from saat.storage import WatchRecord
from saat.ui.images import cropped_pixmap, first_image
from saat.ui.maintenance import is_maintenance_due

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
        self._update_overlay_visibility()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovering = False
        self._update_overlay_visibility()
        super().leaveEvent(event)

    def _update_overlay_visibility(self) -> None:
        if self._checkbox is not None:
            self._checkbox.setVisible(self._hovering or self._checkbox.isChecked())
        if self._wore_today_bar is not None:
            self._wore_today_bar.setVisible(self._hovering)

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

        if is_maintenance_due(record.watch):
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

        self._wore_today_bar = QPushButton("Wore this today", container)
        self._wore_today_bar.setProperty("class", "card-wore-today-bar")
        self._wore_today_bar.setFixedSize(CARD_WIDTH, WORE_TODAY_BAR_HEIGHT)
        self._wore_today_bar.move(0, IMAGE_HEIGHT - WORE_TODAY_BAR_HEIGHT)
        self._wore_today_bar.clicked.connect(lambda: self.wore_today_requested.emit(record))
        self._wore_today_bar.setVisible(False)

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
