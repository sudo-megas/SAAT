from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from saat.image_import import THUMBNAIL_DIR_NAME
from saat.storage import WatchRecord

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def list_images(record: WatchRecord) -> list[Path]:
    """Images in a watch's images/ folder, in display order (primary first).
    Order follows watch.images when present (SPEC.md's data model table
    doesn't cover gallery order; see the field's docstring in models.py) —
    any file not listed there, or every file for a watch.toml written before
    this field existed, falls back to alphabetical order after it."""
    images_dir = record.path / "images"
    if not images_dir.is_dir():
        return []
    on_disk = {p.name: p for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS}

    ordered_names = record.watch.images if record.watch is not None else []
    ordered = [on_disk[name] for name in ordered_names if name in on_disk]
    remaining = sorted(p for name, p in on_disk.items() if name not in ordered_names)
    return ordered + remaining


def cropped_pixmap(path: Path, width: int, height: int) -> QPixmap | None:
    """Scaled to fill width x height exactly, centre-cropping the excess.
    Prefers the cached thumbnail derivative when one exists — grid cards and
    gallery strips only ever need a small crop, not the full original."""
    thumbnail = path.parent / THUMBNAIL_DIR_NAME / path.name
    source = thumbnail if thumbnail.exists() else path

    pixmap = QPixmap(str(source))
    if pixmap.isNull():
        return None
    scaled = pixmap.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation)
    x = max(0, (scaled.width() - width) // 2)
    y = max(0, (scaled.height() - height) // 2)
    return scaled.copy(x, y, width, height)


def fit_pixmap(path: Path, max_width: int, max_height: int) -> QPixmap | None:
    """Scaled to fit within max_width x max_height, preserving aspect ratio.
    Always the original — this is for the detail page's large image."""
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    return pixmap.scaled(max_width, max_height, Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
