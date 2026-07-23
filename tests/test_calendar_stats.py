import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from datetime import date
from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLabel

from saat.models import Watch
from saat.storage import WatchRecord
from saat.ui import theme
from saat.ui.calendar_stats import PERIOD_LABELS, StatsView, _ChipSwatch, _RotationBar, _RotationRow, _WeekdayCell, _bar_scale
from saat.ui.year_view import slug_color
from saat.wear import PERIOD_ALL_TIME, PERIOD_MONTH, PERIOD_YEAR, compute_period_stats

_app = QApplication.instance() or QApplication([])


def _record(slug: str, brand: str, model: str, worn: list[date] | None = None) -> WatchRecord:
    return WatchRecord(slug=slug, path=Path(f"/nonexistent/{slug}"), watch=Watch(brand=brand, model=model, worn=worn or []))


def _shown(view: StatsView, size=(700, 900)) -> StatsView:
    view.resize(*size)
    view.show()
    QApplication.processEvents()
    return view


def _section_texts(view: StatsView) -> list[str]:
    """Every section heading currently built — identified by objectName, not
    by text case or the spec-row-label class alone, since the weekday strip
    also uses uppercase spec-row-label text (MON/TUE/...) for its own
    per-cell labels."""
    return [label.text() for label in view._sections_container.findChildren(QLabel, "statsSectionHeading")]


class PeriodSwitchingTests(unittest.TestCase):
    def test_defaults_to_this_month(self) -> None:
        view = StatsView()
        self.assertEqual(view._period, PERIOD_MONTH)
        self.assertTrue(view._period_buttons[PERIOD_MONTH].isChecked())

    def test_clicking_a_period_button_switches_period_and_checked_state(self) -> None:
        view = StatsView()
        view.render([_record("a", "Seiko", "A")], today=date(2026, 1, 15))

        view._period_buttons[PERIOD_YEAR].click()

        self.assertEqual(view._period, PERIOD_YEAR)
        self.assertTrue(view._period_buttons[PERIOD_YEAR].isChecked())
        self.assertFalse(view._period_buttons[PERIOD_MONTH].isChecked())

    def test_switching_period_re_renders_from_the_last_given_records(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2025, 6, 1)])
        view = StatsView()
        view.render([record], today=date(2026, 1, 15))
        self.assertEqual(view._sections_container.findChildren(_RotationRow), [])  # nothing this month

        view._period_buttons[PERIOD_ALL_TIME].click()

        rows = view._sections_container.findChildren(_RotationRow)
        self.assertEqual(len(rows), 1)


class SectionVisibilityTests(unittest.TestCase):
    def test_rotation_and_not_worn_are_complementary_when_something_was_worn(self) -> None:
        worn = _record("a", "Seiko", "A", worn=[date(2026, 1, 1)])
        idle = _record("b", "Omega", "B")
        view = StatsView()
        view.render([worn, idle], today=date(2026, 1, 15))

        self.assertEqual(len(view._sections_container.findChildren(_RotationRow)), 1)
        self.assertIn("NOT WORN IN THIS PERIOD", _section_texts(view))

    def test_watches_exist_but_nothing_worn_this_period_hides_rotation_not_not_worn(self) -> None:
        """Confirmed design: per-section hiding. Rotation (and weekday) have
        nothing to show and hide; Not-worn still lists every watch and
        Coverage still reads a real 0%, rather than the whole panel
        switching to an empty state."""
        a = _record("a", "Seiko", "A")
        b = _record("b", "Omega", "B")
        view = StatsView()
        view.render([a, b], today=date(2026, 1, 15))

        headings = _section_texts(view)
        self.assertNotIn("ROTATION", headings)
        self.assertNotIn("WEEKDAY", headings)
        self.assertIn("NOT WORN IN THIS PERIOD", headings)
        self.assertIn("COVERAGE", headings)
        self.assertEqual(view._empty_message.text(), "")  # the quiet whole-panel message is unrelated to this case

    def test_not_worn_hides_when_every_watch_was_worn(self) -> None:
        record = _record("a", "Seiko", "A", worn=[date(2026, 1, 1)])
        view = StatsView()
        view.render([record], today=date(2026, 1, 15))
        self.assertNotIn("NOT WORN IN THIS PERIOD", _section_texts(view))

    def test_weekday_shows_when_at_least_one_weekday_has_data(self) -> None:
        record = _record("a", "Seiko", "A", worn=[date(2026, 1, 5)])  # a Monday
        view = StatsView()
        view.render([record], today=date(2026, 1, 15))
        self.assertIn("WEEKDAY", _section_texts(view))
        chips = view._sections_container.findChildren(_WeekdayCell)
        self.assertEqual(len(chips), 7)

    def test_streaks_hides_when_nothing_was_ever_recorded(self) -> None:
        record = _record("a", "Seiko", "A")
        view = StatsView()
        view.render([record], today=date(2026, 1, 15))
        self.assertNotIn("STREAKS", _section_texts(view))

    def test_streaks_shows_the_run_when_something_was_worn(self) -> None:
        record = _record("a", "Seiko", "A", worn=[date(2026, 1, 1), date(2026, 1, 2)])
        view = StatsView()
        view.render([record], today=date(2026, 1, 15))
        self.assertIn("STREAKS", _section_texts(view))

    def test_deltas_line_is_absent_for_all_time(self) -> None:
        record = _record("a", "Seiko", "A", worn=[date(2026, 1, 1)])
        view = StatsView()
        view.render([record], today=date(2026, 1, 15))
        view._period_buttons[PERIOD_ALL_TIME].click()
        # Coverage itself still shows; only the "vs. last period" delta line is gone.
        self.assertIn("COVERAGE", _section_texts(view))


