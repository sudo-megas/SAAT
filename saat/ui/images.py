from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from saat.storage import WatchRecord

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def list_images(record: WatchRecord) -> list[Path]:
    """Images in a watch's images/ folder, in display order (primary first)."""
    images_dir = record.path / "images"
    if not images_dir.is_dir():
        return []
    return sorted(p for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)


def cropped_pixmap(path: Path, width: int, height: int) -> QPixmap | None:
    """Scaled to fill width x height exactly, centre-cropping the excess."""
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    scaled = pixmap.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation)
    x = max(0, (scaled.width() - width) // 2)
    y = max(0, (scaled.height() - height) // 2)
    return scaled.copy(x, y, width, height)


def fit_pixmap(path: Path, max_width: int, max_height: int) -> QPixmap | None:
    """Scaled to fit within max_width x max_height, preserving aspect ratio."""
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    return pixmap.scaled(max_width, max_height, Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
