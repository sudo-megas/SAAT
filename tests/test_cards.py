import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from PySide6.QtCore import QAbstractAnimation, QEvent, QPoint
from PySide6.QtGui import QColor, QEnterEvent
from PySide6.QtWidgets import QApplication, QLabel

from saat.models import Acquisition, LogEntry, Maintenance, Watch
from saat.storage import create_watch, load_collection
from saat.ui import theme
from saat.ui.cards import WatchCard, _MaintenanceDueDot
from saat.ui.theme import ANIM_DURATION_MS

_app = QApplication.instance() or QApplication([])


def _close(a: QColor, b: QColor, tolerance: int = 30) -> bool:
    return abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue()) < tolerance


def _hover(card: WatchCard, entering: bool) -> None:
    """enterEvent/leaveEvent need a real QEnterEvent/QEvent with scene
    coordinates that aren't worth constructing for a unit test — drive the
    same state+recompute the handlers themselves call."""
    card._hovering = entering
    card._update_overlay_visibility()


def _enter(card: WatchCard) -> None:
    """The real enterEvent, unlike _hover() above, needs an actual
    QEnterEvent — it's what's under test in WatchCardHoverBorderAnimationTests
    below, so unlike _hover() it can't be shortcut."""
    pos = QPoint(10, 10)
    card.enterEvent(QEnterEvent(pos, pos, card.mapToGlobal(pos)))


def _leave(card: WatchCard) -> None:
    card.leaveEvent(QEvent(QEvent.Type.Leave))


