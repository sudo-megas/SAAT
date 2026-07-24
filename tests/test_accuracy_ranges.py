import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLabel

from saat.models import Movement, Watch
from saat.storage import WatchRecord
from saat.ui import theme
from saat.ui.accuracy_ranges import (
    MIN_SPAN_PX,
    _AccuracyAxis,
    _AccuracyRow,
    build_accuracy_section,
)
from saat.ui.compare import AccuracyEntry, build_accuracy_entries

_app = QApplication.instance() or QApplication([])


def _record(slug: str, **kwargs) -> WatchRecord:
    return WatchRecord(slug=slug, path=Path(f"/nonexistent/{slug}"), watch=Watch(brand="B", model=slug, movement=Movement(**kwargs)))


def _entry(slug: str, min_sec_per_day: float, max_sec_per_day: float, original_unit: str = "sec/day") -> AccuracyEntry:
    return AccuracyEntry(
        record=_record(slug),
        min_sec_per_day=min_sec_per_day,
        max_sec_per_day=max_sec_per_day,
        original_min=min_sec_per_day,
        original_max=max_sec_per_day,
        original_unit=original_unit,
    )


def _shown(widget, width=200):
    widget.setFixedWidth(width)
    widget.show()
    QApplication.processEvents()
    return widget


def _close(a: QColor, b: QColor, tolerance: int = 30) -> bool:
    return abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue()) < tolerance


class AccuracyAxisGeometryTests(unittest.TestCase):
    """Pins absolute pixel offsets computed independently from the same
    linear-interpolation formula the widget itself uses, per the
    milestone's warning that a plausible-looking chart can still be
    wrong: the point here is the zero line and span both land exactly
    where accuracy_axis_bounds() + the watch's own min/max say they should."""

    def test_span_and_zero_line_land_at_the_expected_pixels(self) -> None:
        entry = _entry("a", min_sec_per_day=-10, max_sec_per_day=20)
        axis = _shown(_AccuracyAxis(entry, axis_min=-40, axis_max=40, parent=None), width=200)
        image = axis.grab().toImage()
        mid_y = axis.height() // 2

        expected_left = round((-10 - -40) / 80 * 200)   # 75
        expected_right = round((20 - -40) / 80 * 200)   # 150
        expected_zero = round((0 - -40) / 80 * 200)     # 100

        color = theme.colors()
        # inside the span, away from the zero line
        self.assertTrue(_close(image.pixelColor(80, mid_y), _slug_color_of(entry)))
        # the zero line, drawn last, wins over the span fill at that x
        self.assertTrue(_close(image.pixelColor(expected_zero, mid_y), QColor(color.text)))
        # zero line spans the full height, unlike the (narrower) span fill
        self.assertTrue(_close(image.pixelColor(expected_zero, 0), QColor(color.text)))
        self.assertTrue(_close(image.pixelColor(expected_zero, axis.height() - 1), QColor(color.text)))
        # outside the span entirely: background
        self.assertTrue(_close(image.pixelColor(expected_left - 5, mid_y), QColor(color.plate)))
        self.assertTrue(_close(image.pixelColor(expected_right + 5, mid_y), QColor(color.plate)))
        axis.close()

    def test_a_near_zero_span_still_draws_a_visible_minimum_width_sliver(self) -> None:
        """SPEC.md §5.4: quartz renders as a near-invisible hairline — near,
        not literally zero pixels wide, or the insight the visual exists
        to show would be invisible instead of legible."""
        entry = _entry("a", min_sec_per_day=10.0, max_sec_per_day=10.01)  # effectively a point, away from zero
        axis = _shown(_AccuracyAxis(entry, axis_min=-40, axis_max=40, parent=None), width=200)
        image = axis.grab().toImage()
        mid_y = axis.height() // 2
        expected_left = round((10.0 - -40) / 80 * 200)

        found_width = 0
        x = expected_left
        while x < axis.width() and _close(image.pixelColor(x, mid_y), _slug_color_of(entry)):
            found_width += 1
            x += 1
        self.assertGreaterEqual(found_width, MIN_SPAN_PX)
        axis.close()

    def test_a_wide_mechanical_span_is_dramatically_wider_than_a_quartz_one_on_the_same_axis(self) -> None:
        wide = _entry("mech", min_sec_per_day=-20, max_sec_per_day=40)
        narrow = _entry("quartz", min_sec_per_day=-0.5, max_sec_per_day=0.5, original_unit="sec/month")
        axis_min, axis_max = -20.0, 40.0

        wide_axis = _shown(_AccuracyAxis(wide, axis_min, axis_max), width=200)
        narrow_axis = _shown(_AccuracyAxis(narrow, axis_min, axis_max), width=200)
        wide_image, narrow_image = wide_axis.grab().toImage(), narrow_axis.grab().toImage()
        mid_y = wide_axis.height() // 2

        def _measure(image, color) -> int:
            return sum(1 for x in range(200) if _close(image.pixelColor(x, mid_y), color))

        wide_width = _measure(wide_image, _slug_color_of(wide))
        narrow_width = _measure(narrow_image, _slug_color_of(narrow))
        self.assertGreater(wide_width, narrow_width * 10)
        wide_axis.close()
        narrow_axis.close()


def _slug_color_of(entry: AccuracyEntry) -> QColor:
    from saat.ui.year_view import slug_color
    return slug_color(entry.record.slug)


class AccuracyRowTests(unittest.TestCase):
    def test_row_shows_the_original_unconverted_value_and_unit(self) -> None:
        entry = AccuracyEntry(
            record=_record("a"), min_sec_per_day=-0.5, max_sec_per_day=0.5,
            original_min=-15, original_max=15, original_unit="sec/month",
        )
        row = _AccuracyRow(entry, axis_min=-20.0, axis_max=40.0)
        labels = [l.text() for l in row.findChildren(QLabel)]
        self.assertIn("-15/+15 sec/month", labels)


class BuildAccuracySectionTests(unittest.TestCase):
    def test_none_when_fewer_than_two_watches_have_accuracy(self) -> None:
        records = [_record("a", accuracy_min=-10, accuracy_max=20)]
        self.assertIsNone(build_accuracy_section(records))

    def test_a_widget_with_one_row_per_qualifying_watch(self) -> None:
        records = [
            _record("a", accuracy_min=-10, accuracy_max=20),
            _record("b", accuracy_min=-1, accuracy_max=1),
            _record("c"),  # no accuracy data — excluded, not crashing, not counted
        ]
        section = build_accuracy_section(records)
        self.assertIsNotNone(section)
        self.assertEqual(len(section.findChildren(_AccuracyRow)), 2)

    def test_works_with_two_three_and_four_watches(self) -> None:
        for count in (2, 3, 4):
            records = [_record(str(i), accuracy_min=-10 - i, accuracy_max=10 + i) for i in range(count)]
            with self.subTest(count=count):
                self.assertIsNotNone(build_accuracy_section(records))


class BothThemesRenderTests(unittest.TestCase):
    def tearDown(self) -> None:
        theme.set_mode(theme.MODE_DARK)

    def test_renders_in_both_modes(self) -> None:
        records = [
            _record("a", accuracy_min=-20, accuracy_max=40),
            _record("b", accuracy_min=-15, accuracy_max=15, accuracy_unit="sec/month"),
        ]
        for mode in (theme.MODE_DARK, theme.MODE_LIGHT):
            theme.set_mode(mode)
            with self.subTest(mode=mode):
                section = _shown(build_accuracy_section(records), width=400)
                section.grab()  # must not raise
                section.close()


if __name__ == "__main__":
    unittest.main()
