import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from saat import autostart
from saat.config import Config
from saat.models import Watch
from saat.storage import WatchRecord, create_watch, load_collection
from saat.ui.main_window import MainWindow
from saat.ui.tray import MAX_WORE_TODAY_ENTRIES, TrayController

_app = QApplication.instance() or QApplication([])

TODAY = date(2026, 7, 27)


def _record(slug: str, brand: str, model: str, worn: list[date] | None = None, status: str = "Owned") -> WatchRecord:
    return WatchRecord(
        slug=slug,
        path=Path(f"/nonexistent/{slug}"),
        watch=Watch(brand=brand, model=model, worn=worn or [], status=status),
    )


class TrayControllerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.visible = True
        self.tray = TrayController(window_visible_getter=lambda: self.visible)
        self.addCleanup(self.tray.hide)

    def _menu_actions(self, menu):
        return list(menu.actions())


class ShowHideLabelTests(TrayControllerTestCase):
    def test_label_is_hide_while_window_is_visible(self) -> None:
        self.visible = True
        self.tray._refresh_menu()
        self.assertEqual(self.tray._show_hide_action.text(), "Hide")

    def test_label_is_show_while_window_is_hidden(self) -> None:
        self.visible = False
        self.tray._refresh_menu()
        self.assertEqual(self.tray._show_hide_action.text(), "Show")

    def test_triggering_the_action_emits_show_hide_requested(self) -> None:
        received = []
        self.tray.show_hide_requested.connect(lambda: received.append(True))
        self.tray._show_hide_action.trigger()
        self.assertEqual(len(received), 1)


class ActivationReasonTests(TrayControllerTestCase):
    def test_left_click_trigger_emits_show_hide_requested(self) -> None:
        received = []
        self.tray.show_hide_requested.connect(lambda: received.append(True))
        self.tray._on_activated(QSystemTrayIcon.ActivationReason.Trigger)
        self.assertEqual(len(received), 1)

    def test_double_click_does_not_emit_show_hide_requested(self) -> None:
        received = []
        self.tray.show_hide_requested.connect(lambda: received.append(True))
        self.tray._on_activated(QSystemTrayIcon.ActivationReason.DoubleClick)
        self.assertEqual(len(received), 0)

    def test_context_menu_reason_does_not_emit_show_hide_requested(self) -> None:
        """Right click is handled entirely by Qt's own setContextMenu()
        plumbing -- this class must not double-fire show/hide for it."""
        received = []
        self.tray.show_hide_requested.connect(lambda: received.append(True))
        self.tray._on_activated(QSystemTrayIcon.ActivationReason.Context)
        self.assertEqual(len(received), 0)


class CheckableActionTests(TrayControllerTestCase):
    def test_toggling_close_to_tray_emits_close_to_tray_toggled(self) -> None:
        received = []
        self.tray.close_to_tray_toggled.connect(received.append)
        self.tray._close_to_tray_action.trigger()
        self.assertEqual(received, [True])

    def test_toggling_start_minimised_emits_start_minimised_toggled(self) -> None:
        received = []
        self.tray.start_minimised_toggled.connect(received.append)
        self.tray._start_minimised_action.trigger()
        self.assertEqual(received, [True])

    def test_set_close_to_tray_checked_seeds_initial_state(self) -> None:
        self.tray.set_close_to_tray_checked(True)
        self.assertTrue(self.tray._close_to_tray_action.isChecked())

    def test_set_start_minimised_checked_seeds_initial_state(self) -> None:
        self.tray.set_start_minimised_checked(True)
        self.assertTrue(self.tray._start_minimised_action.isChecked())


