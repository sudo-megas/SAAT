import io
from pathlib import Path

from PIL import Image, ImageOps
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


def first_image(record: WatchRecord) -> Path | None:
    """The primary photo (SPEC.md §5.2/§5.6) — first in gallery order, or
    None. Shared by grid cards, the calendar's day cells, and the detail
    page's twelve-month wear strip, so "primary photo" means one thing."""
    images = list_images(record)
    return images[0] if images else None


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


def load_oriented_original(path: Path) -> QPixmap | None:
    """The ORIGINAL file, corrected for EXIF orientation. A bare
    QPixmap(str(path)) never applies EXIF orientation on its own —
    QImageReader.autoTransform() defaults to false — so anything reading the
    original itself (rather than cropped_pixmap's .thumbnails/ derivative,
    already corrected once at generation time by image_import.py's own
    Pillow step) needs the same correction applied at read time instead.
    Shared by fit_pixmap below and the full-screen image viewer, so the fix
    lives in exactly one place. Returns None for a missing or unreadable
    file rather than raising — the caller's job is to show that plainly,
    not crash."""
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            data = buffer.getvalue()
    except (OSError, ValueError):
        return None
    pixmap = QPixmap()
    if not pixmap.loadFromData(data):
        return None
    return pixmap


def load_for_export(path: Path, max_long_edge: int = 1600) -> QPixmap | None:
    """EXIF-corrected and downscaled to at most max_long_edge on its long
    edge, re-encoded as JPEG rather than load_oriented_original's PNG --
    milestone 19's PDF export embeds one of these per watch, and a whole
    collection embedded losslessly at full resolution would make for an
    unreasonably large document. On-screen viewing (the full-screen viewer,
    the detail page) stays lossless via load_oriented_original; only the
    PDF path trades a little quality for file size. Returns None for a
    missing or unreadable file, same as load_oriented_original."""
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            if max(img.width, img.height) > max_long_edge:
                img.thumbnail((max_long_edge, max_long_edge), Image.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            data = buffer.getvalue()
    except (OSError, ValueError):
        return None
    pixmap = QPixmap()
    if not pixmap.loadFromData(data):
        return None
    return pixmap


def fit_pixmap(path: Path, max_width: int, max_height: int) -> QPixmap | None:
    """Scaled to fit within max_width x max_height, preserving aspect ratio.
    Always the original — this is for the detail page's large image."""
    pixmap = load_oriented_original(path)
    if pixmap is None:
        return None
    return pixmap.scaled(max_width, max_height, Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
