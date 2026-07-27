import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from PySide6.QtWidgets import QApplication

from saat.ui.top_bar import SCOPE_COLLECTION, SCOPE_WISHLIST, VIEW_CALENDAR, VIEW_GRID, TopBar

_app = QApplication.instance() or QApplication([])

# TopBar sits beside a SIDEBAR_WIDTH=260 sidebar (saat/ui/theme.py), so at the
# app's own documented "minimum 1100x700" (SPEC.md §5.1) it actually only
# ever receives about 1100-260=840px of width, never the full window figure.
# 840 is the realistic floor; 1100 is thrown in as extra margin above it.
_SPEC_FLOOR_CONTENT_WIDTH = 840
_GENEROUS_WIDTH = 1100


def _row_widgets(top_bar: TopBar, row: str) -> list:
    if row == "row1":
        widgets = [
            top_bar._collection_button, top_bar._wishlist_button, top_bar._search_field,
            top_bar._grid_button, top_bar._table_button, top_bar._calendar_button,
        ]
    else:
        widgets = [
            top_bar._sort_combo, top_bar._sort_direction_button, top_bar._preset_combo,
            top_bar._compare_button, top_bar._pick_button, top_bar._export_button, top_bar._theme_toggle,
        ]
    return [w for w in widgets if w.isVisible()]


def _has_overlap(widgets: list) -> bool:
    return any(a.geometry().right() >= b.geometry().left() for a, b in zip(widgets, widgets[1:]))


class TopBarNoOverlapTests(unittest.TestCase):
    """Regression coverage for the top bar's two-row layout: milestones 19
    and 20 each added another action button to what was originally a single
    row, and the row silently overflowed SPEC.md's documented 1100x700
    minimum by hundreds of pixels before anyone noticed on a real laptop.
    Every case here must hold at _SPEC_FLOOR_CONTENT_WIDTH, not just at a
    comfortable desktop width."""

    def _assert_no_overlap_at(self, top_bar: TopBar, width: int) -> None:
        top_bar.resize(width, top_bar.sizeHint().height())
        _app.processEvents()
        for row in ("row1", "row2"):
            widgets = _row_widgets(top_bar, row)
            self.assertFalse(
                _has_overlap(widgets),
                f"{row} widgets overlap at width={width}: "
                + ", ".join(f"{w.__class__.__name__}={w.geometry()}" for w in widgets),
            )

    def test_collection_scope_grid_view(self) -> None:
        top_bar = TopBar()
        top_bar.set_scope(SCOPE_COLLECTION)
        top_bar.set_view(VIEW_GRID)
        for width in (_SPEC_FLOOR_CONTENT_WIDTH, _GENEROUS_WIDTH):
            self._assert_no_overlap_at(top_bar, width)

    def test_wishlist_scope_grid_view(self) -> None:
        """Wishlist hides the pick button (saat/ui/top_bar.py _set_scope),
        a different widget set from Collection scope -- worth checking on
        its own rather than assuming it's strictly easier to fit."""
        top_bar = TopBar()
        top_bar.set_scope(SCOPE_WISHLIST)
        top_bar.set_view(VIEW_GRID)
        for width in (_SPEC_FLOOR_CONTENT_WIDTH, _GENEROUS_WIDTH):
            self._assert_no_overlap_at(top_bar, width)

    def test_collection_scope_calendar_view(self) -> None:
        """The search field is disabled (not hidden) in Calendar view -- a
        disabled QLineEdit still occupies its full layout width, so this
        must be checked separately rather than assumed identical to Grid."""
        top_bar = TopBar()
        top_bar.set_scope(SCOPE_COLLECTION)
        top_bar.set_view(VIEW_CALENDAR)
        for width in (_SPEC_FLOOR_CONTENT_WIDTH, _GENEROUS_WIDTH):
            self._assert_no_overlap_at(top_bar, width)


if __name__ == "__main__":
    unittest.main()