class StartAtLoginMenuItemTests(unittest.TestCase):
    """SPEC.md milestone 18 §11: hidden entirely in portable mode, not
    merely disabled -- and §14: reflects reality on every menu open, never
    a cached flag."""

    def test_absent_when_autostart_is_unavailable(self) -> None:
        tray = TrayController(window_visible_getter=lambda: True, autostart_available=False)
        self.addCleanup(tray.hide)
        self.assertIsNone(tray._start_at_login_action)

    def test_present_and_checkable_when_autostart_is_available(self) -> None:
        tray = TrayController(window_visible_getter=lambda: True, autostart_available=True)
        self.addCleanup(tray.hide)
        self.assertIsNotNone(tray._start_at_login_action)
        self.assertTrue(tray._start_at_login_action.isCheckable())

    def test_refresh_syncs_checked_state_from_disk_without_emitting_toggled(self) -> None:
        tray = TrayController(window_visible_getter=lambda: True, autostart_available=True)
        self.addCleanup(tray.hide)
        received = []
        tray.start_at_login_toggled.connect(received.append)

        with patch.object(autostart, "is_enabled", return_value=True):
            tray._refresh_menu()

        self.assertTrue(tray._start_at_login_action.isChecked())
        self.assertEqual(received, [], "a programmatic refresh must never re-trigger enable()/disable()")

    def test_refresh_reflects_disabled_state_too(self) -> None:
        tray = TrayController(window_visible_getter=lambda: True, autostart_available=True)
        self.addCleanup(tray.hide)
        with patch.object(autostart, "is_enabled", return_value=False):
            tray._refresh_menu()
        self.assertFalse(tray._start_at_login_action.isChecked())

    def test_a_real_user_click_emits_start_at_login_toggled(self) -> None:
        tray = TrayController(window_visible_getter=lambda: True, autostart_available=True)
        self.addCleanup(tray.hide)
        received = []
        tray.start_at_login_toggled.connect(received.append)

        tray._start_at_login_action.trigger()

        self.assertEqual(received, [True])


class WoreTodaySubmenuTests(TrayControllerTestCase):
    def test_empty_collection_shows_a_disabled_placeholder(self) -> None:
        self.tray.set_records([])
        self.tray._rebuild_wore_today_menu()
        [action] = self._menu_actions(self.tray._wore_today_menu)
        self.assertFalse(action.isEnabled())

    def test_non_owned_watches_are_excluded(self) -> None:
        self.tray.set_records([
            _record("wishlist-a", "Omega", "Seamaster", status="Wishlist"),
            _record("sold-a", "Seiko", "SKX007", status="Sold"),
        ])
        self.tray._rebuild_wore_today_menu()
        [action] = self._menu_actions(self.tray._wore_today_menu)
        self.assertFalse(action.isEnabled())

    def test_most_recently_worn_owned_watch_appears_first(self) -> None:
        older = [_record("a", "Seiko", "SKX007", worn=[TODAY - timedelta(days=10)])]
        newer = [_record("b", "Casio", "G-Shock", worn=[TODAY - timedelta(days=1)])]
        self.tray.set_records(older + newer)
        self.tray._rebuild_wore_today_menu()
        actions = self._menu_actions(self.tray._wore_today_menu)
        self.assertEqual([a.text() for a in actions], ["Casio G-Shock", "Seiko SKX007"])

    def test_never_worn_owned_watches_sort_after_worn_ones(self) -> None:
        worn = _record("a", "Seiko", "SKX007", worn=[TODAY])
        never_worn = _record("b", "Casio", "G-Shock", worn=[])
        self.tray.set_records([never_worn, worn])
        self.tray._rebuild_wore_today_menu()
        actions = self._menu_actions(self.tray._wore_today_menu)
        self.assertEqual([a.text() for a in actions], ["Seiko SKX007", "Casio G-Shock"])

    def test_capped_at_ten_entries(self) -> None:
        records = [
            _record(f"w{i}", "Brand", f"Model{i:02d}", worn=[TODAY - timedelta(days=i)])
            for i in range(15)
        ]
        self.tray.set_records(records)
        self.tray._rebuild_wore_today_menu()
        actions = self._menu_actions(self.tray._wore_today_menu)
        self.assertEqual(len(actions), MAX_WORE_TODAY_ENTRIES)
        # Most recent (smallest days-ago, i.e. i=0..9) survive the cap.
        self.assertEqual(actions[0].text(), "Brand Model00")

    def test_triggering_an_entry_emits_wore_today_requested_with_that_record(self) -> None:
        target = _record("a", "Seiko", "SKX007", worn=[])
        self.tray.set_records([target])
        self.tray._rebuild_wore_today_menu()
        received = []
        self.tray.wore_today_requested.connect(received.append)
        [action] = self._menu_actions(self.tray._wore_today_menu)
        action.trigger()
        self.assertEqual(received, [target])


