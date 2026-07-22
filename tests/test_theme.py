import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from saat.config import Config
from saat.models import Watch
from saat.storage import create_watch
from saat.ui import theme
from saat.ui.collection_view import CollectionView
from saat.ui.main_window import MainWindow
from saat.ui.theme import MODE_DARK, MODE_LIGHT, apply_theme

_app = QApplication.instance() or QApplication([])


class ThemeModeResetMixin:
    """theme.py's current mode is process-global — any test that changes it
    must restore MODE_DARK afterward or it leaks into unrelated tests."""

    def tearDown(self) -> None:
        theme.set_mode(MODE_DARK)
        super().tearDown()


class PaletteAndModeTests(ThemeModeResetMixin, unittest.TestCase):
    def test_default_mode_is_dark(self) -> None:
        self.assertEqual(theme.current_mode(), MODE_DARK)

    def test_dark_colors_match_spec(self) -> None:
        self.assertEqual(theme.colors().plate, "#1C1B19")
        self.assertEqual(theme.colors().gilt, "#C9A227")

    def test_switching_mode_switches_the_returned_palette(self) -> None:
        theme.set_mode(MODE_LIGHT)
        self.assertEqual(theme.current_mode(), MODE_LIGHT)
        self.assertEqual(theme.colors().plate, "#F1EEE6")

    def test_every_field_differs_between_the_two_palettes(self) -> None:
        theme.set_mode(MODE_DARK)
        dark = theme.colors()
        theme.set_mode(MODE_LIGHT)
        light = theme.colors()
        for field in ("plate", "plate_high", "rule", "text", "text_muted", "gilt", "ruby"):
            self.assertNotEqual(getattr(dark, field), getattr(light, field), field)

    def test_setting_an_unknown_mode_raises(self) -> None:
        with self.assertRaises(ValueError):
            theme.set_mode("sepia")


class ApplyThemeStylesheetTests(ThemeModeResetMixin, unittest.TestCase):
    def test_apply_theme_with_a_mode_regenerates_the_stylesheet(self) -> None:
        apply_theme(_app, MODE_DARK)
        dark_sheet = _app.styleSheet()
        apply_theme(_app, MODE_LIGHT)
        light_sheet = _app.styleSheet()

        self.assertIn("#1C1B19", dark_sheet)
        self.assertIn("#F1EEE6", light_sheet)
        self.assertNotEqual(dark_sheet, light_sheet)

    def test_toggling_twice_returns_to_the_original_stylesheet(self) -> None:
        apply_theme(_app, MODE_DARK)
        original = _app.styleSheet()
        apply_theme(_app, MODE_LIGHT)
        apply_theme(_app, MODE_DARK)
        self.assertEqual(_app.styleSheet(), original)

    def test_omitting_mode_keeps_whatever_mode_is_already_current(self) -> None:
        theme.set_mode(MODE_LIGHT)
        apply_theme(_app)
        self.assertIn("#F1EEE6", _app.styleSheet())


class ConfigThemeModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-theme-config-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_unset_theme_mode_is_none(self) -> None:
        config = Config(self.tmp / "config.toml")
        self.assertIsNone(config.theme_mode())

    def test_theme_mode_round_trips_through_save_and_reload(self) -> None:
        path = self.tmp / "config.toml"
        config = Config(path)
        config.set_theme_mode(MODE_LIGHT)
        config.save()

        reloaded = Config(path)
        self.assertEqual(reloaded.theme_mode(), MODE_LIGHT)


class TopBarToggleTests(ThemeModeResetMixin, unittest.TestCase):
    def test_clicking_the_toggle_emits_theme_toggle_requested(self) -> None:
        from saat.ui.top_bar import TopBar

        bar = TopBar()
        bar.resize(1400, 60)
        bar.show()
        QApplication.processEvents()

        received = []
        bar.theme_toggle_requested.connect(lambda: received.append(True))

        QTest.mouseClick(bar._theme_toggle, Qt.MouseButton.LeftButton)

        self.assertEqual(len(received), 1)
        bar.close()

    def test_toggle_widget_repaints_without_error_in_both_modes(self) -> None:
        """The glyph branches on theme.current_mode() inside paintEvent —
        make sure both branches (sun and moon-via-path-subtraction) actually
        run clean, not just whichever mode happens to be active by default."""
        from saat.ui.top_bar import TopBar

        bar = TopBar()
        theme.set_mode(MODE_DARK)
        bar._theme_toggle.repaint()
        theme.set_mode(MODE_LIGHT)
        bar._theme_toggle.repaint()


class CollectionViewBubblesToggleTests(ThemeModeResetMixin, unittest.TestCase):
    def test_collection_view_re_emits_the_top_bars_toggle_signal(self) -> None:
        config = Config(Path(tempfile.mktemp(suffix=".toml")))
        view = CollectionView([], config)

        received = []
        view.theme_toggle_requested.connect(lambda: received.append(True))
        view._top_bar.theme_toggle_requested.emit()

        self.assertEqual(len(received), 1)


class EndToEndThemeToggleTests(ThemeModeResetMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-theme-flow-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.config_path = self.tmp / "config.toml"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def test_toggling_through_the_real_window_persists_and_a_fresh_launch_restores_it(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))

        config = Config(self.config_path)
        apply_theme(_app, config.theme_mode() or MODE_DARK)
        window = MainWindow(self.watches_dir, self.backups_dir, config)
        collection_view = window.centralWidget().currentWidget()

        self.assertEqual(theme.current_mode(), MODE_DARK)
        collection_view._top_bar.theme_toggle_requested.emit()

        self.assertEqual(theme.current_mode(), MODE_LIGHT)
        reloaded_config = Config(self.config_path)
        self.assertEqual(reloaded_config.theme_mode(), MODE_LIGHT)

        # Simulate a fresh process launch: reset the in-memory mode to what a
        # new process would start with, then run main.py's exact startup
        # sequence against the same config path.
        theme.set_mode(MODE_DARK)
        fresh_config = Config(self.config_path)
        apply_theme(_app, fresh_config.theme_mode() or MODE_DARK)
        MainWindow(self.watches_dir, self.backups_dir, fresh_config)

        self.assertEqual(theme.current_mode(), MODE_LIGHT)


if __name__ == "__main__":
    unittest.main()
