import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from datetime import datetime, time
from unittest.mock import patch

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from saat.ui import theme
from saat.ui.watch_dial import (
    DIAL_DIAMETER,
    MARGIN,
    LUG_GAP,
    LUG_HEIGHT,
    MIN_TIMER_INTERVAL_MS,
    PINION_RADIUS,
    WatchDialWidget,
    hand_angles,
    ms_until_next_minute,
)

_app = QApplication.instance() or QApplication([])


def _shown(widget, size=None):
    if size is not None:
        widget.resize(*size)
    widget.show()
    QApplication.processEvents()
    return widget


def _close(a: QColor, b: QColor, tolerance: int = 40) -> bool:
    return abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue()) < tolerance


class HandAnglesTests(unittest.TestCase):
    def test_midnight_both_hands_at_twelve(self) -> None:
        self.assertEqual(hand_angles(time(0, 0)), (0.0, 0.0))

    def test_three_oclock_sharp(self) -> None:
        self.assertEqual(hand_angles(time(3, 0)), (90.0, 0.0))

    def test_six_thirty_hour_hand_drifts_halfway_to_seven(self) -> None:
        self.assertEqual(hand_angles(time(6, 30)), (195.0, 180.0))

    def test_hour_wraps_at_twelve_not_twenty_four(self) -> None:
        self.assertEqual(hand_angles(time(12, 0)), (0.0, 0.0))
        self.assertEqual(hand_angles(time(13, 0)), (30.0, 0.0))

    def test_one_thirty(self) -> None:
        self.assertEqual(hand_angles(time(1, 30)), (45.0, 180.0))


class MsUntilNextMinuteTests(unittest.TestCase):
    def test_exactly_on_the_minute_gives_a_full_sixty_seconds(self) -> None:
        self.assertEqual(ms_until_next_minute(datetime(2024, 1, 1, 12, 0, 0, 0)), 60000)

    def test_half_a_minute_in_gives_thirty_seconds_remaining(self) -> None:
        self.assertEqual(ms_until_next_minute(datetime(2024, 1, 1, 12, 0, 30, 0)), 30000)

    def test_a_millisecond_before_the_boundary_is_clamped_to_the_floor(self) -> None:
        # As close to the boundary as a datetime can represent (59.999999s in)
        # -- the naive computation rounds to ~0ms, which must never be allowed
        # to re-arm a single-shot timer near-instantly.
        result = ms_until_next_minute(datetime(2024, 1, 1, 12, 0, 59, 999999))
        self.assertEqual(result, MIN_TIMER_INTERVAL_MS)

    def test_never_returns_below_the_floor(self) -> None:
        for microsecond in (0, 1, 500_000, 999_999):
            with self.subTest(microsecond=microsecond):
                result = ms_until_next_minute(datetime(2024, 1, 1, 12, 0, 59, microsecond))
                self.assertGreaterEqual(result, MIN_TIMER_INTERVAL_MS)


class TimerLifecycleTests(unittest.TestCase):
    """SPEC.md's own verification demand: the timer must stop when the dial
    isn't visible, checked with an assertion rather than eyeballed."""

    def test_timer_is_not_running_before_the_widget_is_shown(self) -> None:
        widget = WatchDialWidget()
        self.assertFalse(widget._timer.isActive())
        widget.deleteLater()

    def test_show_starts_the_timer_and_hide_stops_it(self) -> None:
        widget = _shown(WatchDialWidget())
        self.assertTrue(widget._timer.isActive())
        widget.hide()
        self.assertFalse(widget._timer.isActive())
        widget.close()

    def test_hiding_then_reshowing_restarts_the_timer(self) -> None:
        widget = _shown(WatchDialWidget())
        widget.hide()
        self.assertFalse(widget._timer.isActive())
        widget.show()
        QApplication.processEvents()
        self.assertTrue(widget._timer.isActive())
        widget.close()


class PaintTests(unittest.TestCase):
    """A fixed, mocked time (03:15, hands well away from the 12 o'clock ring
    point used to sample the chapter ring itself) so every assertion here is
    fully deterministic -- no dependency on when the suite happens to run."""

    FIXED_NOW = datetime(2024, 6, 1, 3, 15, 0, 0)

    def tearDown(self) -> None:
        theme.set_palette("default-dark")

    def _painted(self):
        with patch("saat.ui.watch_dial.datetime") as mock_datetime:
            mock_datetime.now.return_value = self.FIXED_NOW
            widget = _shown(WatchDialWidget())
            image = widget.grab().toImage()
        return widget, image

    def test_renders_in_both_modes_without_error(self) -> None:
        for mode in ("default-dark", "default-light"):
            theme.set_palette(mode)
            with self.subTest(mode=mode):
                widget, image = self._painted()
                self.assertFalse(image.isNull())
                widget.close()

    def test_chapter_ring_is_drawn_in_rule_colour(self) -> None:
        widget, image = self._painted()
        cx = widget.width() / 2
        cy = MARGIN + LUG_HEIGHT + LUG_GAP + DIAL_DIAMETER / 2
        radius = DIAL_DIAMETER / 2
        # The 12 o'clock tick: a radial line from the ring inward, midpoint
        # is solidly on the stroke regardless of antialiasing at either end.
        sample = image.pixelColor(round(cx), round(cy - radius + 4))
        self.assertTrue(_close(sample, QColor(theme.colors().rule)))
        widget.close()

    def test_gilt_appears_only_at_the_centre_pinion(self) -> None:
        widget, image = self._painted()
        gilt = QColor(theme.colors().gilt)
        cx, cy = widget.width() / 2, MARGIN + LUG_HEIGHT + LUG_GAP + DIAL_DIAMETER / 2
        max_allowed_radius = PINION_RADIUS + 2  # antialiasing edge slack
        offenders = []
        for y in range(widget.height()):
            for x in range(widget.width()):
                if _close(image.pixelColor(x, y), gilt, tolerance=60):
                    distance = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                    if distance > max_allowed_radius:
                        offenders.append((x, y, distance))
        self.assertEqual(offenders, [], "gilt must appear only at the centre pinion")
        widget.close()

    def test_pinion_itself_is_gilt(self) -> None:
        widget, image = self._painted()
        cx, cy = round(widget.width() / 2), round(MARGIN + LUG_HEIGHT + LUG_GAP + DIAL_DIAMETER / 2)
        self.assertTrue(_close(image.pixelColor(cx, cy), QColor(theme.colors().gilt)))
        widget.close()

    def test_hour_and_minute_hands_are_drawn_in_text_colour(self) -> None:
        import math

        widget, image = self._painted()
        cx = widget.width() / 2
        cy = MARGIN + LUG_HEIGHT + LUG_GAP + DIAL_DIAMETER / 2
        radius = DIAL_DIAMETER / 2
        hour_angle, minute_angle = hand_angles(self.FIXED_NOW.time())
        text = QColor(theme.colors().text)

        for angle, fraction in ((hour_angle, 0.5 * 0.7), (minute_angle, 0.78 * 0.7)):
            theta = math.radians(angle)
            x = round(cx + math.sin(theta) * radius * fraction)
            y = round(cy - math.cos(theta) * radius * fraction)
            with self.subTest(angle=angle):
                self.assertTrue(_close(image.pixelColor(x, y), text))
        widget.close()


if __name__ == "__main__":
    unittest.main()
