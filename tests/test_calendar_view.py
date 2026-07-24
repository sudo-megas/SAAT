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
from saat.ui.calendar_view import CalendarView, _DayCell, _MODE_MONTH, _MODE_STATS, _MODE_YEAR
from saat.ui.month_grid import GridDay
from saat.ui.watch_picker import WatchPicker

_app = QApplication.instance() or QApplication([])


def _record(
    slug: str, brand: str, model: str, worn: list[date] | None = None, status: str = "Owned"
) -> WatchRecord:
    return WatchRecord(
        slug=slug, path=Path(f"/nonexistent/{slug}"), watch=Watch(brand=brand, model=model, worn=worn or [], status=status)
    )


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

    def test_navigating_months_updates_the_month_combo_and_year_spinbox(self) -> None:
        view = CalendarView([])
        year_before, month_index_before = view._year_spinbox.value(), view._month_combo.currentIndex()
        view._go_next()
        self.assertEqual((view._year_spinbox.value(), view._month_combo.currentIndex()), (view._year, view._month - 1))
        self.assertNotEqual((view._year_spinbox.value(), view._month_combo.currentIndex()), (year_before, month_index_before))

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

    def test_a_non_owned_watch_is_not_offered_by_the_picker(self) -> None:
        """SPEC.md §5.12: a Wishlist watch can't be worn, so it must not be
        assignable — offering it would let the picker "succeed" while
        build_worn_index() silently drops the assignment on the next render."""
        owned = _record("seiko-sarb033", "Seiko", "SARB033")
        wishlist = _record("omega-speedmaster", "Omega", "Speedmaster", status="Wishlist")
        view = CalendarView([owned, wishlist])

        captured = {}

        def _capture_init(self, records, current=None, parent=None):
            captured["slugs"] = {r.slug for r in records}
            self._chosen = None
            self._cleared = False

        with patch.object(WatchPicker, "__init__", _capture_init), \
             patch.object(WatchPicker, "exec", return_value=QDialog.DialogCode.Rejected):
            view._on_range_chosen([date.today()])

        self.assertEqual(captured["slugs"], {"seiko-sarb033"})


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


class MonthGridRealKeyboardEventTests(unittest.TestCase):
    """Drives actual QKeyEvents at _MonthGrid (not _focused_day directly),
    mirroring MonthGridRealMouseEventTests above for the keyboard cursor."""

    def test_focusing_the_grid_puts_the_cursor_on_today(self) -> None:
        view = CalendarView([])
        view.resize(1200, 900)
        view.show()
        QApplication.processEvents()

        view._grid.setFocus()
        QApplication.processEvents()

        self.assertTrue(view._grid._cells[date.today()].focused)
        view.close()

    def test_right_arrow_moves_the_cursor_forward_one_day(self) -> None:
        view = CalendarView([])
        view.resize(1200, 900)
        view.show()
        QApplication.processEvents()
        view._grid.setFocus()
        QApplication.processEvents()

        QTest.keyClick(view._grid, Qt.Key.Key_Right)

        expected = date.today() + timedelta(days=1)
        self.assertTrue(view._grid._cells[expected].focused)
        self.assertFalse(view._grid._cells[date.today()].focused)
        view.close()

    def test_down_arrow_moves_the_cursor_forward_one_week(self) -> None:
        view = CalendarView([])
        view.resize(1200, 900)
        view.show()
        QApplication.processEvents()
        first_of_month = date(view._year, view._month, 1)
        view._grid._focused_day = first_of_month
        view._grid.setFocus()
        QApplication.processEvents()

        QTest.keyClick(view._grid, Qt.Key.Key_Down)

        self.assertEqual(view._grid._focused_day, first_of_month + timedelta(days=7))
        view.close()

    def test_left_arrow_at_the_first_of_the_month_does_not_cross_into_the_previous_month(self) -> None:
        view = CalendarView([])
        view.resize(1200, 900)
        view.show()
        QApplication.processEvents()
        first_of_month = date(view._year, view._month, 1)
        view._grid._focused_day = first_of_month
        view._grid.setFocus()
        QApplication.processEvents()

        QTest.keyClick(view._grid, Qt.Key.Key_Left)

        self.assertEqual(view._grid._focused_day, first_of_month)
        view.close()

    def test_enter_opens_the_watch_picker_for_the_focused_day(self) -> None:
        view = CalendarView([])
        view.resize(1200, 900)
        view.show()
        QApplication.processEvents()
        view._grid.setFocus()
        QApplication.processEvents()

        received = []
        view._grid.range_chosen.connect(received.append)

        with patch.object(WatchPicker, "exec", return_value=QDialog.DialogCode.Rejected):
            QTest.keyClick(view._grid, Qt.Key.Key_Return)

        self.assertEqual(received, [[date.today()]])
        view.close()

    def test_switching_to_a_month_without_today_resets_the_cursor_to_the_first(self) -> None:
        view = CalendarView([])
        view.resize(1200, 900)
        view.show()
        QApplication.processEvents()

        view._go_next()

        self.assertEqual(view._grid._focused_day, date(view._year, view._month, 1))
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


class TodayButtonTests(unittest.TestCase):
    def test_returns_to_the_current_month_from_month_mode(self) -> None:
        view = CalendarView([])
        view._go_next()
        view._go_next()
        view._go_next()
        today = date.today()
        self.assertNotEqual((view._year, view._month), (today.year, today.month))

        view._go_today()

        self.assertEqual((view._year, view._month), (today.year, today.month))

    def test_returns_to_the_current_year_from_year_mode_without_touching_month(self) -> None:
        view = CalendarView([])
        view._set_mode(_MODE_YEAR)
        view._year += 5
        view._month = 3  # deliberately not today's month, to prove Year mode's Today leaves it alone
        view._render()

        view._go_today()

        self.assertEqual(view._year, date.today().year)
        self.assertEqual(view._month, 3)

    def test_hidden_in_stats_mode(self) -> None:
        view = CalendarView([])
        view.show()
        QApplication.processEvents()

        view._set_mode(_MODE_STATS)
        QApplication.processEvents()

        self.assertFalse(view._today_button.isVisible())
        view.close()


