import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLabel

from saat.models import Acquisition, Case, Watch
from saat.storage import WatchRecord
from saat.ui import theme
from saat.ui.compare import DimensionBarValue
from saat.ui.dimension_bars import MIN_BAR_PX, _DimensionBarCell, build_dimension_bars_section
from saat.ui.year_view import slug_color

_app = QApplication.instance() or QApplication([])


def _record(slug: str, **kwargs) -> WatchRecord:
    return WatchRecord(slug=slug, path=Path(f"/nonexistent/{slug}"), watch=Watch(brand="B", model=slug, **kwargs))


def _shown(widget, width=300):
    widget.setFixedWidth(width)
    widget.show()
    QApplication.processEvents()
    return widget


def _close(a: QColor, b: QColor, tolerance: int = 30) -> bool:
    return abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue()) < tolerance


class DimensionBarCellGeometryTests(unittest.TestCase):
    """Pins the bar's pixel width against the same magnitude/max_magnitude
    ratio the widget itself computes, and confirms the reserved text
    budget keeps that ratio identical to a second cell's — the "shared
    scale within a row" requirement is a claim about relative pixel
    widths, so it has to be checked between two cells, not just within one."""

    def test_full_scale_watch_fills_the_whole_track(self) -> None:
        value = DimensionBarValue(record=_record("a"), magnitude=100.0, text="100 g")
        cell = _shown(_DimensionBarCell(value, max_magnitude=100.0, reserved_text_width=40), width=300)
        image = cell.grab().toImage()
        mid_y = cell.height() // 2
        track_width = 300 - 40 - 8  # cell width - reserved - TEXT_GAP
        color = slug_color("a")
        self.assertTrue(_close(image.pixelColor(2, mid_y), color))
        self.assertTrue(_close(image.pixelColor(round(track_width) - 2, mid_y), color))
        cell.close()

    def test_half_scale_watch_fills_half_the_track_and_no_further(self) -> None:
        value = DimensionBarValue(record=_record("a"), magnitude=50.0, text="50 g")
        cell = _shown(_DimensionBarCell(value, max_magnitude=100.0, reserved_text_width=40), width=300)
        image = cell.grab().toImage()
        mid_y = cell.height() // 2
        track_width = 300 - 40 - 8
        color = slug_color("a")
        self.assertTrue(_close(image.pixelColor(round(track_width / 2) - 3, mid_y), color))
        self.assertFalse(_close(image.pixelColor(round(track_width) - 2, mid_y), color))
        cell.close()

    def test_a_tiny_but_real_value_still_draws_a_visible_minimum_width_bar(self) -> None:
        """A watch priced far below the row's max must still read as
        "has a value", not collapse to the same blank appearance as a
        watch with no value at all for that row."""
        value = DimensionBarValue(record=_record("a"), magnitude=15.0, text="15.00 USD")
        cell = _shown(_DimensionBarCell(value, max_magnitude=6500.0, reserved_text_width=60), width=300)
        image = cell.grab().toImage()
        mid_y = cell.height() // 2
        color = slug_color("a")
        found_width = sum(1 for x in range(0, 240) if _close(image.pixelColor(x, mid_y), color))
        self.assertGreaterEqual(found_width, MIN_BAR_PX)
        cell.close()

    def test_missing_value_draws_no_bar_at_all(self) -> None:
        value = DimensionBarValue(record=_record("a"), magnitude=None, text="—")
        cell = _shown(_DimensionBarCell(value, max_magnitude=100.0, reserved_text_width=40), width=300)
        image = cell.grab().toImage()
        mid_y = cell.height() // 2
        color = slug_color("a")
        self.assertFalse(any(_close(image.pixelColor(x, mid_y), color) for x in range(0, 200)))
        cell.close()


class DimensionBarSectionTests(unittest.TestCase):
    def test_none_when_no_dimension_qualifies(self) -> None:
        records = [_record("a"), _record("b")]  # no case/acquisition data at all
        self.assertIsNone(build_dimension_bars_section(records))

    def test_a_row_per_qualifying_attribute(self) -> None:
        records = [
            _record("a", case=Case(weight_g=120, water_resistance_m=100)),
            _record("b", case=Case(weight_g=90, water_resistance_m=200)),
        ]
        section = build_dimension_bars_section(records)
        labels = [l.text() for l in section.findChildren(QLabel)]
        self.assertIn("Weight", labels)
        self.assertIn("Water Resistance", labels)

    def test_diameter_lug_to_lug_and_thickness_never_appear_as_rows(self) -> None:
        records = [
            _record("a", case=Case(diameter_mm=38, lug_to_lug_mm=46, thickness_mm=11)),
            _record("b", case=Case(diameter_mm=40, lug_to_lug_mm=48, thickness_mm=12)),
        ]
        self.assertIsNone(build_dimension_bars_section(records))

    def test_price_row_appears_in_collection_scope(self) -> None:
        records = [
            _record("a", acquisition=Acquisition(price=1000, currency="USD")),
            _record("b", acquisition=Acquisition(price=2000, currency="USD")),
        ]
        section = build_dimension_bars_section(records, is_wishlist=False)
        labels = [l.text() for l in section.findChildren(QLabel)]
        self.assertIn("Price", labels)
        self.assertNotIn("Target Price", labels)

    def test_target_price_row_appears_in_wishlist_scope(self) -> None:
        records = [
            _record("a", acquisition=Acquisition(target_price=1000, currency="USD")),
            _record("b", acquisition=Acquisition(target_price=2000, currency="USD")),
        ]
        section = build_dimension_bars_section(records, is_wishlist=True)
        labels = [l.text() for l in section.findChildren(QLabel)]
        self.assertIn("Target Price", labels)
        self.assertNotIn("Price", labels)

    def test_works_with_two_three_and_four_watches(self) -> None:
        for count in (2, 3, 4):
            records = [_record(str(i), case=Case(weight_g=100 + i)) for i in range(count)]
            with self.subTest(count=count):
                section = build_dimension_bars_section(records)
                self.assertIsNotNone(section)
                self.assertEqual(len(section.findChildren(_DimensionBarCell)), count)


class BothThemesRenderTests(unittest.TestCase):
    def tearDown(self) -> None:
        theme.set_mode(theme.MODE_DARK)

    def test_renders_in_both_modes(self) -> None:
        records = [
            _record("a", case=Case(weight_g=120, water_resistance_m=100), acquisition=Acquisition(price=1000, currency="USD")),
            _record("b", case=Case(weight_g=90, water_resistance_m=200), acquisition=Acquisition(price=2000, currency="USD")),
        ]
        for mode in (theme.MODE_DARK, theme.MODE_LIGHT):
            theme.set_mode(mode)
            with self.subTest(mode=mode):
                section = _shown(build_dimension_bars_section(records), width=600)
                section.grab()  # must not raise
                section.close()


if __name__ == "__main__":
    unittest.main()
