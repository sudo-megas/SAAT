import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from datetime import date
from pathlib import Path

from PySide6.QtWidgets import QApplication

from saat.models import Watch
from saat.storage import WatchRecord
from saat.ui.calendar_stats import StatsView
from saat.ui.calendar_view import CalendarView, _MODE_MONTH, _MODE_STATS, _MODE_YEAR
from saat.ui.year_view import YearView, slug_color
from saat.wear import build_worn_index

_app = QApplication.instance() or QApplication([])


def _record(slug: str, brand: str, model: str) -> WatchRecord:
    return WatchRecord(slug=slug, path=Path(f"/nonexistent/{slug}"), watch=Watch(brand=brand, model=model))


class SlugColorTests(unittest.TestCase):
    def test_same_slug_always_yields_the_same_colour(self) -> None:
        self.assertEqual(slug_color("seiko-sarb033").getRgb(), slug_color("seiko-sarb033").getRgb())

    def test_different_slugs_usually_yield_different_colours(self) -> None:
        self.assertNotEqual(slug_color("seiko-sarb033").getRgb(), slug_color("omega-speedmaster").getRgb())


class YearViewRenderingTests(unittest.TestCase):
    def test_render_builds_twelve_month_blocks(self) -> None:
        view = YearView()
        view.render(2026, {})
        self.assertEqual(view._layout.count(), 12)

    def test_clicking_a_month_block_emits_its_month_number(self) -> None:
        view = YearView()
        view.render(2026, {})
        received = []
        view.month_clicked.connect(received.append)

        block = view._layout.itemAt(2).widget()  # March, per the 4-col row/col layout
        block.clicked.emit(block._month)

        self.assertEqual(received, [3])


class CalendarViewModeToggleTests(unittest.TestCase):
    """The Month/Year/Stats 3-way toggle (Milestone 13 replaced the earlier
    boolean Year-view toggle with this)."""

    def test_switching_to_year_mode_switches_the_stack_and_year_spinbox(self) -> None:
        view = CalendarView([])
        view._year = 2026
        view._render()

        view._set_mode(_MODE_YEAR)

        self.assertIs(view._content_stack.currentWidget(), view._year_view)
        self.assertEqual(view._year_spinbox.value(), 2026)

    def test_switching_to_stats_mode_switches_the_stack(self) -> None:
        view = CalendarView([])
        view._set_mode(_MODE_STATS)
        self.assertIs(view._content_stack.currentWidget(), view._stats_view)
        self.assertIsInstance(view._stats_view, StatsView)

    def test_prev_next_step_by_year_while_year_mode_is_active(self) -> None:
        view = CalendarView([])
        view._year = 2026
        view._set_mode(_MODE_YEAR)

        view._go_next()

        self.assertEqual(view._year, 2027)
        self.assertEqual(view._year_spinbox.value(), 2027)

    def test_clicking_a_month_in_year_view_returns_to_month_mode_for_that_month(self) -> None:
        view = CalendarView([])
        view._year = 2026
        view._set_mode(_MODE_YEAR)

        view._jump_to_month(3)

        self.assertEqual(view._mode, _MODE_MONTH)
        self.assertFalse(view._year_button.isChecked())
        self.assertEqual(view._content_stack.currentIndex(), 0)
        self.assertEqual(view._month, 3)
        self.assertEqual(view._year, 2026)

    def test_a_days_colour_chip_matches_its_watchs_slug_colour(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033")
        record.watch.worn.append(date(2026, 3, 15))
        worn_index = build_worn_index([record])

        view = CalendarView([record])
        view._year = 2026
        view._set_mode(_MODE_YEAR)

        march_block = view._year_view._layout.itemAt(2).widget()
        self.assertEqual(march_block._worn_index[date(2026, 3, 15)].slug, "seiko-sarb033")


if __name__ == "__main__":
    unittest.main()