class AppIconTests(unittest.TestCase):
    def test_icon_provides_pixmaps_at_common_tray_sizes(self) -> None:
        from saat.ui.tray import _app_icon

        icon = _app_icon()
        for size in (16, 22, 24, 32, 48, 64):
            with self.subTest(size=size):
                pixmap = icon.pixmap(size, size)
                self.assertFalse(pixmap.isNull())
                self.assertEqual(pixmap.width(), size)
                self.assertEqual(pixmap.height(), size)


# --- MainWindow integration ------------------------------------------------


class MainWindowTrayTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-tray-mainwindow-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()
        self._windows: list[MainWindow] = []

    def tearDown(self) -> None:
        # Each tray-enabled window starts a real, repeating poll QTimer
        # (_poll_tray_availability). Left running, it would keep firing
        # during later, unrelated tests' event-loop pumps once the whole
        # suite's wall-clock runtime passes the poll interval -- stop it
        # explicitly rather than trusting process teardown to happen first.
        # _tray is also forced to None before close() so this always takes
        # the real-quit path regardless of what close_to_tray a given test
        # configured, and deleteLater() actually releases the widget instead
        # of leaving dozens of hidden MainWindows alive for the rest of the
        # suite.
        for window in self._windows:
            if window._tray_poll_timer is not None:
                window._tray_poll_timer.stop()
            if window._tray is not None:
                window._tray.hide()
            window._tray = None
            window.close()
            window.deleteLater()
        QApplication.processEvents()
        super().tearDown()

    def _config(self) -> Config:
        return Config(self.tmp / "config.toml")

    def _window(self, tray_available: bool | None, config: Config | None = None) -> MainWindow:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="Test"))
        window = MainWindow(
            self.watches_dir, self.backups_dir, config or self._config(), tray_available=tray_available,
        )
        window.show()
        self._windows.append(window)
        return window


class CapabilityDetectionTests(MainWindowTrayTestCase):
    def test_tray_unavailable_means_no_tray_object(self) -> None:
        window = self._window(tray_available=False)
        self.assertIsNone(window._tray)

    def test_tray_available_means_a_tray_object_exists(self) -> None:
        window = self._window(tray_available=True)
        self.assertIsNotNone(window._tray)

    def test_no_tray_close_always_quits_even_if_close_to_tray_is_set(self) -> None:
        """Defends against config carried over from a session that did have
        a tray (or a hand-edited config.toml): without a tray object right
        now, close-to-tray must never be able to strand the user."""
        config = self._config()
        config.set_close_to_tray(True)
        config.save()
        window = self._window(tray_available=False, config=config)

        window.close()

        self.assertFalse(window.isVisible())


class CloseToTrayBehaviorTests(MainWindowTrayTestCase):
    def test_close_to_tray_off_by_default_closes_for_real(self) -> None:
        window = self._window(tray_available=True)
        window.close()
        self.assertFalse(window.isVisible())

    def test_close_to_tray_on_hides_instead_of_closing(self) -> None:
        config = self._config()
        config.set_close_to_tray(True)
        config.save()
        window = self._window(tray_available=True, config=config)
        self.assertTrue(window.isVisible())

        window.close()

        self.assertFalse(window.isVisible())
        # Still a live window (hidden, not torn down) -- e.g. the tray
        # object is untouched and the app did not quit.
        self.assertIsNotNone(window._tray)

    def test_close_to_tray_on_does_not_quit_the_application(self) -> None:
        config = self._config()
        config.set_close_to_tray(True)
        config.save()
        window = self._window(tray_available=True, config=config)

        with patch.object(_app, "quit") as mock_quit:
            window.close()

        mock_quit.assert_not_called()


