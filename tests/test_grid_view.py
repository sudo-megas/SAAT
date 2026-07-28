import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from saat.models import Watch
from saat.storage import create_watch, load_collection
from saat.ui.cards import DEFAULT_CARD_WIDTH
from saat.ui.grid_view import MAX_FILL_STRETCH, GridView
from saat.ui.theme import CARD_PADDING, PAGE_MARGIN, SIDEBAR_WIDTH

_app = QApplication.instance() or QApplication([])


def _formula_columns(usable_width: int) -> int:
    """Independent re-derivation of _compute_render_width()'s own columns
    step -- calling GridView's own method wouldn't test anything, since a
    bug in the formula would then agree with itself. This is what
    GridViewReflowTests.test_geometry_derived_columns_matches_the_formulas_own_columns
    below checks _columns (the FlowLayout's real, independently-computed
    row-wrap geometry) against."""
    usable = max(usable_width, DEFAULT_CARD_WIDTH)
    return max(2, (usable + CARD_PADDING) // (DEFAULT_CARD_WIDTH + CARD_PADDING))


class GridViewKeyboardNavTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-grid-keyboard-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _view(self, count: int = 6) -> GridView:
        # Zero-padded numbers, not "ABCDEF"[:count] -- milestone 21b's
        # denser default card width needs a count that can comfortably
        # exceed 26+ columns at a real window width, not just 6.
        for i in range(count):
            create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model=f"{i:03d}"))
        records = sorted(load_collection(self.watches_dir), key=lambda r: r.watch.model)
        view = GridView()
        view.set_records(records)
        view.resize(1400, 900)
        view.show()
        QApplication.processEvents()
        self.assertGreaterEqual(view._columns, 2, "test needs at least two columns to be meaningful")
        return view

    def test_focusing_the_grid_puts_the_cursor_on_the_first_card(self) -> None:
        view = self._view()
        view.setFocus()
        QApplication.processEvents()

        self.assertTrue(view._cards[0].property("cursor-focused"))
        view.close()

    def test_losing_focus_hides_the_cursor_ring(self) -> None:
        view = self._view()
        view.setFocus()
        QApplication.processEvents()
        view.clearFocus()
        QApplication.processEvents()

        self.assertFalse(view._cards[0].property("cursor-focused"))
        view.close()

    def test_right_arrow_moves_the_cursor_to_the_next_card(self) -> None:
        view = self._view()
        view.setFocus()
        QApplication.processEvents()

        QTest.keyClick(view, Qt.Key.Key_Right)

        self.assertFalse(view._cards[0].property("cursor-focused"))
        self.assertTrue(view._cards[1].property("cursor-focused"))
        view.close()

    def test_left_arrow_at_the_first_card_stays_put(self) -> None:
        view = self._view()
        view.setFocus()
        QApplication.processEvents()

        QTest.keyClick(view, Qt.Key.Key_Left)

        self.assertTrue(view._cards[0].property("cursor-focused"))
        view.close()

    def test_down_arrow_moves_the_cursor_by_the_column_count(self) -> None:
        # Milestone 21b's target-width reflow computes far more columns at
        # this same 1400px width than the old fixed-CARD_WIDTH formula did
        # -- the default count=6 no longer guarantees a second row exists
        # to move down into, so this test asks for enough records that one
        # does regardless of the exact column count.
        view = self._view(count=30)
        columns = view._columns
        view.setFocus()
        QApplication.processEvents()

        QTest.keyClick(view, Qt.Key.Key_Down)

        self.assertTrue(view._cards[columns].property("cursor-focused"))
        view.close()

    def test_up_arrow_past_the_top_row_stays_put(self) -> None:
        view = self._view()
        view.setFocus()
        QApplication.processEvents()

        QTest.keyClick(view, Qt.Key.Key_Up)

        self.assertTrue(view._cards[0].property("cursor-focused"))
        view.close()

    def test_enter_activates_the_focused_card(self) -> None:
        view = self._view()
        view.setFocus()
        QApplication.processEvents()
        received = []
        view.record_activated.connect(received.append)

        QTest.keyClick(view, Qt.Key.Key_Right)
        QTest.keyClick(view, Qt.Key.Key_Return)

        self.assertEqual(received, [view._cards[1].record])
        view.close()

    def test_rebuilding_records_resets_the_cursor(self) -> None:
        view = self._view()
        view.setFocus()
        QApplication.processEvents()
        QTest.keyClick(view, Qt.Key.Key_Right)
        self.assertIsNotNone(view._focus_index)

        records = sorted(load_collection(self.watches_dir), key=lambda r: r.watch.model)
        view.set_records(records)

        self.assertIsNone(view._focus_index)
        view.close()


