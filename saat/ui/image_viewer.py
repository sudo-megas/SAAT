from pathlib import Path

from PySide6.QtCore import QPointF, QSize, QSizeF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent, QPixmap, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import QWidget

from saat.ui import theme
from saat.ui.images import load_oriented_original
from saat.ui.theme import SIZE_SM, resolve_fonts

MIN_ZOOM = 0.05
MAX_ZOOM = 8.0
ZOOM_STEP = 1.1
INDICATOR_MARGIN = 16


def compute_fit_scale(image_size: QSize, viewport_size: QSize) -> float:
    """The scale that fits image_size within viewport_size, preserving aspect
    ratio. May upscale a small image to fill the viewport -- that's what
    "fit to window" means in any image viewer, not just downscaling."""
    if (image_size.width() <= 0 or image_size.height() <= 0
            or viewport_size.width() <= 0 or viewport_size.height() <= 0):
        return 1.0
    return min(viewport_size.width() / image_size.width(), viewport_size.height() / image_size.height())


def clamp_zoom(factor: float) -> float:
    return max(MIN_ZOOM, min(MAX_ZOOM, factor))


def clamp_pan(offset: QPointF, scaled_size: QSizeF, viewport_size: QSize) -> QPointF:
    """Keeps the image from leaving a gap past its own edge in either axis
    once it's larger than the viewport; forces that axis back to 0 (centred)
    once it isn't. This is what makes "drag pans when zoomed in" true without
    a separate zoomed/not-zoomed mode check anywhere else -- an image that
    already fits simply can't be dragged, by construction."""
    def _clamp_axis(value: float, scaled_dim: float, viewport_dim: float) -> float:
        if scaled_dim <= viewport_dim:
            return 0.0
        max_offset = (scaled_dim - viewport_dim) / 2
        return max(-max_offset, min(max_offset, value))

    return QPointF(
        _clamp_axis(offset.x(), scaled_size.width(), viewport_size.width()),
        _clamp_axis(offset.y(), scaled_size.height(), viewport_size.height()),
    )


class ImageViewerOverlay(QWidget):
    """A full-screen, in-window overlay for one watch's gallery -- covers the
    main window rather than opening a second top-level window, since Wayland
    compositors vary in how they handle secondary fullscreen windows. See
    SPEC.md §5.6. Loads the ORIGINAL file (EXIF-orientation corrected, see
    images.load_oriented_original), never the Pillow thumbnail. MainWindow
    owns showing, raising, resizing and closing it -- this widget only knows
    about the gallery it was given."""

    closed = Signal()

    def __init__(self, images: list[Path], start_index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._images = images
        self._index = max(0, min(start_index, len(images) - 1)) if images else 0
        self._fit = True
        self._zoom = 1.0
        self._pan = QPointF(0, 0)
        self._original_cache: dict[int, QPixmap | None] = {}
        self._displayed_cache: tuple[object, QPixmap] | None = None
        self._drag_origin: QPointF | None = None
        self._drag_origin_pan: QPointF | None = None
        self._font = resolve_fonts()["mono"]

    # --- image loading / scaling -------------------------------------------

    def _original(self, index: int) -> QPixmap | None:
        if index not in self._original_cache:
            self._original_cache[index] = load_oriented_original(self._images[index])
        return self._original_cache[index]

    def _current_scale(self, original_size: QSize) -> float:
        return compute_fit_scale(original_size, self.size()) if self._fit else self._zoom

    def _displayed_pixmap(self) -> QPixmap | None:
        original = self._original(self._index)
        if original is None:
            return None
        scale = self._current_scale(original.size())
        key = (self._index, self.width(), self.height(), self._fit, round(scale, 4))
        if self._displayed_cache is not None and self._displayed_cache[0] == key:
            return self._displayed_cache[1]

        target_w = max(1, round(original.width() * scale))
        target_h = max(1, round(original.height() * scale))
        scaled = original.scaled(target_w, target_h, Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
        # Only the latest (index, size, zoom) combination is kept -- the goal
        # is "don't rescale on every paint while nothing has changed", not an
        # ever-growing history across every photo and zoom level ever
        # visited, which would just be a slower memory leak.
        self._displayed_cache = (key, scaled)
        return scaled

    # --- painting -----------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        colors = theme.colors()
        painter.fillRect(self.rect(), QColor(colors.plate))

        if not self._images or self._original(self._index) is None:
            painter.setPen(QColor(colors.text_muted))
            font = QFont(self._font)
            font.setPixelSize(SIZE_SM)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "This photo could not be loaded.")
            painter.end()
            return

        pixmap = self._displayed_pixmap()
        if pixmap is not None:
            scaled_size = QSizeF(pixmap.size())
            self._pan = clamp_pan(self._pan, scaled_size, self.size())
            x = (self.width() - pixmap.width()) / 2 + self._pan.x()
            y = (self.height() - pixmap.height()) / 2 + self._pan.y()
            painter.drawPixmap(QPointF(x, y), pixmap)

        if len(self._images) > 1:
            font = QFont(self._font)
            font.setPixelSize(SIZE_SM)
            painter.setFont(font)
            painter.setPen(QColor(colors.text_muted))
            indicator_rect = self.rect().adjusted(0, 0, -INDICATOR_MARGIN, -INDICATOR_MARGIN)
            text = f"{self._index + 1} / {len(self._images)}"
            painter.drawText(indicator_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, text)

        painter.end()

    # --- navigation -----------------------------------------------------------

    def _navigate(self, delta: int) -> None:
        new_index = self._index + delta
        if not (0 <= new_index < len(self._images)):
            return
        self._index = new_index
        self._fit = True
        self._zoom = 1.0
        self._pan = QPointF(0, 0)
        self.update()

    def _toggle_fit_and_actual_size(self) -> None:
        if self._fit:
            self._fit = False
            self._zoom = 1.0
        else:
            self._fit = True
            self._pan = QPointF(0, 0)
        self.update()

    # --- input -----------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.accept()  # never let this fall through to the DetailView QScrollArea beneath
        delta = event.angleDelta().y()
        if delta == 0 or not self._images:
            return
        original = self._original(self._index)
        if original is None:
            return
        current_scale = self._current_scale(original.size())
        factor = ZOOM_STEP if delta > 0 else 1 / ZOOM_STEP
        self._zoom = clamp_zoom(current_scale * factor)
        self._fit = False
        self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_fit_and_actual_size()
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.position()
            self._drag_origin_pan = QPointF(self._pan)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_origin is not None and self._drag_origin_pan is not None:
            delta = event.position() - self._drag_origin
            self._pan = self._drag_origin_pan + delta
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_origin = None
        self._drag_origin_pan = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.closed.emit()
        elif event.key() == Qt.Key.Key_Left:
            self._navigate(-1)
        elif event.key() == Qt.Key.Key_Right:
            self._navigate(1)
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.update()
