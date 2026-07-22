import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from saat.models import Watch
from saat.storage import WatchRecord
from saat.ui import theme
from saat.ui.calendar_view import CalendarView, _DayCell
from saat.ui.month_grid import GridDay
from saat.ui.watch_picker import WatchPicker

_app = QApplication.instance() or QApplication([])


def _record(slug: str, brand: str, model: str, worn: list[date] | None = None) -> WatchRecord:
    return WatchRecord(slug=slug, path=Path(f"/nonexistent/{slug}"), watch=Watch(brand=brand, model=model, worn=worn or []))


class CalendarViewRenderingTests(unittest.TestCase):
    def test_defaults_to_the_current_month(self) -> None:
        view = CalendarView([])
        today = date.today()
        self.assertEqual((view._year, view._month), (today.year, today.month))

    def test_a_day_with_an_assigned_watch_shows_its_record(self) -> None:
        today = date.today()
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[today])
        view = CalendarView([record])
        self.assertEqual(view._grid._cells[today].record.slug, "seiko-sarb033")

    def test_an_assigned_day_with_no_photo_paints_a_different_fill_than_an_empty_day(self) -> None:
        """Regression: both used to fall through to the same PLATE_HIGH fill
        with full-brightness text, making an assigned watch with no photo
        indistinguishable on screen from a day nothing was recorded on."""
        today = date.today()
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[today])
        view = CalendarView([record])
        assigned_cell = view._grid._cells[today]
        empty_cell = next(c for day, c in view._grid._cells.items() if day != today and c.grid_day.in_month)
        for cell in (assigned_cell, empty_cell):
            cell.resize(72, 72)

        # Bottom-right corner: away from the day number and the brand label,
        # both left-aligned near the top — pure fill colour, no glyph pixels.
        assigned_pixel = assigned_cell.grab().toImage().pixelColor(64, 64)
        empty_pixel = empty_cell.grab().toImage().pixelColor(64, 64)
        self.assertNotEqual(assigned_pixel.name(), empty_pixel.name())

    def test_an_empty_day_has_no_record(self) -> None:
        view = CalendarView([])
        cell = next(iter(view._grid._cells.values()))
        self.assertIsNone(cell.record)

    def test_navigating_months_updates_the_label(self) -> None:
        view = CalendarView([])
        label_before = view._month_label.text()
        view._go_next()
        self.assertNotEqual(view._month_label.text(), label_before)

    def test_navigating_backward_from_january_wraps_to_december_of_the_prior_year(self) -> None:
        view = CalendarView([])
        view._year, view._month = 2026, 1
        view._render()
        view._go_previous()
        self.assertEqual((view._year, view._month), (2025, 12))


class DayCellNumberColorTests(unittest.TestCase):
    """Regression: the day number over a photo sits on a fixed black scrim
    (see the scrim's own fixed QColor(0,0,0,130) a few lines above it in
    calendar_view.py), not a themed surface. Using theme.colors().text there
    made light mode draw near-black ink on that same near-black scrim —
    measured at 1.5:1, effectively invisible. See SPEC.md §6's contrast pass."""

    def tearDown(self) -> None:
        theme.set_mode(theme.MODE_DARK)

    def test_number_colour_over_a_photo_is_fixed_regardless_of_theme_mode(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033")
        cell = _DayCell(GridDay(day=date.today(), in_month=True), record, is_today=False)
        cell._pixmap = QPixmap(10, 10)

        for mode in (theme.MODE_DARK, theme.MODE_LIGHT):
            theme.set_mode(mode)
            with self.subTest(mode=mode):
                self.assertEqual(cell._number_color(theme.colors()).name(), "#e8e4dc")

    def test_number_colour_without_a_photo_still_follows_the_active_palette(self) -> None:
        assigned = _record("seiko-sarb033", "Seiko", "SARB033")
        cell_assigned = _DayCell(GridDay(day=date.today(), in_month=True), assigned, is_today=False)
        cell_empty = _DayCell(GridDay(day=date.today(), in_month=True), None, is_today=False)
        self.assertIsNone(cell_assigned._pixmap)

        for mode in (theme.MODE_DARK, theme.MODE_LIGHT):
            theme.set_mode(mode)
            palette = theme.colors()
            with self.subTest(mode=mode):
                self.assertEqual(cell_assigned._number_color(palette).name(), QColor(palette.text).name())
                self.assertEqual(cell_empty._number_color(palette).name(), QColor(palette.text_muted).name())


class CalendarViewAssignFlowTests(unittest.TestCase):
    def test_clicking_an_empty_day_and_picking_a_watch_emits_assign_requested(self) -> None:
        target_day = date.today()
        record = _record("seiko-sarb033", "Seiko", "SARB033")
        view = CalendarView([record])

        received = []
        view.assign_requested.connect(lambda dates, rec: received.append((dates, rec)))

        def _pick(self):
            self._chosen = record
            return QDialog.DialogCode.Accepted

        with patch.object(WatchPicker, "exec", _pick):
            view._on_range_chosen([target_day])

        self.assertEqual(len(received), 1)
        dates, chosen = received[0]
        self.assertEqual(dates, [target_day])
        self.assertEqual(chosen.slug, "seiko-sarb033")

    def test_clear_in_the_picker_emits_clear_requested(self) -> None:
        target_day = date.today()
        view = CalendarView([])

        received = []
        view.clear_requested.connect(received.append)

        def _pick_clear(self):
            self._cleared = True
            return QDialog.DialogCode.Accepted

        with patch.object(WatchPicker, "exec", _pick_clear):
            view._on_range_chosen([target_day])

        self.assertEqual(received, [[target_day]])

    def test_cancelling_the_picker_emits_nothing(self) -> None:
        view = CalendarView([])
        received = []
        view.assign_requested.connect(lambda *a: received.append(a))
        view.clear_requested.connect(lambda *a: received.append(a))

        with patch.object(WatchPicker, "exec", return_value=QDialog.DialogCode.Rejected):
            view._on_range_chosen([date.today()])

        self.assertEqual(received, [])

    def test_a_single_already_assigned_day_passes_its_watch_as_current_to_the_picker(self) -> None:
        target_day = date.today()
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[target_day])
        view = CalendarView([record])

        captured = {}

        def _capture_init(self, records, current=None, parent=None):
            captured["current"] = current
            self._chosen = None
            self._cleared = False

        with patch.object(WatchPicker, "__init__", _capture_init), \
             patch.object(WatchPicker, "exec", return_value=QDialog.DialogCode.Rejected):
            view._on_range_chosen([target_day])

        self.assertEqual(captured["current"].slug, "seiko-sarb033")

    def test_a_multi_day_range_does_not_pre_mark_a_current_watch(self) -> None:
        """A drag-selected range can span days with different (or no) owners
        — there's no single 'current' watch to mark. See SPEC.md §5.5."""
        day1, day2 = date.today(), date.today() + timedelta(days=1)
        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[day1])
        view = CalendarView([record])

        captured = {}

        def _capture_init(self, records, current=None, parent=None):
            captured["current"] = current
            self._chosen = None
            self._cleared = False

        with patch.object(WatchPicker, "__init__", _capture_init), \
             patch.object(WatchPicker, "exec", return_value=QDialog.DialogCode.Rejected):
            view._on_range_chosen([day1, day2])

        self.assertIsNone(captured["current"])