class GridViewReflowTests(unittest.TestCase):
    """Milestone 21b: target-width reflow -- a wider screen gets more
    columns of roughly DEFAULT_CARD_WIDTH each, not fewer bigger cards."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-grid-reflow-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _view(self, count: int, width: int, height: int = 900) -> GridView:
        for i in range(count):
            create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model=f"{i:03d}"))
        records = sorted(load_collection(self.watches_dir), key=lambda r: r.watch.model)
        view = GridView()
        view.resize(width, height)
        view.show()
        self.addCleanup(view.close)
        view.set_records(records)
        QApplication.processEvents()
        return view

    def test_geometry_derived_columns_matches_the_formulas_own_columns(self) -> None:
        """The exact regression this milestone's plan called out: the
        vendored FlowLayout computes its wrap independently from each
        card's real sizeHint(), so _columns (read back from actual
        post-layout geometry) must agree with what the reflow formula's
        own columns step predicts -- a 1px disagreement here would
        silently break Key_Up/Key_Down's delta math without either half
        raising an error on its own."""
        width = 1400
        view = self._view(count=40, width=width)
        usable = view.viewport().width() - 2 * PAGE_MARGIN
        self.assertEqual(view._columns, _formula_columns(usable))

    def test_card_width_stays_within_the_drift_bound_across_window_widths(self) -> None:
        """DEFAULT_CARD_WIDTH..DEFAULT_CARD_WIDTH+MAX_FILL_STRETCH, by
        construction -- the provable bound behind "card size stays
        visually consistent, column count differs" (as opposed to the old
        fixed-columns/scaled-cards shape this replaces, where card size
        varied by hundreds of px between screen sizes).

        The widths tried here (700..2200) are real GridView pixel widths,
        chosen to reflect how the view is actually sized in the shipped
        app -- not an exhaustive claim about the formula for arbitrarily
        small viewports. The formula's own columns=2 floor has no matching
        floor on render_width (see _compute_render_width()'s docstring),
        but that only bites below a ~468px viewport, which MainWindow's
        enforced MIN_SIZE=(1100, 700) never lets this view's real
        viewport approach (measured ~826-840px at that floor)."""
        for width in (700, 900, 1100, 1400, 1800, 2200):
            with self.subTest(width=width):
                view = self._view(count=12, width=width)
                card_width = view._cards[0].width()
                self.assertGreaterEqual(card_width, DEFAULT_CARD_WIDTH - 8)  # the //8 quantization's own floor
                self.assertLessEqual(card_width, DEFAULT_CARD_WIDTH + MAX_FILL_STRETCH)

    def test_1920_and_2560_produce_the_milestones_own_worked_example(self) -> None:
        """Pinned regression for the plan's own two worked examples
        (sidebar-adjusted usable width, per SIDEBAR_WIDTH): 1920x1080 at
        7 columns / 216px cards matches exactly; 2560x1440 lands at
        10 columns / 208px (not the plan's stated 210px -- a small
        arithmetic slip in the plan's own prose summary, not in this
        formula: (2252 - 9*16)//10 == 210, but 210 is not a multiple of
        8, and the deliberate //8 quantization step floors it to 208).
        Both sit comfortably inside the drift bound either way.

        A tall window (2000px) and a record count that fits without
        wrapping vertically (10, comfortably under both cases' own column
        count) keeps the vertical scrollbar off deliberately -- confirmed
        empirically that its own width (platform/style-dependent, ~14px
        here) shifts the usable width enough to change which multiple-of-8
        bucket the formula lands in. That's real, correct behavior (a
        vertical scrollbar does eat real width), just not this test's
        concern -- test_card_width_stays_within_the_drift_bound_across_
        window_widths above already covers the general, scrollbar-agnostic
        claim (the range, not an exact pinned figure) across six widths
        without needing to control for it."""
        cases = [(1920, 7, 216), (2560, 10, 208)]
        for screen_width, expected_columns, expected_card_width in cases:
            with self.subTest(screen_width=screen_width):
                view = self._view(count=10, width=screen_width - SIDEBAR_WIDTH, height=2000)
                self.assertFalse(view.verticalScrollBar().isVisible())
                self.assertEqual(view._columns, expected_columns)
                self.assertEqual(view._cards[0].width(), expected_card_width)

    def test_every_row_is_reachable_by_scrolling_not_just_the_first_screenful(self) -> None:
        """QScrollArea's own setWidgetResizable(True) does not correctly
        negotiate height against a custom height-for-width QLayout like
        FlowLayout -- confirmed directly: left to its own auto-sizing,
        _container's height answered as if squeezed to its narrowest
        possible single-card width, not its real current width, which
        badly undercounted the true row count for any collection past the
        first screen. FlowLayout itself laid every row out correctly;
        they were just silently unreachable by scroll, since QScrollArea
        sizes its scroll range off _container's height, not off where its
        deepest child actually sits. A collection long enough to need
        several screens of rows (40 records, a narrow-ish 900px window to
        force few columns and many rows) reproduces this directly if the
        _relayout() fix (explicit setFixedHeight from the layout's own
        heightForWidth()) ever regresses."""
        view = self._view(count=40, width=900, height=700)
        last_card = view._cards[-1]

        self.assertGreaterEqual(view._container.height(), last_card.y() + last_card.height())

        view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())
        QApplication.processEvents()
        last_bottom_in_viewport = last_card.mapTo(view.viewport(), last_card.rect().bottomLeft()).y()
        self.assertLessEqual(last_bottom_in_viewport, view.viewport().rect().height())

    def test_container_height_stays_correct_across_a_pure_resize(self) -> None:
        """The same heightForWidth() fix applies on the resizeEvent path
        (_relayout() alone, no set_records()) too -- not just right after
        construction, which test_every_row_is_reachable_by_scrolling_not_
        just_the_first_screenful above already covers."""
        view = self._view(count=40, width=1400, height=900)

        view.resize(1000, 900)
        QApplication.processEvents()

        last_card = view._cards[-1]
        self.assertGreaterEqual(view._container.height(), last_card.y() + last_card.height())


if __name__ == "__main__":
    unittest.main()