def _border_pixel(card: WatchCard) -> QColor:
    """Top edge, inset past the rounded corner -- the one place the 1px
    border is guaranteed to be a solid, unaliased run of its full color."""
    image = card.grab().toImage()
    return image.pixelColor(image.width() // 2, 0)


class WatchCardMaintenanceDotTests(unittest.TestCase):
    """SPEC.md §4: 'a small gilt dot' on the grid card, silent otherwise."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-card-maintenance-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_dot_when_nothing_is_due(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        [record] = load_collection(self.watches_dir)
        card = WatchCard(record)
        self.assertIsNone(card.findChild(_MaintenanceDueDot))

    def test_dot_appears_when_service_is_overdue(self) -> None:
        watch = Watch(
            brand="Seiko", model="SARB033",
            maintenance=Maintenance(service_interval_years=1),
            log=[LogEntry(date=date(2020, 1, 1), kind="Service")],
        )
        create_watch(self.watches_dir, self.backups_dir, watch)
        [record] = load_collection(self.watches_dir)
        card = WatchCard(record)
        self.assertIsNotNone(card.findChild(_MaintenanceDueDot))

    def test_a_broken_record_never_shows_a_dot(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        broken = self.watches_dir / "broken"
        broken.mkdir()
        (broken / "watch.toml").write_text("brand = ][not valid toml", encoding="utf-8")
        records = load_collection(self.watches_dir)
        broken_record = next(r for r in records if r.watch is None)

        card = WatchCard(broken_record)
        self.assertIsNone(card.findChild(_MaintenanceDueDot))


class WatchCardCompareAndWoreTodayTests(unittest.TestCase):
    """SPEC.md §5.2: 'Card hover reveals a "Wore this today" action and a
    compare checkbox.' A checked checkbox stays visible without hovering, so
    the user can see and undo their current selection at a glance."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-card-compare-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        [self.record] = load_collection(self.watches_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_checkbox_and_wore_today_bar_are_hidden_by_default(self) -> None:
        card = WatchCard(self.record)
        card.show()
        self.assertFalse(card._checkbox.isVisible())
        self.assertFalse(card._wore_today_bar.isVisible())

    def test_hovering_reveals_both_and_leaving_hides_them_again(self) -> None:
        card = WatchCard(self.record)
        card.show()
        _hover(card, entering=True)
        self.assertTrue(card._checkbox.isVisible())
        self.assertTrue(card._wore_today_bar.isVisible())

        _hover(card, entering=False)
        self.assertFalse(card._checkbox.isVisible())
        self.assertFalse(card._wore_today_bar.isVisible())

    def test_a_checked_checkbox_stays_visible_after_the_mouse_leaves(self) -> None:
        card = WatchCard(self.record)
        card.show()
        _hover(card, entering=True)
        card._checkbox.setChecked(True)
        _hover(card, entering=False)
        self.assertTrue(card._checkbox.isVisible())
        self.assertFalse(card._wore_today_bar.isVisible())  # the wore-today bar is hover-only, not selection-sticky

    def test_constructing_with_compare_selected_starts_checked_and_visible(self) -> None:
        card = WatchCard(self.record, compare_selected=True)
        card.show()
        self.assertTrue(card._checkbox.isChecked())
        self.assertTrue(card._checkbox.isVisible())

    def test_toggling_the_checkbox_emits_compare_toggled_with_the_record(self) -> None:
        card = WatchCard(self.record)
        received = []
        card.compare_toggled.connect(lambda record, checked: received.append((record.slug, checked)))
        card._checkbox.setChecked(True)
        card._checkbox.setChecked(False)
        self.assertEqual(received, [(self.record.slug, True), (self.record.slug, False)])

    def test_clicking_the_checkbox_does_not_also_activate_the_card(self) -> None:
        card = WatchCard(self.record)
        activated = []
        card.activated.connect(lambda r: activated.append(r))
        card._checkbox.click()
        self.assertEqual(activated, [])

    def test_clicking_wore_today_emits_the_request_and_not_activation(self) -> None:
        card = WatchCard(self.record)
        wore_today = []
        activated = []
        card.wore_today_requested.connect(lambda r: wore_today.append(r))
        card.activated.connect(lambda r: activated.append(r))
        card._wore_today_bar.click()
        self.assertEqual([r.slug for r in wore_today], [self.record.slug])
        self.assertEqual(activated, [])


class WatchCardWishlistPresentationTests(unittest.TestCase):
    """SPEC.md §5.12: a non-Owned card has no wear affordances; a Wishlist
    card shows target price + rating in the slot the Wore-today bar would
    otherwise occupy, always visible rather than hover-only."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-card-wishlist-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_wishlist_card_has_no_wore_today_bar(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", status="Wishlist"))
        [record] = load_collection(self.watches_dir)
        card = WatchCard(record)
        self.assertIsNone(card._wore_today_bar)

    def test_wishlist_card_ignores_maintenance_due(self) -> None:
        watch = Watch(
            brand="Seiko", model="SARB033", status="Wishlist",
            maintenance=Maintenance(service_interval_years=1),
            log=[LogEntry(date=date(2020, 1, 1), kind="Service")],
        )
        create_watch(self.watches_dir, self.backups_dir, watch)
        [record] = load_collection(self.watches_dir)
        card = WatchCard(record)
        self.assertIsNone(card.findChild(_MaintenanceDueDot))

    def test_wishlist_card_shows_target_price_and_rating(self) -> None:
        watch = Watch(
            brand="Seiko", model="SARB033", status="Wishlist", rating=3,
            acquisition=Acquisition(target_price=650, currency="USD"),
        )
        create_watch(self.watches_dir, self.backups_dir, watch)
        [record] = load_collection(self.watches_dir)
        card = WatchCard(record)
        labels = [label.text() for label in card.findChildren(QLabel) if label.property("class") == "card-wishlist-info-bar"]
        self.assertEqual(len(labels), 1)
        self.assertIn("650.00 USD", labels[0])
        self.assertIn("★★★☆☆", labels[0])

    def test_wishlist_card_shows_em_dashes_when_target_price_and_rating_are_absent(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", status="Wishlist"))
        [record] = load_collection(self.watches_dir)
        card = WatchCard(record)
        labels = [label.text() for label in card.findChildren(QLabel) if label.property("class") == "card-wishlist-info-bar"]
        self.assertEqual(labels, ["—  ·  —"])

    def test_a_non_owned_non_wishlist_card_has_neither_bar(self) -> None:
        """Sold/Incoming/Gifted: no wear affordance (not Owned) and no
        wishlist info bar (not Wishlist either)."""
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", status="Sold"))
        [record] = load_collection(self.watches_dir)
        card = WatchCard(record)
        self.assertIsNone(card._wore_today_bar)
        self.assertEqual([label for label in card.findChildren(QLabel) if label.property("class") == "card-wishlist-info-bar"], [])


class WatchCardHoverBorderAnimationTests(unittest.TestCase):
    """Milestone 16d (SPEC.md §6 motion): the card border eases between
    rule@ and gilt@ on hover rather than snapping — QSS has no transition
    primitive, so WatchCard.paintEvent draws this border itself, driven by
    a QVariantAnimation. Driven via setCurrentTime(), not QTest.qWait(): see
    tests/test_sidebar.py's width test for why a real wait is avoided here."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-card-hover-border-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        [self.record] = load_collection(self.watches_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_border_is_rule_colored_at_rest(self) -> None:
        card = WatchCard(self.record)
        card.show()
        self.assertTrue(_close(_border_pixel(card), QColor(theme.colors().rule)))

    def test_entering_hover_starts_an_animation_toward_gilt(self) -> None:
        card = WatchCard(self.record)
        card.show()
        _enter(card)
        self.assertEqual(card._border_animation.state(), QAbstractAnimation.State.Running)
        self.assertEqual(QColor(card._border_animation.endValue()), QColor(theme.colors().gilt))

    def test_border_reaches_gilt_once_the_hover_animation_completes(self) -> None:
        card = WatchCard(self.record)
        card.show()
        _enter(card)
        card._border_animation.setCurrentTime(ANIM_DURATION_MS)
        self.assertTrue(_close(_border_pixel(card), QColor(theme.colors().gilt)))

    def test_leaving_hover_animates_the_border_back_to_rule(self) -> None:
        card = WatchCard(self.record)
        card.show()
        _enter(card)
        card._border_animation.setCurrentTime(ANIM_DURATION_MS)
        _leave(card)
        card._border_animation.setCurrentTime(ANIM_DURATION_MS)
        self.assertTrue(_close(_border_pixel(card), QColor(theme.colors().rule)))

    def test_cursor_focused_hover_does_not_crash_and_still_paints(self) -> None:
        """Cursor-focus's own 2px gilt@ QSS border wins outright (see
        paintEvent) -- this just guards the early-return path against
        raising when both states are true at once, not its exact pixels."""
        card = WatchCard(self.record)
        card.setProperty("cursor-focused", True)
        card.show()
        _enter(card)
        card._border_animation.setCurrentTime(ANIM_DURATION_MS)
        card.grab()  # must not raise


if __name__ == "__main__":
    unittest.main()