class MonthGridRealMouseEventTests(unittest.TestCase):
    """Drives actual QMouseEvents at _MonthGrid (not _on_range_chosen directly)
    to exercise childAt()-based day resolution end to end — the one path every
    other calendar test bypasses."""

    def test_clicking_a_day_cell_resolves_to_that_exact_day(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033")
        view = CalendarView([record])
        view.resize(1200, 900)
        view.show()
        QApplication.processEvents()

        target_day = date(view._year, view._month, 5)
        cell = view._grid._cells[target_day]
        pos = cell.geometry().center()

        received = []
        view._grid.range_chosen.connect(received.append)

        with patch.object(WatchPicker, "exec", return_value=QDialog.DialogCode.Rejected):
            QTest.mouseClick(view._grid, Qt.MouseButton.LeftButton, pos=pos)

        self.assertEqual(received, [[target_day]])
        view.close()

    def test_dragging_across_two_cells_resolves_to_the_chronological_range(self) -> None:
        view = CalendarView([])
        view.resize(1200, 900)
        view.show()
        QApplication.processEvents()

        start_day = date(view._year, view._month, 5)
        end_day = date(view._year, view._month, 8)
        start_pos = view._grid._cells[start_day].geometry().center()
        end_pos = view._grid._cells[end_day].geometry().center()

        received = []
        view._grid.range_chosen.connect(received.append)

        with patch.object(WatchPicker, "exec", return_value=QDialog.DialogCode.Rejected):
            QTest.mousePress(view._grid, Qt.MouseButton.LeftButton, pos=start_pos)
            QTest.mouseMove(view._grid, pos=end_pos)
            QTest.mouseRelease(view._grid, Qt.MouseButton.LeftButton, pos=end_pos)

        expected = [start_day + timedelta(days=i) for i in range(4)]
        self.assertEqual(received, [expected])
        view.close()


class CalendarViewSetRecordsPreservesMonthTests(unittest.TestCase):
    def test_set_records_does_not_change_the_displayed_month(self) -> None:
        view = CalendarView([])
        view._go_next()
        view._go_next()
        year_before, month_before = view._year, view._month

        view.set_records([_record("seiko-sarb033", "Seiko", "SARB033")])

        self.assertEqual((view._year, view._month), (year_before, month_before))

    def test_set_records_refreshes_the_worn_index(self) -> None:
        today = date.today()
        view = CalendarView([])
        self.assertIsNone(view._grid._cells[today].record)

        record = _record("seiko-sarb033", "Seiko", "SARB033", worn=[today])
        view.set_records([record])

        self.assertEqual(view._grid._cells[today].record.slug, "seiko-sarb033")


class CalendarFooterTests(unittest.TestCase):
    def test_footer_counts_days_watches_and_not_worn(self) -> None:
        today = date.today()
        worn_watch = _record("seiko-sarb033", "Seiko", "SARB033", worn=[today])
        idle_watch = _record("omega-speedmaster", "Omega", "Speedmaster")
        view = CalendarView([worn_watch, idle_watch])

        text = view._footer_text()
        self.assertIn("1 days recorded", text)
        self.assertIn("1 watches worn", text)
        self.assertIn("1 not worn this month", text)


if __name__ == "__main__":
    unittest.main()
