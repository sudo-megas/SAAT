import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from PySide6.QtWidgets import QApplication

from saat.models import LogEntry, Maintenance, Watch
from saat.storage import create_watch, load_collection
from saat.ui.cards import WatchCard, _MaintenanceDueDot

_app = QApplication.instance() or QApplication([])


def _hover(card: WatchCard, entering: bool) -> None:
    """enterEvent/leaveEvent need a real QEnterEvent/QEvent with scene
    coordinates that aren't worth constructing for a unit test — drive the
    same state+recompute the handlers themselves call."""
    card._hovering = entering
    card._update_overlay_visibility()


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


if __name__ == "__main__":
    unittest.main()