class MonthYearJumpControlsTests(unittest.TestCase):
    def test_changing_the_month_combo_navigates(self) -> None:
        view = CalendarView([])
        view._year, view._month = 2026, 1
        view._render()

        view._month_combo.setCurrentIndex(5)  # June

        self.assertEqual(view._month, 6)

    def test_changing_the_year_spinbox_navigates(self) -> None:
        view = CalendarView([])
        view._year_spinbox.setValue(2030)
        self.assertEqual(view._year, 2030)

    def test_switching_to_year_mode_hides_the_month_combo_but_not_the_year_spinbox(self) -> None:
        view = CalendarView([])
        view.show()
        QApplication.processEvents()

        view._set_mode(_MODE_YEAR)
        QApplication.processEvents()

        self.assertFalse(view._month_combo.isVisible())
        self.assertTrue(view._year_spinbox.isVisible())
        view.close()

    def test_switching_to_stats_mode_hides_both_jump_controls(self) -> None:
        view = CalendarView([])
        view.show()
        QApplication.processEvents()

        view._set_mode(_MODE_STATS)
        QApplication.processEvents()

        self.assertFalse(view._month_combo.isVisible())
        self.assertFalse(view._year_spinbox.isVisible())
        view.close()

    def test_render_syncing_the_spinbox_across_a_year_wrap_does_not_fire_valuechanged(self) -> None:
        """The spinbox/combo are updated with signals blocked during
        _render() — this is what stops that sync from re-entering
        _on_year_spinbox_changed and turning one navigation into two."""
        view = CalendarView([])
        view._year, view._month = 2026, 12
        view._render()
        fired = []
        view._year_spinbox.valueChanged.connect(fired.append)

        view._go_next()  # December -> January: the year actually changes

        self.assertEqual(view._year, 2027)
        self.assertEqual(view._year_spinbox.value(), 2027)
        self.assertEqual(fired, [])


class RotationEmphasisTests(unittest.TestCase):
    """Click-through from Stats mode's Rotation list. See SPEC.md §5.5."""

    def tearDown(self) -> None:
        theme.set_mode(theme.MODE_DARK)

    def test_persists_across_month_navigation(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033")
        view = CalendarView([record])
        view._on_rotation_clicked("seiko-sarb033")

        view._go_next()

        self.assertEqual(view._emphasized_slug, "seiko-sarb033")
        self.assertEqual(view._mode, _MODE_MONTH)

    def test_clears_on_mode_change(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033")
        view = CalendarView([record])
        view._on_rotation_clicked("seiko-sarb033")

        view._set_mode(_MODE_YEAR)

        self.assertIsNone(view._emphasized_slug)

    def test_rotation_click_switches_to_month_mode_without_losing_the_emphasis_it_sets(self) -> None:
        """_set_mode() unconditionally clears emphasis — that's the "mode
        change clears it" rule — so the rotation-click handler must apply
        that clearing before it sets the new emphasis, not after."""
        view = CalendarView([])
        view._set_mode(_MODE_STATS)

        view._on_rotation_clicked("seiko-sarb033")

        self.assertEqual(view._mode, _MODE_MONTH)
        self.assertEqual(view._emphasized_slug, "seiko-sarb033")

    def test_clear_emphasis_is_a_no_op_when_nothing_is_emphasized(self) -> None:
        view = CalendarView([])
        view.clear_emphasis()  # must not raise
        self.assertIsNone(view._emphasized_slug)

    def test_clear_emphasis_clears_an_active_emphasis(self) -> None:
        record = _record("seiko-sarb033", "Seiko", "SARB033")
        view = CalendarView([record])
        view._on_rotation_clicked("seiko-sarb033")

        view.clear_emphasis()

        self.assertIsNone(view._emphasized_slug)

    def test_dimmed_cell_is_visibly_different_from_an_emphasized_cell_in_both_themes(self) -> None:
        for mode in (theme.MODE_DARK, theme.MODE_LIGHT):
            theme.set_mode(mode)
            with self.subTest(mode=mode):
                today = date.today()
                other_day = today + timedelta(days=1) if today.day < 27 else today - timedelta(days=1)
                emphasized = _record("seiko-sarb033", "Seiko", "SARB033", worn=[today])
                other = _record("omega-speedmaster", "Omega", "Speedmaster", worn=[other_day])
                view = CalendarView([emphasized, other])
                view.resize(1200, 900)
                view.show()
                QApplication.processEvents()

                view._on_rotation_clicked("seiko-sarb033")
                QApplication.processEvents()

                emphasized_cell = view._grid._cells[today]
                dimmed_cell = view._grid._cells[other_day]
                self.assertFalse(emphasized_cell.dimmed)
                self.assertTrue(dimmed_cell.dimmed)
                for cell in (emphasized_cell, dimmed_cell):
                    cell.resize(72, 72)

                # Bottom-right corner: away from the day number and the
                # brand label, both left-aligned near the top — pure fill
                # colour, same spot the existing assigned-vs-empty pixel
                # test already samples.
                emphasized_pixel = emphasized_cell.grab().toImage().pixelColor(64, 64)
                dimmed_pixel = dimmed_cell.grab().toImage().pixelColor(64, 64)
                self.assertNotEqual(emphasized_pixel.name(), dimmed_pixel.name())
                view.close()


if __name__ == "__main__":
    unittest.main()