class AlwaysQuitPathsTests(MainWindowTrayTestCase):
    """The bug this milestone's own review caught: Ctrl+Q and the tray's own
    Quit action must always quit, even with close-to-tray ON -- SPEC.md
    §5.11 and milestone 18 §7 both promise this unconditionally."""

    def test_ctrl_q_quits_even_with_close_to_tray_enabled(self) -> None:
        config = self._config()
        config.set_close_to_tray(True)
        config.save()
        window = self._window(tray_available=True, config=config)

        with patch.object(_app, "quit") as mock_quit:
            window._quit()

        mock_quit.assert_called_once()

    def test_tray_quit_action_quits_even_with_close_to_tray_enabled(self) -> None:
        config = self._config()
        config.set_close_to_tray(True)
        config.save()
        window = self._window(tray_available=True, config=config)

        with patch.object(_app, "quit") as mock_quit:
            window._tray.quit_requested.emit()

        mock_quit.assert_called_once()

    def test_quit_saves_window_geometry(self) -> None:
        window = self._window(tray_available=True)
        with patch.object(_app, "quit"):
            with patch.object(window, "_save_geometry") as mock_save:
                window._quit()
        mock_save.assert_called_once()


class HideToTrayHintTests(MainWindowTrayTestCase):
    def test_first_hide_shows_the_hint_and_persists_it(self) -> None:
        window = self._window(tray_available=True)
        with patch.object(window._tray, "supports_messages", return_value=True):
            with patch.object(window._tray, "show_hint_message") as mock_message:
                window._hide_to_tray()
        mock_message.assert_called_once()
        self.assertTrue(window._config.tray_hint_shown())

    def test_second_hide_does_not_show_the_hint_again(self) -> None:
        config = self._config()
        config.set_tray_hint_shown(True)
        config.save()
        window = self._window(tray_available=True, config=config)
        with patch.object(window._tray, "supports_messages", return_value=True):
            with patch.object(window._tray, "show_hint_message") as mock_message:
                window._hide_to_tray()
        mock_message.assert_not_called()

    def test_hint_is_not_marked_shown_if_the_host_cannot_deliver_it(self) -> None:
        """A platform that can't show tray messages today must not burn the
        one chance a future session (a new tray host) might have."""
        window = self._window(tray_available=True)
        with patch.object(window._tray, "supports_messages", return_value=False):
            with patch.object(window._tray, "show_hint_message") as mock_message:
                window._hide_to_tray()
        mock_message.assert_not_called()
        self.assertFalse(window._config.tray_hint_shown())


class TrayResilienceTests(MainWindowTrayTestCase):
    def test_tray_disappearing_while_hidden_restores_the_window(self) -> None:
        window = self._window(tray_available=True)
        window.hide()
        self.assertFalse(window.isVisible())

        with patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=False):
            window._poll_tray_availability()

        self.assertTrue(window.isVisible())
        self.assertIsNone(window._tray)

    def test_tray_disappearing_while_visible_does_not_force_a_state_change(self) -> None:
        window = self._window(tray_available=True)
        self.assertTrue(window.isVisible())

        with patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=False):
            window._poll_tray_availability()

        self.assertTrue(window.isVisible())
        self.assertIsNone(window._tray)

    def test_tray_staying_available_is_a_no_op(self) -> None:
        window = self._window(tray_available=True)
        with patch.object(QSystemTrayIcon, "isSystemTrayAvailable", return_value=True):
            window._poll_tray_availability()
        self.assertIsNotNone(window._tray)


