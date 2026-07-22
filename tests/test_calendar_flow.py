import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog

from saat.config import Config
from saat.models import Watch
from saat.storage import load_collection
from saat.storage import create_watch
from saat.ui.collection_view import CollectionView
from saat.ui.detail_view import DetailView
from saat.ui.main_window import MainWindow
from saat.ui.top_bar import VIEW_CALENDAR
from saat.ui.watch_picker import WatchPicker

_app = QApplication.instance() or QApplication([])


class UITestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-calendar-flow-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _config(self) -> Config:
        return Config(self.tmp / "config.toml")


def _pick(record):
    def _exec(self):
        self._chosen = record
        self._cleared = False
        return QDialog.DialogCode.Accepted
    return _exec


class EndToEndAssignPreservesMonthTests(UITestCase):
    def test_assigning_a_day_through_the_real_window_writes_to_disk_and_keeps_the_navigated_month(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()
        self.assertIsInstance(collection_view, CollectionView)

        collection_view._top_bar.set_view(VIEW_CALENDAR)
        calendar_view = collection_view._calendar_view
        calendar_view._go_next()
        calendar_view._go_next()
        calendar_view._go_next()
        navigated_year, navigated_month = calendar_view._year, calendar_view._month

        [record] = load_collection(self.watches_dir)
        target_day = date(navigated_year, navigated_month, 15)

        with patch.object(WatchPicker, "exec", _pick(record)):
            calendar_view._on_range_chosen([target_day])

        # Still the SAME CollectionView/CalendarView instance — no full
        # MainWindow reload — and still showing the month the user navigated to.
        self.assertIs(window.centralWidget().currentWidget(), collection_view)
        self.assertIs(collection_view._calendar_view, calendar_view)
        self.assertEqual((calendar_view._year, calendar_view._month), (navigated_year, navigated_month))

        [reloaded] = load_collection(self.watches_dir)
        self.assertEqual(reloaded.watch.worn, [target_day])

    def test_grid_and_sidebar_reflect_the_change_without_a_full_reload(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()
        calendar_view = collection_view._calendar_view

        [record] = load_collection(self.watches_dir)
        with patch.object(WatchPicker, "exec", _pick(record)):
            calendar_view._on_range_chosen([date.today()])

        # records property (used by the form's enum* suggestions) sees the update.
        [updated] = collection_view.records
        self.assertEqual(updated.watch.worn, [date.today()])

    def test_clearing_a_day_through_the_real_window(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", worn=[date.today()]))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()
        calendar_view = collection_view._calendar_view

        def _clear(self):
            self._cleared = True
            return QDialog.DialogCode.Accepted

        with patch.object(WatchPicker, "exec", _clear):
            calendar_view._on_range_chosen([date.today()])

        [reloaded] = load_collection(self.watches_dir)
        self.assertEqual(reloaded.watch.worn, [])

    def test_one_watch_per_day_when_assigned_from_the_real_window(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", worn=[date.today()]))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Omega", model="Speedmaster"))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()
        calendar_view = collection_view._calendar_view

        omega = next(r for r in load_collection(self.watches_dir) if r.watch.brand == "Omega")
        with patch.object(WatchPicker, "exec", _pick(omega)):
            calendar_view._on_range_chosen([date.today()])

        reloaded = {r.watch.brand: r.watch.worn for r in load_collection(self.watches_dir)}
        self.assertEqual(reloaded["Seiko"], [])
        self.assertEqual(reloaded["Omega"], [date.today()])


class WoreTodayFromDetailViewTests(UITestCase):
    def test_clicking_wore_today_persists_and_refreshes_the_same_detail_page(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()
        [record] = collection_view.records

        collection_view.record_activated.emit(record)
        detail_view = window.centralWidget().currentWidget()
        self.assertIsInstance(detail_view, DetailView)

        detail_view.wore_today_requested.emit(record)

        current = window.centralWidget().currentWidget()
        self.assertIsInstance(current, DetailView)
        self.assertEqual(current.record.watch.worn, [date.today()])

        [reloaded] = load_collection(self.watches_dir)
        self.assertEqual(reloaded.watch.worn, [date.today()])

    def test_clicking_it_twice_is_a_no_op(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()
        [record] = collection_view.records
        collection_view.record_activated.emit(record)
        detail_view = window.centralWidget().currentWidget()

        detail_view.wore_today_requested.emit(record)
        current = window.centralWidget().currentWidget()
        current.wore_today_requested.emit(current.record)

        final = window.centralWidget().currentWidget()
        self.assertEqual(final.record.watch.worn, [date.today()])


if __name__ == "__main__":
    unittest.main()
