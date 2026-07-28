import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from PySide6.QtWidgets import QApplication

from saat.ui.bottom_bar import BottomBar
from saat.ui.collection_summary import CollectionSummary, WishlistSummary

_app = QApplication.instance() or QApplication([])

# BottomBar's own retranslate-from-the-stored-summary behavior is covered
# through the real production path in test_retranslation.py's
# MainWindowRetranslationTests (a bare BottomBar() here has no config/
# install_language() apparatus of its own to drive a real LanguageChange
# the way that file's setUp already provides).


class BottomBarSummaryTextTests(unittest.TestCase):
    def test_no_summary_yet_shows_blank_text(self) -> None:
        bar = BottomBar()
        self.assertEqual(bar._summary_label.text(), "")

    def test_setting_then_clearing_the_summary_blanks_the_text_again(self) -> None:
        """set_summary(None) is what MainWindow calls while navigating away
        from CollectionView (Detail/Compare) -- stale collection figures
        under a page they don't describe would be worse than blank."""
        bar = BottomBar()
        bar.set_summary(CollectionSummary(total=3))
        self.assertNotEqual(bar._summary_label.text(), "")

        bar.set_summary(None)

        self.assertEqual(bar._summary_label.text(), "")

    def test_collection_summary_shows_count_movement_kinds_and_value(self) -> None:
        bar = BottomBar()
        summary = CollectionSummary(
            total=3, by_movement_kind=[("Automatic", 2), ("Quartz", 1)], value_by_currency=[("USD", 1500.0)]
        )

        bar.set_summary(summary)

        text = bar._summary_label.text()
        self.assertIn("3 watches", text)
        self.assertIn("Automatic 2", text)
        self.assertIn("Quartz 1", text)
        self.assertIn("1,500.00 USD", text)  # fmt_price's own format, not re-verified here

    def test_singular_count_uses_the_singular_form(self) -> None:
        bar = BottomBar()
        bar.set_summary(CollectionSummary(total=1))
        self.assertIn("1 watch", bar._summary_label.text())
        self.assertNotIn("1 watches", bar._summary_label.text())

    def test_wishlist_summary_branches_on_type_not_a_separate_flag(self) -> None:
        """CollectionView.current_summary (collection_view.py) always
        returns one of these two distinct dataclasses -- BottomBar tells
        them apart with isinstance(), the same way it's told apart
        everywhere else compute_wishlist_summary's result is consumed
        (export.py, sidebar.py), rather than needing a redundant
        is_wishlist bool threaded alongside it."""
        bar = BottomBar()
        summary = WishlistSummary(total=2, target_value_by_currency=[("USD", 800.0)])

        bar.set_summary(summary)

        text = bar._summary_label.text()
        self.assertIn("2 watches", text)
        self.assertIn("800.00 USD", text)
        self.assertNotIn("Due within 12mo", text)  # has_any_target_date is False here

    def test_wishlist_summary_with_no_due_dates_in_the_next_12mo_shows_zero(self) -> None:
        bar = BottomBar()
        summary = WishlistSummary(total=1, has_any_target_date=True, due_next_12_months_by_currency=[])

        bar.set_summary(summary)

        self.assertIn("Due within 12mo: 0", bar._summary_label.text())


class BottomBarPaletteRelayTests(unittest.TestCase):
    def test_palette_button_selection_is_relayed_under_bottom_bars_own_signal(self) -> None:
        bar = BottomBar()
        received = []
        bar.palette_selected.connect(received.append)

        bar._palette_button.palette_selected.emit("nord")

        self.assertEqual(received, ["nord"])


if __name__ == "__main__":
    unittest.main()
