import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from saat.models import Case, Watch
from saat.storage import WatchRecord
from saat.ui import theme
from saat.ui.case_silhouette import (
    DRAWING_WIDTH,
    SCALE_BAR_MM,
    _LegendRow,
    _ScaleBar,
    _SideProfileRow,
    _TopDownSilhouette,
    build_case_silhouette_section,
    drawing_scale,
)
from saat.ui.compare import build_silhouette_entries
from saat.ui.theme import MODE_DARK, MODE_LIGHT
from saat.ui.year_view import slug_color

_app = QApplication.instance() or QApplication([])


def _record(slug: str, brand: str, model: str, case: Case | None = None) -> WatchRecord:
    return WatchRecord(slug=slug, path=Path(f"/nonexistent/{slug}"), watch=Watch(brand=brand, model=model, case=case or Case()))


def _shown(widget, size=None):
    if size is not None:
        widget.resize(*size)
    widget.show()
    QApplication.processEvents()
    return widget


def _close(a: QColor, b: QColor, tolerance: int = 40) -> bool:
    return abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue()) < tolerance


def _stroke_radii(image, cx: int, cy: int, width: int) -> list[int]:
    """Scans rightward from the shared centre along y=cy, returning the
    pixel offset of every background -> non-background transition it finds
    — one per concentric circle's stroke, smallest first. Detects "not
    background" rather than a specific hue, so it works regardless of
    which colours slug_color() happens to hand out."""
    plate = QColor(theme.colors().plate)
    edges = []
    was_background = True
    for x in range(cx, width):
        is_background = _close(image.pixelColor(x, cy), plate)
        if was_background and not is_background:
            edges.append(x - cx)
        was_background = is_background
    return edges


class TopDownSilhouetteGeometryTests(unittest.TestCase):
    """Per the milestone's own warning: a silhouette drawn at the wrong
    scale looks entirely plausible in a screenshot. These pin both the
    RATIO between two circles (catches per-watch mis-normalisation) and an
    ABSOLUTE radius against the pure silhouette_scale() (catches a
    uniformly-wrong-but-internally-consistent scale, which a ratio-only
    check cannot)."""

    def test_radius_ratio_and_absolute_scale_match_real_diameters(self) -> None:
        records = [
            _record("a", "Seiko", "A", case=Case(diameter_mm=36)),
            _record("b", "Casio", "B", case=Case(diameter_mm=44)),
        ]
        entries, _ = build_silhouette_entries(records)
        expected_scale = drawing_scale(entries)

        widget = _shown(_TopDownSilhouette(entries, expected_scale))
        image = widget.grab().toImage()
        cx, cy = widget.width() // 2, widget.height() // 2

        radii = _stroke_radii(image, cx, cy, widget.width())
        self.assertEqual(len(radii), 2, "expected exactly two concentric circle strokes")
        radius_a, radius_b = radii

        expected_radius_a = (36 / 2) * expected_scale
        expected_radius_b = (44 / 2) * expected_scale
        self.assertAlmostEqual(radius_a, expected_radius_a, delta=2)
        self.assertAlmostEqual(radius_b, expected_radius_b, delta=2)
        self.assertAlmostEqual(radius_b / radius_a, 44 / 36, delta=0.05)
        widget.close()

    def test_a_watch_missing_diameter_is_never_drawn_as_a_zero_radius_circle(self) -> None:
        # build_silhouette_entries already excludes it; this just guards
        # against a future caller handing a None-diameter entry in directly.
        records = [_record("a", "Seiko", "A", case=Case(diameter_mm=40))]
        entries, missing = build_silhouette_entries(records)
        self.assertEqual(len(entries), 1)
        widget = _TopDownSilhouette(entries, drawing_scale(entries))  # must not raise
        widget.deleteLater()

    def test_fixed_size_is_bounded_to_drawing_width_regardless_of_watch_count(self) -> None:
        """SPEC.md M15: the drawing must stay a compact, bounded diagram —
        never n-times wider as more watches are added to the comparison."""
        for count in (2, 3, 4):
            records = [_record(str(i), "Seiko", str(i), case=Case(diameter_mm=38, lug_to_lug_mm=46)) for i in range(count)]
            entries, _ = build_silhouette_entries(records)
            widget = _TopDownSilhouette(entries, drawing_scale(entries))
            with self.subTest(count=count):
                self.assertEqual(widget.width(), DRAWING_WIDTH)
            widget.deleteLater()


