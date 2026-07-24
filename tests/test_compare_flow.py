import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel

from saat.config import Config
from saat.models import Acquisition, Watch
from saat.storage import create_watch, load_collection
from saat.ui.collection_view import CollectionView
from saat.ui.compare_view import CompareView
from saat.ui.main_window import MainWindow

_app = QApplication.instance() or QApplication([])


class UITestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-compare-flow-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _config(self) -> Config:
        return Config(self.tmp / "config.toml")


class GridCheckboxToCompareViewTests(UITestCase):
    def test_checking_two_cards_shows_the_compare_button_with_the_right_count(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="A"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="B"))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        window.show()
        collection_view = window.centralWidget().currentWidget()

        cards = collection_view._grid_view._cards
        cards[0]._checkbox.setChecked(True)
        cards[1]._checkbox.setChecked(True)

        self.assertTrue(collection_view._top_bar._compare_button.isVisible())
        self.assertEqual(collection_view._top_bar._compare_button.text(), "Compare (2)")

    def test_clicking_compare_opens_a_compare_view_with_exactly_the_selected_watches(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="A"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="B"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="C"))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()

        cards = collection_view._grid_view._cards
        expected = {cards[0]._record.slug, cards[2]._record.slug}
        cards[0]._checkbox.setChecked(True)
        cards[2]._checkbox.setChecked(True)

        collection_view._top_bar._compare_button.click()

        current = window.centralWidget().currentWidget()
        self.assertIsInstance(current, CompareView)
        shown_titles = {label.text() for label in current.findChildren(QLabel) if label.property("class") == "detail-title"}
        expected_models = {r.watch.model for r in collection_view.records if r.slug in expected}
        self.assertEqual(shown_titles, expected_models)

    def test_back_from_compare_returns_to_the_same_collection_view(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="A"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="B"))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()

        for card in collection_view._grid_view._cards:
            card._checkbox.setChecked(True)
        collection_view._top_bar._compare_button.click()

        compare_view = window.centralWidget().currentWidget()
        compare_view.back_requested.emit()

        self.assertIs(window.centralWidget().currentWidget(), collection_view)

    def test_a_fifth_selection_is_rejected_and_the_count_stays_at_the_cap(self) -> None:
        for i in range(5):
            create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model=f"M{i}"))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()

        for card in collection_view._grid_view._cards[:4]:
            card._checkbox.setChecked(True)
        self.assertEqual(collection_view._top_bar._compare_button.text(), "Compare (4)")

        collection_view._grid_view._cards[4]._checkbox.setChecked(True)

        self.assertEqual(collection_view._top_bar._compare_button.text(), "Compare (4)")
        self.assertFalse(collection_view._grid_view._cards[4]._checkbox.isChecked())

    def test_table_selection_feeds_the_same_compare_count_as_the_grid(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="A"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="B"))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()

        collection_view._table_view.selectRow(0)
        self.assertEqual(collection_view._top_bar._compare_button.text(), "Compare (1)")

    def test_a_watch_selected_in_the_table_shows_as_checked_after_switching_to_grid(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="A"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="B"))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()
        [target] = [r for r in collection_view.records if r.watch.model == "A"]

        collection_view._table_view.selectRow(0 if collection_view._ordered_records[0].slug == target.slug else 1)

        checked_slugs = {c._record.slug for c in collection_view._grid_view._cards if c._checkbox.isChecked()}
        self.assertEqual(checked_slugs, {target.slug})


class WishlistScopeThreadsIntoCompareViewTests(UITestCase):
    def test_comparing_from_wishlist_scope_shows_target_price_not_price(self) -> None:
        """SPEC.md M15 Commit C: the dimension-bars price row follows the
        active scope. Collection-scope compare is already covered by
        GridCheckboxToCompareViewTests; this is the Wishlist-scope half,
        exercised through the real MainWindow/CollectionView/TopBar wiring
        rather than by constructing CompareView directly, since the thing
        actually being tested is that MainWindow reads the scope correctly
        at the moment Compare is clicked."""
        create_watch(self.watches_dir, self.backups_dir, Watch(
            brand="Seiko", model="A", status="Wishlist", acquisition=Acquisition(target_price=500, currency="USD"),
        ))
        create_watch(self.watches_dir, self.backups_dir, Watch(
            brand="Seiko", model="B", status="Wishlist", acquisition=Acquisition(target_price=800, currency="USD"),
        ))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()
        collection_view._top_bar._wishlist_button.click()

        for card in collection_view._grid_view._cards:
            card._checkbox.setChecked(True)
        collection_view._top_bar._compare_button.click()

        compare_view = window.centralWidget().currentWidget()
        self.assertIsInstance(compare_view, CompareView)
        labels = [l.text() for l in compare_view.findChildren(QLabel)]
        self.assertIn("Target Price", labels)
        self.assertNotIn("Price", labels)


class GridWoreTodayHoverTests(UITestCase):
    def test_clicking_wore_today_on_a_card_persists_through_the_real_window(self) -> None:
        from datetime import date

        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()

        collection_view._grid_view._cards[0]._wore_today_bar.click()

        [reloaded] = load_collection(self.watches_dir)
        self.assertEqual(reloaded.watch.worn, [date.today()])


if __name__ == "__main__":
    unittest.main()
