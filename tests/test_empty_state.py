import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from saat.config import Config
from saat.models import Watch
from saat.storage import create_watch
from saat.ui.empty_state import EmptyStateView
from saat.ui.main_window import MainWindow
from saat.ui.watch_dial import WatchDialWidget

_app = QApplication.instance() or QApplication([])


class EmptyStateCompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-empty-state-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dial_is_present_as_a_child(self) -> None:
        view = EmptyStateView(self.tmp / "watches")
        self.assertIsNotNone(view.findChild(WatchDialWidget))

    def test_dial_is_the_first_widget_in_the_layout(self) -> None:
        view = EmptyStateView(self.tmp / "watches")
        first_item = view.layout().itemAt(0).widget()
        self.assertIsInstance(first_item, WatchDialWidget)

    def test_existing_copy_is_unchanged(self) -> None:
        view = EmptyStateView(self.tmp / "watches")
        labels = [w.text() for w in view.findChildren(QLabel)]
        self.assertIn("Your collection is empty.", labels)
        self.assertIn(
            "Watches live in the watches/ folder as editable TOML files.\n"
            "Add your first one to get started.",
            labels,
        )

    def test_add_button_and_folder_link_still_present_and_wired(self) -> None:
        view = EmptyStateView(self.tmp / "watches")
        buttons = {b.text(): b for b in view.findChildren(QPushButton)}
        self.assertIn("Add watch", buttons)
        self.assertIn("Open watches/ folder", buttons)

        received = []
        view.add_watch_requested.connect(lambda: received.append(True))
        buttons["Add watch"].click()
        self.assertEqual(received, [True])


class DialTimerIntegrationTests(unittest.TestCase):
    """SPEC.md's own verification demand for this milestone: the dial's timer
    must provably stop once the collection is no longer empty -- an
    assertion against the real MainWindow reload path, not an eyeball check."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-dial-timer-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _config(self) -> Config:
        return Config(self.tmp / "config.toml")

    def test_dial_timer_stops_once_a_watch_is_added(self) -> None:
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        window.show()
        QApplication.processEvents()

        dial = window.centralWidget().currentWidget().findChild(WatchDialWidget)
        self.assertIsNotNone(dial, "expected the empty state to contain a WatchDialWidget")
        self.assertTrue(dial._timer.isActive(), "dial timer should be running while the empty state is shown")

        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="Test"))
        window._load_and_show_collection()
        QApplication.processEvents()

        self.assertFalse(dial._timer.isActive(), "dial timer must stop once the empty state is torn down")
        window.close()


if __name__ == "__main__":
    unittest.main()
