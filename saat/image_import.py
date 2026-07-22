import shutil
from pathlib import Path

from PIL import Image, ImageOps

THUMBNAIL_DIR_NAME = ".thumbnails"
THUMBNAIL_MAX_DIMENSION = 640


def thumbnail_path(images_dir: Path, filename: str) -> Path:
    return images_dir / THUMBNAIL_DIR_NAME / filename


def import_image(source: Path, images_dir: Path, filename: str) -> None:
    """Copy `source` into images_dir/filename unchanged, and generate a
    same-named thumbnail derivative under images_dir/.thumbnails/ — the
    Images tab "generates thumbnails with Pillow" per SPEC.md §5.7. The
    original is never modified or re-encoded; only the derivative is."""
    images_dir.mkdir(parents=True, exist_ok=True)
    dest = images_dir / filename
    shutil.copy2(source, dest)
    _write_thumbnail(dest, thumbnail_path(images_dir, filename))


def remove_image(images_dir: Path, filename: str) -> None:
    (images_dir / filename).unlink(missing_ok=True)
    thumbnail_path(images_dir, filename).unlink(missing_ok=True)


def _write_thumbnail(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.thumbnail((THUMBNAIL_MAX_DIMENSION, THUMBNAIL_MAX_DIMENSION), Image.LANCZOS)
        img.save(dest, "JPEG", quality=85)
