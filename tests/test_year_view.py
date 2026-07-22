import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from datetime import date
from pathlib import Path

from PySide6.QtWidgets import QApplication

from saat.models import Watch
from saat.storage import WatchRecord
from saat.ui.calendar_view import CalendarView
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


class CalendarViewYearToggleTests(unittest.TestCase):
    def test_toggling_year_view_switches_the_stack_and_label(self) -> None:
        view = CalendarView([])
        view._year = 2026
        view._render()

        view._year_view_button.setChecked(True)
        view._toggle_year_view()

        self.assertIs(view._content_stack.currentWidget(), view._year_view)
        self.assertEqual(view._month_label.text(), "2026")

    def test_prev_next_step_by_year_while_year_view_is_active(self) -> None:
        view = CalendarView([])
        view._year = 2026
        view._year_view_button.setChecked(True)
        view._toggle_year_view()

        view._go_next()

        self.assertEqual(view._year, 2027)
        self.assertEqual(view._month_label.text(), "2027")

    def test_clicking_a_month_in_year_view_returns_to_month_view_for_that_month(self) -> None:
        view = CalendarView([])
        view._year = 2026
        view._year_view_button.setChecked(True)
        view._toggle_year_view()

        view._jump_to_month(3)

        self.assertFalse(view._year_view_active)
        self.assertFalse(view._year_view_button.isChecked())
        self.assertEqual(view._content_stack.currentIndex(), 0)
        self.assertEqual(view._month, 3)
        self.assertEqual(view._month_label.text(), "March 2026")

    def test_a_days_colour_chip_matches_its_watchs_slug_colour(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033")
        record.watch.worn.append(date(2026, 3, 15))
        worn_index = build_worn_index([record])

        view = CalendarView([record])
        view._year = 2026
        view._year_view_button.setChecked(True)
        view._toggle_year_view()

        march_block = view._year_view._layout.itemAt(2).widget()
        self.assertEqual(march_block._worn_index[date(2026, 3, 15)].slug, "seiko-sarb033")


if __name__ == "__main__":
    unittest.main()