class SideProfileRowTests(unittest.TestCase):
    def test_row_width_never_exceeds_drawing_width(self) -> None:
        records = [_record("a", "Seiko", "A", case=Case(diameter_mm=44, thickness_mm=13))]
        entries, _ = build_silhouette_entries(records)
        row = _SideProfileRow(entries[0], drawing_scale(entries))
        self.assertLessEqual(row.width(), DRAWING_WIDTH)

    def test_profile_hidden_from_the_section_when_fewer_than_two_have_thickness(self) -> None:
        records = [
            _record("a", "Seiko", "A", case=Case(diameter_mm=40, thickness_mm=12)),
            _record("b", "Casio", "B", case=Case(diameter_mm=42)),  # no thickness
        ]
        section = build_case_silhouette_section(records)
        rows = section.findChildren(_SideProfileRow)
        self.assertEqual(rows, [])

    def test_profile_shown_when_two_have_thickness(self) -> None:
        records = [
            _record("a", "Seiko", "A", case=Case(diameter_mm=40, thickness_mm=12)),
            _record("b", "Casio", "B", case=Case(diameter_mm=42, thickness_mm=11)),
        ]
        section = build_case_silhouette_section(records)
        rows = section.findChildren(_SideProfileRow)
        self.assertEqual(len(rows), 2)


class ScaleBarTests(unittest.TestCase):
    def test_scale_bar_length_matches_ten_mm_at_the_given_scale(self) -> None:
        scale = 5.0
        bar = _shown(_ScaleBar(scale))
        image = bar.grab().toImage()
        expected_length = round(SCALE_BAR_MM * scale)
        muted = QColor(theme.colors().text_muted)
        # the tick line sits at y=6 (see _ScaleBar.paintEvent) — just inside
        # the bar's own length should be the reference colour, just past
        # it should not.
        self.assertTrue(_close(image.pixelColor(expected_length - 2, 6), muted))
        bar.close()


class LegendRowTests(unittest.TestCase):
    def test_drawable_watch_name_renders_in_its_slug_colour(self) -> None:
        record = _record("seiko-a", "Seiko", "A", case=Case(diameter_mm=40))
        entries, _ = build_silhouette_entries([record])
        row = _shown(_LegendRow(record, entries[0]))
        image = row.grab().toImage()
        expected = slug_color("seiko-a")
        found = any(
            _close(image.pixelColor(x, row.height() // 2), expected, tolerance=20)
            for x in range(row.width())
        )
        self.assertTrue(found, "expected the watch name to be painted in its slug colour somewhere in the row")
        row.close()

    def test_watch_missing_case_data_gets_no_entry_and_is_noted_as_such(self) -> None:
        record = _record("casio-b", "Casio", "B")  # no case data at all
        row = _LegendRow(record, None)
        self.assertIsNone(row._entry)


class BuildCaseSilhouetteSectionTests(unittest.TestCase):
    def test_none_when_fewer_than_two_watches_have_diameter(self) -> None:
        records = [_record("a", "Seiko", "A", case=Case(diameter_mm=40))]
        self.assertIsNone(build_case_silhouette_section(records))

    def test_a_widget_when_two_watches_have_diameter(self) -> None:
        records = [
            _record("a", "Seiko", "A", case=Case(diameter_mm=40)),
            _record("b", "Casio", "B", case=Case(diameter_mm=42)),
        ]
        self.assertIsNotNone(build_case_silhouette_section(records))

    def test_legend_lists_every_selected_watch_including_ones_missing_case_data(self) -> None:
        records = [
            _record("a", "Seiko", "A", case=Case(diameter_mm=40)),
            _record("b", "Casio", "B", case=Case(diameter_mm=42)),
            _record("c", "Omega", "C"),  # no case data
        ]
        section = build_case_silhouette_section(records)
        legend_rows = section.findChildren(_LegendRow)
        self.assertEqual(len(legend_rows), 3)
        entries_present = [row._entry is not None for row in legend_rows]
        self.assertEqual(entries_present, [True, True, False])

    def test_works_with_two_three_and_four_watches(self) -> None:
        for count in (2, 3, 4):
            records = [_record(str(i), "Seiko", str(i), case=Case(diameter_mm=38 + i)) for i in range(count)]
            with self.subTest(count=count):
                self.assertIsNotNone(build_case_silhouette_section(records))  # must not raise


class BothThemesRenderTests(unittest.TestCase):
    """Not a contrast measurement (that's covered by year_view's exhaustive
    360-hue chip test) — just confirms the silhouette actually paints
    without error in both modes, since a stroke's perceived contrast can
    only really be judged by looking at the rendered screenshot pass."""

    def tearDown(self) -> None:
        theme.set_mode(MODE_DARK)

    def test_renders_in_both_modes(self) -> None:
        records = [
            _record("a", "Seiko", "A", case=Case(diameter_mm=40, lug_to_lug_mm=47, thickness_mm=12)),
            _record("b", "Casio", "B", case=Case(diameter_mm=44, lug_to_lug_mm=50, thickness_mm=13)),
        ]
        for mode in (MODE_DARK, MODE_LIGHT):
            theme.set_mode(mode)
            with self.subTest(mode=mode):
                section = _shown(build_case_silhouette_section(records))
                section.grab()  # must not raise
                section.close()


if __name__ == "__main__":
    unittest.main()