class EmptyCollectionTests(unittest.TestCase):
    def test_zero_records_shows_the_quiet_message_and_hides_sections(self) -> None:
        view = _shown(StatsView())
        view.render([], today=date(2026, 1, 15))
        QApplication.processEvents()
        self.assertTrue(view._empty_message.isVisible())
        self.assertFalse(view._sections_container.isVisible())
        self.assertNotEqual(view._empty_message.text(), "")

    def test_all_malformed_records_is_treated_as_empty(self) -> None:
        broken = WatchRecord(slug="broken", path=Path("/nonexistent/broken"), watch=None, load_error="bad toml")
        view = _shown(StatsView())
        view.render([broken], today=date(2026, 1, 15))
        QApplication.processEvents()
        self.assertTrue(view._empty_message.isVisible())
        self.assertFalse(view._sections_container.isVisible())

    def test_a_populated_collection_hides_the_quiet_message(self) -> None:
        view = _shown(StatsView())
        view.render([_record("a", "Seiko", "A")], today=date(2026, 1, 15))
        QApplication.processEvents()
        self.assertFalse(view._empty_message.isVisible())
        self.assertTrue(view._sections_container.isVisible())


class RotationBarPixelTests(unittest.TestCase):
    """Pixel-sampled per the milestone's explicit ask, in both theme modes —
    not eyeballed. Widths are read back after an explicit resize/show rather
    than assumed, since _RotationBar only sets a *minimum* width."""

    def tearDown(self) -> None:
        theme.set_mode(theme.MODE_DARK)

    def test_bar_fill_and_tick_land_at_the_expected_offsets(self) -> None:
        for mode in (theme.MODE_DARK, theme.MODE_LIGHT):
            theme.set_mode(mode)
            with self.subTest(mode=mode):
                # days_worn (8/10) and even_split (3/10) deliberately differ, so the
                # fill edge (80%) and tick (30%) land at different offsets. A tick
                # miscomputed from days_worn instead of even_split would coincide
                # with the fill edge instead — this fixture is built to catch that.
                bar = _RotationBar(days_worn=8, scale=10.0, even_split=3.0)
                bar.setFixedWidth(200)
                bar.show()
                QApplication.processEvents()
                image = bar.grab().toImage()
                width = bar.width()
                palette = theme.colors()

                mid_y = bar.height() // 2
                fill_edge = round(8 / 10 * width)
                tick_x = round(3 / 10 * width)

                self.assertEqual(image.pixelColor(round(width * 0.5), mid_y).name(), QColor(palette.gilt).name())
                self.assertEqual(image.pixelColor(round(width * 0.7), mid_y).name(), QColor(palette.gilt).name())
                self.assertEqual(image.pixelColor(round(width * 0.9), mid_y).name(), QColor(palette.rule).name())

                # sampled across the FULL widget height: the tick is drawn taller than the bar itself
                for y in (0, mid_y, bar.height() - 1):
                    self.assertEqual(image.pixelColor(tick_x, y).name(), QColor(palette.text_muted).name())
                # and NOT at the fill edge -- pins the tick to even_split, not days_worn
                self.assertNotEqual(image.pixelColor(fill_edge, 0).name(), QColor(palette.text_muted).name())
                bar.close()

    def test_a_zero_day_watch_would_draw_no_fill(self) -> None:
        bar = _RotationBar(days_worn=0, scale=10.0, even_split=None)
        bar.setFixedWidth(200)
        bar.show()
        QApplication.processEvents()
        image = bar.grab().toImage()
        self.assertEqual(image.pixelColor(10, bar.height() // 2).name(), QColor(theme.colors().rule).name())
        bar.close()


class EvenSplitTickAbsenceTests(unittest.TestCase):
    def test_no_tick_pixel_anywhere_when_even_split_is_none(self) -> None:
        """SPEC.md: meaningless with a single watch — even_split_reference()
        already returns None for that case (see test_wear.py); this checks
        the widget honours None by drawing no tick anywhere, not just at
        the position a real tick would have used."""
        bar = _RotationBar(days_worn=5, scale=10.0, even_split=None)
        bar.setFixedWidth(200)
        bar.show()
        QApplication.processEvents()
        image = bar.grab().toImage()
        muted = QColor(theme.colors().text_muted).name()
        found = {image.pixelColor(x, y).name() for x in range(bar.width()) for y in range(bar.height())}
        self.assertNotIn(muted, found)
        bar.close()

    def test_single_watch_collection_produces_no_even_split_reference_end_to_end(self) -> None:
        record = _record("a", "Seiko", "A", worn=[date(2026, 1, 1)])
        view = _shown(StatsView())
        view.render([record], today=date(2026, 1, 15))
        [bar] = view._sections_container.findChildren(_RotationBar)
        self.assertIsNone(bar._even_split)


class BarScaleTests(unittest.TestCase):
    def test_scale_is_at_least_the_top_watchs_days_and_the_even_split(self) -> None:
        a = _record("a", "Seiko", "A", worn=[date(2026, 1, d) for d in range(1, 11)])  # 10 days
        b = _record("b", "Omega", "B", worn=[date(2026, 1, 20)])  # 1 day
        stats = compute_period_stats([a, b], PERIOD_MONTH, today=date(2026, 1, 25))
        scale = _bar_scale(stats)
        self.assertGreaterEqual(scale, 10)
        self.assertGreaterEqual(scale, stats.even_split)
        self.assertLessEqual(scale, stats.period_days)  # never worse than the naive period_days scale

    def test_scale_is_zero_when_rotation_and_even_split_are_both_empty(self) -> None:
        stats = compute_period_stats([], PERIOD_MONTH, today=date(2026, 1, 15))
        self.assertEqual(_bar_scale(stats), 0)


class WeekdayChipColorTests(unittest.TestCase):
    def test_chip_record_matches_the_most_worn_watch(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, 5)])  # a Monday
        view = _shown(StatsView())
        view.render([record], today=date(2026, 1, 15))

        monday_cell = view._sections_container.findChildren(_WeekdayCell)[0]
        [swatch] = monday_cell.findChildren(_ChipSwatch)
        self.assertEqual(swatch._record.slug, "seiko-sarb033")

    def test_an_unowned_weekday_chip_has_no_record(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, 5)])  # only Monday has data
        view = _shown(StatsView())
        view.render([record], today=date(2026, 1, 15))

        sunday_cell = view._sections_container.findChildren(_WeekdayCell)[6]
        [swatch] = sunday_cell.findChildren(_ChipSwatch)
        self.assertIsNone(swatch._record)

    def test_chip_pixel_colour_matches_slug_color(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, 5)])
        view = _shown(StatsView())
        view.render([record], today=date(2026, 1, 15))

        monday_cell = view._sections_container.findChildren(_WeekdayCell)[0]
        [swatch] = monday_cell.findChildren(_ChipSwatch)
        QApplication.processEvents()
        image = swatch.grab().toImage()
        center = swatch.width() // 2, swatch.height() // 2
        self.assertEqual(image.pixelColor(*center).name(), slug_color("seiko-sarb033").name())


class RotationClickThroughTests(unittest.TestCase):
    def test_clicking_a_rotation_row_emits_watch_clicked_with_its_slug(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[date(2026, 1, 1)])
        view = _shown(StatsView())
        view.render([record], today=date(2026, 1, 15))

        [row] = view._sections_container.findChildren(_RotationRow)
        received = []
        view.watch_clicked.connect(received.append)

        row.clicked.emit(row._slug)

        self.assertEqual(received, ["seiko-sarb033"])


class PeriodLabelsTests(unittest.TestCase):
    def test_every_period_constant_has_a_label(self) -> None:
        for period in (PERIOD_MONTH, PERIOD_YEAR, PERIOD_ALL_TIME):
            with self.subTest(period=period):
                self.assertIn(period, PERIOD_LABELS)


if __name__ == "__main__":
    unittest.main()
