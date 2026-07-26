import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw
from PySide6.QtCore import QPoint, QPointF, QSize, QSizeF, Qt
from PySide6.QtGui import QColor, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from saat.ui import theme
from saat.ui.image_viewer import (
    MAX_ZOOM,
    MIN_ZOOM,
    ImageViewerOverlay,
    clamp_pan,
    clamp_zoom,
    compute_fit_scale,
)

_app = QApplication.instance() or QApplication([])


def _shown(widget, size=None):
    if size is not None:
        widget.resize(*size)
    widget.show()
    QApplication.processEvents()
    return widget


class ComputeFitScaleTests(unittest.TestCase):
    def test_downscales_to_fit_within_the_viewport(self) -> None:
        self.assertAlmostEqual(compute_fit_scale(QSize(2000, 1000), QSize(1000, 1000)), 0.5)

    def test_upscales_a_small_image_to_fill_the_viewport(self) -> None:
        # limited by the tighter axis: 1000/100=10 wide, 500/100=5 tall
        self.assertAlmostEqual(compute_fit_scale(QSize(100, 100), QSize(1000, 500)), 5.0)

    def test_degenerate_sizes_return_a_safe_default_instead_of_dividing_by_zero(self) -> None:
        self.assertEqual(compute_fit_scale(QSize(0, 0), QSize(100, 100)), 1.0)
        self.assertEqual(compute_fit_scale(QSize(100, 100), QSize(0, 0)), 1.0)


class ClampZoomTests(unittest.TestCase):
    def test_within_bounds_is_unchanged(self) -> None:
        self.assertEqual(clamp_zoom(1.0), 1.0)

    def test_clamps_to_the_minimum(self) -> None:
        self.assertEqual(clamp_zoom(0.0001), MIN_ZOOM)

    def test_clamps_to_the_maximum(self) -> None:
        self.assertEqual(clamp_zoom(1000.0), MAX_ZOOM)


class ClampPanTests(unittest.TestCase):
    def test_an_image_that_fits_is_forced_back_to_centre(self) -> None:
        pan = clamp_pan(QPointF(500, 500), QSizeF(400, 300), QSize(800, 600))
        self.assertEqual(pan, QPointF(0, 0))

    def test_an_oversized_image_is_clamped_to_its_own_edge(self) -> None:
        # scaled 1000x800 in an 800x600 viewport: max offset is (1000-800)/2
        # = 100 horizontally, (800-600)/2 = 100 vertically.
        pan = clamp_pan(QPointF(500, 500), QSizeF(1000, 800), QSize(800, 600))
        self.assertEqual(pan, QPointF(100, 100))

    def test_an_offset_already_within_bounds_is_unchanged(self) -> None:
        pan = clamp_pan(QPointF(20, -10), QSizeF(1000, 800), QSize(800, 600))
        self.assertEqual(pan, QPointF(20, -10))


class ViewerWidgetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-viewer-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _photo(self, name: str, size=(800, 600), color=(90, 70, 40)) -> Path:
        path = self.tmp / name
        Image.new("RGB", size, color).save(path)
        return path

    def _rotated_photo(self, name: str, size=(300, 400)) -> Path:
        """The same recipe confirmed by hand: draw a marker strip at what
        should be the TOP once correctly oriented, physically rotate the
        stored pixels 90 degrees, and tag Orientation=6. A correct reader
        must show the marker back at the top; an uncorrected one shows it
        on a side instead."""
        correct = Image.new("RGB", size, (20, 20, 20))
        ImageDraw.Draw(correct).rectangle([0, 0, size[0], size[1] // 8], fill=(220, 30, 30))
        stored = correct.rotate(90, expand=True)
        exif = Image.Exif()
        exif[0x0112] = 6
        path = self.tmp / name
        stored.save(path, exif=exif.tobytes())
        return path

    def test_missing_file_shows_the_themed_backdrop_and_does_not_raise(self) -> None:
        viewer = _shown(ImageViewerOverlay([self.tmp / "nope.jpg"], 0), size=(400, 300))
        image = viewer.grab().toImage()
        self.assertFalse(image.isNull())
        corner = image.pixelColor(2, 2)
        self.assertEqual(corner.name(), QColor(theme.colors().plate).name())
        viewer.close()

    def test_a_real_photo_renders_without_raising(self) -> None:
        photo = self._photo("a.jpg")
        viewer = _shown(ImageViewerOverlay([photo], 0), size=(400, 300))
        image = viewer.grab().toImage()
        self.assertFalse(image.isNull())
        viewer.close()

    def test_exif_rotated_original_is_corrected_on_load(self) -> None:
        photo = self._rotated_photo("rot.jpg")
        viewer = ImageViewerOverlay([photo], 0)
        original = viewer._original(0)
        self.assertIsNotNone(original)
        image = original.toImage()
        sampled = image.pixelColor(image.width() // 2, 5)
        self.assertGreater(sampled.red(), 180)
        self.assertLess(sampled.blue(), 60)

    def test_navigation_clamps_at_the_ends_rather_than_wrapping(self) -> None:
        photos = [self._photo(f"{i}.jpg") for i in range(3)]
        viewer = ImageViewerOverlay(photos, 0)

        viewer._navigate(-1)
        self.assertEqual(viewer._index, 0)

        viewer._navigate(1)
        viewer._navigate(1)
        self.assertEqual(viewer._index, 2)

        viewer._navigate(1)
        self.assertEqual(viewer._index, 2)

    def test_start_index_out_of_range_is_clamped(self) -> None:
        photos = [self._photo(f"{i}.jpg") for i in range(2)]
        self.assertEqual(ImageViewerOverlay(photos, 99)._index, 1)
        self.assertEqual(ImageViewerOverlay(photos, -5)._index, 0)

    def test_escape_emits_closed(self) -> None:
        viewer = _shown(ImageViewerOverlay([self._photo("a.jpg")], 0), size=(400, 300))
        viewer.setFocus()
        QApplication.processEvents()
        received = []
        viewer.closed.connect(lambda: received.append(True))

        QTest.keyClick(viewer, Qt.Key.Key_Escape)

        self.assertEqual(received, [True])
        viewer.close()

    def test_double_click_toggles_fit_and_actual_size(self) -> None:
        viewer = _shown(ImageViewerOverlay([self._photo("a.jpg", size=(2000, 1500))], 0), size=(400, 300))
        self.assertTrue(viewer._fit)

        QTest.mouseDClick(viewer, Qt.MouseButton.LeftButton)
        self.assertFalse(viewer._fit)
        self.assertEqual(viewer._zoom, 1.0)

        QTest.mouseDClick(viewer, Qt.MouseButton.LeftButton)
        self.assertTrue(viewer._fit)
        viewer.close()

    def test_wheel_up_zooms_in_from_whatever_the_fit_scale_currently_is(self) -> None:
        viewer = _shown(ImageViewerOverlay([self._photo("a.jpg", size=(2000, 1500))], 0), size=(400, 300))
        fit_scale = viewer._current_scale(viewer._original(0).size())

        event = QWheelEvent(
            QPointF(200, 150), QPointF(200, 150), QPoint(0, 0), QPoint(0, 120),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase, False,
        )
        viewer.wheelEvent(event)

        self.assertTrue(event.isAccepted())
        self.assertFalse(viewer._fit)
        self.assertGreater(viewer._zoom, fit_scale)
        viewer.close()

    def test_repeated_display_requests_with_nothing_changed_return_the_identical_pixmap(self) -> None:
        viewer = _shown(ImageViewerOverlay([self._photo("a.jpg", size=(2000, 1500))], 0), size=(400, 300))

        first = viewer._displayed_pixmap()
        second = viewer._displayed_pixmap()
        self.assertIs(first, second)

        viewer.resize(500, 420)
        QApplication.processEvents()
        third = viewer._displayed_pixmap()
        self.assertIsNot(first, third)
        viewer.close()

    def test_renders_in_both_themes_without_error(self) -> None:
        photo = self._photo("a.jpg")
        for mode in (theme.MODE_DARK, theme.MODE_LIGHT):
            theme.set_mode(mode)
            with self.subTest(mode=mode):
                viewer = _shown(ImageViewerOverlay([photo], 0), size=(400, 300))
                self.assertFalse(viewer.grab().toImage().isNull())
                viewer.close()
        theme.set_mode(theme.MODE_DARK)


if __name__ == "__main__":
    unittest.main()
