import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import time
import unittest
from pathlib import Path

from PIL import Image
from PySide6.QtWidgets import QApplication

from saat.ui import images

_app = QApplication.instance() or QApplication([])


class CroppedPixmapCacheTests(unittest.TestCase):
    """Milestone 21b: table_view.py's thumbnail delegate calls cropped_pixmap()
    on every paint, so an uncached decode-and-scale per cell would redo real
    work on every repaint. Cached per (path, width, height, mtime) -- the
    mtime component is what's actually under test here: a user's own photo
    can change on disk after being cached once (icons.py's cache, the other
    precedent in this codebase, never needs this because its inputs are
    static bundled SVGs)."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-images-cache-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        images._cropped_pixmap_cache.clear()
        self.addCleanup(images._cropped_pixmap_cache.clear)

    def _make_image(self, name: str, color: tuple[int, int, int]) -> Path:
        path = self.tmp / name
        Image.new("RGB", (40, 40), color).save(path)
        return path

    def test_missing_file_returns_none(self) -> None:
        self.assertIsNone(images.cropped_pixmap(self.tmp / "does-not-exist.jpg", 20, 20))

    def test_repeated_calls_for_a_missing_file_stay_none_and_use_one_cache_entry(self) -> None:
        path = self.tmp / "does-not-exist.jpg"
        images.cropped_pixmap(path, 20, 20)
        images.cropped_pixmap(path, 20, 20)
        self.assertIsNone(images.cropped_pixmap(path, 20, 20))
        self.assertEqual(len(images._cropped_pixmap_cache), 1)

    def test_second_call_for_the_same_unchanged_file_is_a_cache_hit(self) -> None:
        path = self._make_image("photo.jpg", (200, 50, 50))
        first = images.cropped_pixmap(path, 20, 20)
        cache_size_after_first = len(images._cropped_pixmap_cache)

        second = images.cropped_pixmap(path, 20, 20)

        self.assertIs(first, second)  # same cached QPixmap object, not just an equal one
        self.assertEqual(len(images._cropped_pixmap_cache), cache_size_after_first)

    def test_different_width_or_height_gets_its_own_cache_entry(self) -> None:
        path = self._make_image("photo.jpg", (200, 50, 50))
        small = images.cropped_pixmap(path, 20, 20)
        large = images.cropped_pixmap(path, 30, 30)
        self.assertEqual(small.size().toTuple(), (20, 20))
        self.assertEqual(large.size().toTuple(), (30, 30))

    def test_replacing_the_file_on_disk_invalidates_the_cache(self) -> None:
        path = self._make_image("photo.jpg", (200, 50, 50))
        images.cropped_pixmap(path, 20, 20)
        cache_size_after_first = len(images._cropped_pixmap_cache)

        # A real mtime bump, not just new content -- same guarantee the
        # cache key relies on for a real edited-in-place photo.
        time.sleep(0.01)
        Image.new("RGB", (40, 40), (50, 200, 50)).save(path)

        images.cropped_pixmap(path, 20, 20)
        self.assertEqual(len(images._cropped_pixmap_cache), cache_size_after_first + 1)


if __name__ == "__main__":
    unittest.main()
