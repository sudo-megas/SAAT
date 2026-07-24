import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from saat.config import Config
from saat.models import Acquisition, Movement, Watch
from saat.storage import create_watch, load_collection
from saat.ui.collection_view import CollectionView
from saat.ui.sidebar import NOT_WORN_LABEL, Sidebar
from saat.ui.theme import ANIM_DURATION_MS

_app = QApplication.instance() or QApplication([])


class UITestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-sidebar-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _config(self) -> Config:
        return Config(self.tmp / "config.toml")


class SidebarRenderingTests(UITestCase):
    def test_facet_with_no_values_across_the_collection_is_not_built(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        records = load_collection(self.watches_dir)
        sidebar = Sidebar(records)
        self.assertNotIn(("group", "Micro Brand"), sidebar._checkboxes)
        self.assertEqual([k for k in sidebar._checkboxes if k[0] == "group"], [])

    def test_facet_with_a_value_builds_one_checkbox_per_distinct_value(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", style="Diver"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Omega", model="Speedmaster", style="Dress"))
        records = load_collection(self.watches_dir)
        sidebar = Sidebar(records)
        self.assertIn(("style", "Diver"), sidebar._checkboxes)
        self.assertIn(("style", "Dress"), sidebar._checkboxes)

    def test_identical_value_in_two_different_facets_does_not_collide(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", style="Other", group="Other"))
        records = load_collection(self.watches_dir)
        sidebar = Sidebar(records)
        self.assertIn(("style", "Other"), sidebar._checkboxes)
        self.assertIn(("group", "Other"), sidebar._checkboxes)
        sidebar._checkboxes[("style", "Other")].setChecked(True)
        active = sidebar.active_facets()
        self.assertEqual(active.get("style"), {"Other"})
        self.assertNotIn("group", active)

    def test_not_worn_checkbox_present_for_a_never_worn_collection(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        records = load_collection(self.watches_dir)
        sidebar = Sidebar(records)
        self.assertIsNotNone(sidebar._not_worn_checkbox)
        self.assertFalse(sidebar.not_worn_only())
        sidebar._not_worn_checkbox.setChecked(True)
        self.assertTrue(sidebar.not_worn_only())

    def test_update_counts_sets_checkbox_labels(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", style="Diver"))
        records = load_collection(self.watches_dir)
        sidebar = Sidebar(records)
        sidebar.update_counts({"style": {"Diver": 3}}, not_worn_count=5)
        self.assertEqual(sidebar._checkboxes[("style", "Diver")].text(), "Diver (3)")
        self.assertEqual(sidebar._not_worn_checkbox.text(), f"{NOT_WORN_LABEL} (5)")

    def test_collapse_toggle_hides_facets_and_shrinks_width(self) -> None:
        """Milestone 16d: the width change is now eased (theme.ANIM_DURATION_MS
        via motion.animate_width), not instant — the visibility change is
        still synchronous, but the final width needs the animation to land.
        Driven via QPropertyAnimation.setCurrentTime() rather than QTest.qWait():
        a real wall-clock wait pumps the whole app's posted-event queue, which
        in a long-running unittest process can include stale deferred-delete
        events for widgets other tests never let the event loop clean up --
        setCurrentTime() advances only this animation, deterministically, with
        no risk of draining that unrelated backlog."""
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", style="Diver"))
        records = load_collection(self.watches_dir)
        sidebar = Sidebar(records)
        sidebar.resize(260, 900)
        expanded_width = sidebar.width()

        sidebar._toggle_button.click()
        self.assertTrue(sidebar._scroll.isHidden())
        sidebar._width_animation.setCurrentTime(ANIM_DURATION_MS)
        self.assertLess(sidebar.width(), expanded_width)

        sidebar._toggle_button.click()
        self.assertFalse(sidebar._scroll.isHidden())
        sidebar._width_animation.setCurrentTime(ANIM_DURATION_MS)
        self.assertEqual(sidebar.width(), expanded_width)

    def test_toggle_button_stays_pinned_to_the_top_while_collapsed(self) -> None:
        """Regression: with only a horizontal alignment flag on the toggle
        button, hiding the scroll area let Qt vertically centre the button in
        the leftover space instead of leaving it pinned at the top."""
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", style="Diver"))
        records = load_collection(self.watches_dir)
        sidebar = Sidebar(records)
        sidebar.resize(260, 900)
        top_y = sidebar._toggle_button.geometry().y()

        sidebar._toggle_button.click()
        self.assertEqual(sidebar._toggle_button.geometry().y(), top_y)


class SidebarWishlistScopeTests(UITestCase):
    """SPEC.md §5.12: Status and Not-worn-90d are degenerate in Wishlist
    scope, and the summary footer swaps to the wishlist figures."""

    def test_status_facet_is_not_built_in_wishlist_scope(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", status="Wishlist"))
        records = load_collection(self.watches_dir)
        sidebar = Sidebar(records, is_wishlist=True)
        self.assertEqual([k for k in sidebar._checkboxes if k[0] == "status"], [])

    def test_not_worn_checkbox_is_absent_in_wishlist_scope(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", status="Wishlist"))
        records = load_collection(self.watches_dir)
        sidebar = Sidebar(records, is_wishlist=True)
        self.assertIsNone(sidebar._not_worn_checkbox)

    def test_status_facet_still_builds_in_collection_scope(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Omega", model="Speedmaster", status="Sold"))
        records = load_collection(self.watches_dir)
        sidebar = Sidebar(records, is_wishlist=False)
        self.assertIn(("status", "Owned"), sidebar._checkboxes)
        self.assertIn(("status", "Sold"), sidebar._checkboxes)

    def test_wishlist_summary_footer_shows_target_price_not_acquisition_value(self) -> None:
        create_watch(
            self.watches_dir, self.backups_dir,
            Watch(brand="Seiko", model="SARB033", status="Wishlist", acquisition=Acquisition(target_price=500, currency="USD")),
        )
        records = load_collection(self.watches_dir)
        sidebar = Sidebar(records, is_wishlist=True)
        texts = [label.text() for label in sidebar._summary_footer.findChildren(QLabel)]
        self.assertIn("1 watch", texts)
        self.assertIn("500.00 USD", texts)


class SidebarSummaryFooterTests(UITestCase):
    """SPEC.md §5.10: the summary always reflects the whole collection, not
    whatever the facet checkboxes above it currently narrow the view to."""

    def test_singular_count_for_one_watch(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        sidebar = Sidebar(load_collection(self.watches_dir))
        texts = [label.text() for label in sidebar._summary_footer.findChildren(QLabel)]
        self.assertIn("1 watch", texts)

    def test_plural_count_and_movement_kind_split(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", movement=Movement(kind="Automatic")))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Casio", model="F-91W", movement=Movement(kind="Quartz")))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Omega", model="Speedmaster", movement=Movement(kind="Automatic")))
        sidebar = Sidebar(load_collection(self.watches_dir))
        texts = [label.text() for label in sidebar._summary_footer.findChildren(QLabel)]
        self.assertIn("3 watches", texts)
        self.assertIn("Automatic 2 · Quartz 1", texts)

    def test_no_currency_line_when_no_watch_has_a_price(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        sidebar = Sidebar(load_collection(self.watches_dir))
        texts = [label.text() for label in sidebar._summary_footer.findChildren(QLabel)]
        self.assertFalse(any("TRY" in t or "USD" in t for t in texts))

    def test_collapsing_hides_the_footer_and_expanding_restores_it(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        sidebar = Sidebar(load_collection(self.watches_dir))

        sidebar._toggle_button.click()
        self.assertTrue(sidebar._summary_footer.isHidden())

        sidebar._toggle_button.click()
        self.assertFalse(sidebar._summary_footer.isHidden())


class SidebarStyledBackgroundTests(UITestCase):
    """See TopBarStyledBackgroundTests in test_ui.py — same class of bug: a
    plain QWidget subclass needs WA_StyledBackground or its QSS border-right
    silently never paints, invisible to any test that only inspects the
    widget tree instead of rendered pixels."""

    def test_sidebar_has_styled_background_enabled(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        records = load_collection(self.watches_dir)
        sidebar = Sidebar(records)
        self.assertTrue(sidebar.testAttribute(Qt.WidgetAttribute.WA_StyledBackground))


class SidebarClearFiltersTests(UITestCase):
    """Milestone 16c: a small new control, since none existed before — hidden
    until at least one filter is active, and it must clear every kind
    (facet checkboxes and the "not worn" checkbox alike) in one click."""

    def setUp(self) -> None:
        super().setUp()
        create_watch(
            self.watches_dir, self.backups_dir,
            Watch(brand="Seiko", model="SARB033", style="Dress"),
        )
        self.records = load_collection(self.watches_dir)

    def test_hidden_with_no_active_filters(self) -> None:
        sidebar = Sidebar(self.records)
        self.assertTrue(sidebar._clear_filters_button.isHidden())

    def test_becomes_visible_once_a_facet_is_checked(self) -> None:
        sidebar = Sidebar(self.records)
        sidebar._checkboxes[("style", "Dress")].setChecked(True)
        self.assertFalse(sidebar._clear_filters_button.isHidden())

    def test_clicking_it_unchecks_every_facet_and_hides_itself_again(self) -> None:
        sidebar = Sidebar(self.records)
        sidebar._checkboxes[("style", "Dress")].setChecked(True)

        sidebar._clear_filters_button.click()

        self.assertFalse(sidebar._checkboxes[("style", "Dress")].isChecked())
        self.assertTrue(sidebar._clear_filters_button.isHidden())

    def test_clicking_it_only_emits_changed_once(self) -> None:
        """Checking two facets then clearing both must not fire changed
        once per checkbox — CollectionView listens to recompute, and a
        multi-fire would just be N redundant passes over the same data."""
        sidebar = Sidebar(self.records)
        sidebar._checkboxes[("style", "Dress")].setChecked(True)
        received = []
        sidebar.changed.connect(lambda: received.append(None))

        sidebar._clear_filters_button.click()

        self.assertEqual(len(received), 1)


class CollectionViewFilteringTests(UITestCase):
    def setUp(self) -> None:
        super().setUp()
        create_watch(
            self.watches_dir, self.backups_dir,
            Watch(brand="Seiko", model="SKX007", style="Diver", movement=Movement(kind="Automatic")),
        )
        create_watch(
            self.watches_dir, self.backups_dir,
            Watch(brand="Omega", model="De Ville", style="Dress", movement=Movement(kind="Quartz")),
        )
        self.records = load_collection(self.watches_dir)

    def test_search_narrows_the_rendered_grid(self) -> None:
        view = CollectionView(self.records, self._config())
        view._top_bar._search_field.setText("skx")
        self.assertEqual(len(view._grid_view._cards), 1)
        self.assertEqual(view._grid_view._cards[0]._record.watch.brand, "Seiko")

    def test_records_property_stays_full_collection_while_search_is_active(self) -> None:
        view = CollectionView(self.records, self._config())
        view._top_bar._search_field.setText("skx")
        self.assertEqual(len(view.records), 2)

    def test_checking_a_facet_value_narrows_the_rendered_grid(self) -> None:
        view = CollectionView(self.records, self._config())
        view._sidebar._checkboxes[("style", "Diver")].setChecked(True)
        self.assertEqual(len(view._grid_view._cards), 1)
        self.assertEqual(view._grid_view._cards[0]._record.watch.style, "Diver")

    def test_a_facets_own_counts_ignore_its_own_active_selection(self) -> None:
        """Regression: counting a facet's values against the already-filtered
        set would zero out every value but the one just checked, making a
        second value in the same facet impossible to select — breaking the
        multi-select the spec requires."""
        view = CollectionView(self.records, self._config())
        view._sidebar._checkboxes[("style", "Diver")].setChecked(True)

        self.assertEqual(view._sidebar._checkboxes[("style", "Diver")].text(), "Diver (1)")
        self.assertEqual(view._sidebar._checkboxes[("style", "Dress")].text(), "Dress (1)")

    def test_a_different_facets_counts_do_reflect_the_active_selection(self) -> None:
        view = CollectionView(self.records, self._config())
        view._sidebar._checkboxes[("style", "Diver")].setChecked(True)

        self.assertEqual(view._sidebar._checkboxes[("movement_kind", "Automatic")].text(), "Automatic (1)")
        self.assertEqual(view._sidebar._checkboxes[("movement_kind", "Quartz")].text(), "Quartz (0)")

    def test_selecting_two_values_in_the_same_facet_ors_them(self) -> None:
        view = CollectionView(self.records, self._config())
        view._sidebar._checkboxes[("style", "Diver")].setChecked(True)
        view._sidebar._checkboxes[("style", "Dress")].setChecked(True)
        self.assertEqual(len(view._grid_view._cards), 2)

    def test_malformed_record_is_hidden_once_a_filter_is_active(self) -> None:
        broken = self.watches_dir / "broken"
        broken.mkdir()
        (broken / "watch.toml").write_text("brand = ][not valid toml", encoding="utf-8")
        records = load_collection(self.watches_dir)

        view = CollectionView(records, self._config())
        self.assertEqual(len(view._grid_view._cards), 3)  # shown while unfiltered

        view._top_bar._search_field.setText("skx")
        self.assertEqual(len(view._grid_view._cards), 1)  # broken record dropped

    def test_least_worn_sort_puts_never_worn_before_previously_worn(self) -> None:
        from datetime import date

        create_watch(
            self.watches_dir, self.backups_dir,
            Watch(brand="Casio", model="F-91W", worn=[date(2020, 1, 1)]),
        )
        records = load_collection(self.watches_dir)
        view = CollectionView(records, self._config())
        view._on_sort_changed("least_worn")
        brands_in_order = [view._grid_view._cards[i]._record.watch.brand for i in range(3)]
        self.assertEqual(brands_in_order[-1], "Casio")  # the only ever-worn watch sorts last


if __name__ == "__main__":
    unittest.main()
