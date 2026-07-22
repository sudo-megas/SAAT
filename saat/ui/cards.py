from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from saat.storage import WatchRecord
from saat.ui.images import cropped_pixmap, list_images

# SPEC.md §5.1: four to five cards per row on a 1440p (2560px) display.
CARD_WIDTH = 480
IMAGE_HEIGHT = int(CARD_WIDTH * 5 / 4)  # 4:5 portrait crop
TEXT_BLOCK_HEIGHT = 100
CARD_CONTENT_PADDING = 16  # SPEC.md §6: card padding 16


def _first_image(record: WatchRecord) -> Path | None:
    images = list_images(record)
    return images[0] if images else None


class WatchCard(QFrame):
    """A photo-forward grid card for one watch. See SPEC.md §5.2."""

    activated = Signal(object)  # emits the WatchRecord; only for successfully loaded watches

    def __init__(self, record: WatchRecord, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "watch-card")
        self.setFixedWidth(CARD_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if record.watch is not None:
            layout.addWidget(self._build_image(record))
            layout.addWidget(self._build_info(record))
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self._record = record
        else:
            layout.addWidget(self._build_error(record))
            self._record = None

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._record is not None and event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.activated.emit(self._record)
        super().mouseReleaseEvent(event)

    def _build_image(self, record: WatchRecord) -> QWidget:
        image_path = _first_image(record)
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
        return label

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