class TraySyncRecordsTests(MainWindowTrayTestCase):
    def test_records_are_pushed_to_the_tray_on_load(self) -> None:
        window = self._window(tray_available=True)
        self.assertEqual(len(window._tray._records), 1)

    def test_wore_today_from_the_tray_updates_the_watch_on_disk(self) -> None:
        window = self._window(tray_available=True)
        [record] = load_collection(self.watches_dir)

        window._tray.wore_today_requested.emit(record)

        [reloaded] = load_collection(self.watches_dir)
        self.assertIn(date.today(), reloaded.watch.worn)


class AutostartMenuItemIntegrationTests(MainWindowTrayTestCase):
    def test_start_at_login_item_present_when_autostart_available(self) -> None:
        with patch.object(autostart, "is_available", return_value=True):
            window = self._window(tray_available=True)
        self.assertIsNotNone(window._tray._start_at_login_action)

    def test_start_at_login_item_absent_when_autostart_unavailable(self) -> None:
        with patch.object(autostart, "is_available", return_value=False):
            window = self._window(tray_available=True)
        self.assertIsNone(window._tray._start_at_login_action)

    def test_toggling_on_calls_autostart_enable(self) -> None:
        window = self._window(tray_available=True)
        with patch.object(autostart, "enable") as mock_enable:
            window._on_start_at_login_toggled(True)
        mock_enable.assert_called_once()

    def test_toggling_off_calls_autostart_disable(self) -> None:
        window = self._window(tray_available=True)
        with patch.object(autostart, "disable") as mock_disable:
            window._on_start_at_login_toggled(False)
        mock_disable.assert_called_once()

    def test_a_failure_enabling_autostart_is_surfaced_not_swallowed(self) -> None:
        """SPEC.md §2 rule 7: never silently swallow an exception."""
        window = self._window(tray_available=True)
        with patch.object(autostart, "enable", side_effect=OSError("permission denied")):
            with patch.object(QMessageBox, "critical") as mock_critical:
                window._on_start_at_login_toggled(True)
        mock_critical.assert_called_once()

    def test_a_failure_disabling_autostart_is_surfaced_not_swallowed(self) -> None:
        window = self._window(tray_available=True)
        with patch.object(autostart, "disable", side_effect=OSError("permission denied")):
            with patch.object(QMessageBox, "critical") as mock_critical:
                window._on_start_at_login_toggled(False)
        mock_critical.assert_called_once()


class ShouldStartHiddenTests(MainWindowTrayTestCase):
    """SPEC.md milestone 18 §15: 'Start minimised' only ever affects an
    autostarted launch, never a manual one, and only when a tray actually
    exists right now -- starting hidden with nothing to restore from would
    strand the user exactly as badly as anything else in this milestone."""

    def test_false_when_tray_unavailable_even_if_autostarted_and_start_minimised(self) -> None:
        config = self._config()
        config.set_start_minimised(True)
        config.save()
        window = self._window(tray_available=False, config=config)
        self.assertFalse(window.should_start_hidden(started_via_autostart=True))

    def test_false_on_a_manual_launch_even_with_start_minimised_on(self) -> None:
        config = self._config()
        config.set_start_minimised(True)
        config.save()
        window = self._window(tray_available=True, config=config)
        self.assertFalse(window.should_start_hidden(started_via_autostart=False))

    def test_false_when_autostarted_but_start_minimised_is_off(self) -> None:
        window = self._window(tray_available=True)
        self.assertFalse(window.should_start_hidden(started_via_autostart=True))

    def test_true_only_when_tray_available_and_autostarted_and_start_minimised(self) -> None:
        config = self._config()
        config.set_start_minimised(True)
        config.save()
        window = self._window(tray_available=True, config=config)
        self.assertTrue(window.should_start_hidden(started_via_autostart=True))


if __name__ == "__main__":
    unittest.main()
