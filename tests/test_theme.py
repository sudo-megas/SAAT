import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontInfo
from PySide6.QtWidgets import QApplication

from saat.config import Config
from saat.models import Watch
from saat.storage import create_watch
from saat.ui import theme
from saat.ui.main_window import MainWindow
from saat.ui.theme import apply_theme

_app = QApplication.instance() or QApplication([])

# SPEC.md §6 item 8's exact list, order and ids -- the popover and every
# ordering-sensitive test check against this, not a hardcoded pair.
EXPECTED_PALETTE_ORDER = (
    "default-light",
    "default-dark",
    "noctalia",
    "catppuccin-latte",
    "catppuccin-frappe",
    "catppuccin-macchiato",
    "catppuccin-mocha",
    "rose-pine-dawn",
    "nord",
    "kanagawa-lotus",
)


class ThemeModeResetMixin:
    """theme.py's active palette id is process-global — any test that
    changes it must restore default-dark afterward or it leaks into
    unrelated tests."""

    def tearDown(self) -> None:
        theme.set_palette("default-dark")
        super().tearDown()


class PaletteRegistryTests(ThemeModeResetMixin, unittest.TestCase):
    def test_default_palette_is_default_dark(self) -> None:
        self.assertEqual(theme.current_palette_id(), "default-dark")

    def test_dark_colors_match_spec(self) -> None:
        self.assertEqual(theme.colors().plate, "#1C1B19")
        self.assertEqual(theme.colors().gilt, "#C9A227")

    def test_switching_palette_switches_the_returned_colors(self) -> None:
        theme.set_palette("default-light")
        self.assertEqual(theme.current_palette_id(), "default-light")
        self.assertEqual(theme.colors().plate, "#FAF8F5")

    def test_default_light_and_default_dark_differ_in_every_field(self) -> None:
        dark = theme.palette("default-dark").palette
        light = theme.palette("default-light").palette
        for field in ("plate", "plate_high", "rule", "text", "text_muted", "gilt", "ruby"):
            self.assertNotEqual(getattr(dark, field), getattr(light, field), field)

    def test_setting_an_unknown_palette_id_raises(self) -> None:
        with self.assertRaises(ValueError):
            theme.set_palette("sepia")

    def test_looking_up_an_unknown_palette_id_raises(self) -> None:
        with self.assertRaises(ValueError):
            theme.palette("sepia")

    def test_palettes_returns_all_ten_in_spec_order(self) -> None:
        self.assertEqual(tuple(entry.id for entry in theme.palettes()), EXPECTED_PALETTE_ORDER)

    def test_active_palette_tracks_set_palette(self) -> None:
        theme.set_palette("nord")
        self.assertEqual(theme.active_palette().id, "nord")
        self.assertIs(theme.active_palette().palette, theme.palette("nord").palette)

    def test_every_palette_has_an_is_dark_flag_and_a_non_empty_name(self) -> None:
        for entry in theme.palettes():
            with self.subTest(palette=entry.id):
                self.assertIsInstance(entry.is_dark, bool)
                self.assertTrue(entry.name)

    def test_display_name_translates_the_two_generic_defaults(self) -> None:
        # No translator installed in tests -- QCoreApplication.translate()
        # with nothing installed returns the source text unchanged, so this
        # also confirms the English source strings are exactly right.
        self.assertEqual(theme.display_name(theme.palette("default-dark")), "Default Dark")
        self.assertEqual(theme.display_name(theme.palette("default-light")), "Default Light")

    def test_display_name_passes_proper_nouns_through_untranslated(self) -> None:
        self.assertEqual(theme.display_name(theme.palette("nord")), "Nord")
        self.assertEqual(theme.display_name(theme.palette("catppuccin-mocha")), "Catppuccin Mocha")

    def test_paper_is_not_part_of_the_registry(self) -> None:
        self.assertNotIn(theme.PAPER, [entry.palette for entry in theme.palettes()])
        with self.assertRaises(ValueError):
            theme.palette("paper")


class ApplyThemeStylesheetTests(ThemeModeResetMixin, unittest.TestCase):
    def test_apply_theme_with_a_palette_id_regenerates_the_stylesheet(self) -> None:
        apply_theme(_app, "default-dark")
        dark_sheet = _app.styleSheet()
        apply_theme(_app, "default-light")
        light_sheet = _app.styleSheet()

        self.assertIn("#1C1B19", dark_sheet)
        self.assertIn("#FAF8F5", light_sheet)
        self.assertNotEqual(dark_sheet, light_sheet)

    def test_switching_and_back_returns_to_the_original_stylesheet(self) -> None:
        apply_theme(_app, "default-dark")
        original = _app.styleSheet()
        apply_theme(_app, "default-light")
        apply_theme(_app, "default-dark")
        self.assertEqual(_app.styleSheet(), original)

    def test_omitting_palette_id_keeps_whatever_is_already_current(self) -> None:
        theme.set_palette("default-light")
        apply_theme(_app)
        self.assertIn("#FAF8F5", _app.styleSheet())

    def test_switching_through_all_ten_palettes_produces_no_errors(self) -> None:
        for entry in theme.palettes():
            apply_theme(_app, entry.id)
            self.assertIn(entry.palette.plate, _app.styleSheet())


class LiveSwitchRepaintTests(ThemeModeResetMixin, unittest.TestCase):
    """SPEC.md §6: switching palette is live, no restart -- custom-painted
    (QPainter) widgets must pick up the new palette on their very next
    repaint, not just the QSS-driven stock widgets apply_theme()'s own
    setStyleSheet() call already handles for free."""

    def test_minute_track_header_repaints_without_error_across_a_switch(self) -> None:
        from saat.ui.minute_track import MinuteTrackHeader

        header = MinuteTrackHeader("Movement")
        apply_theme(_app, "nord")
        header.repaint()
        apply_theme(_app, "catppuccin-latte")
        header.repaint()

    def test_a_live_watched_widget_actually_reflects_the_new_palettes_color(self) -> None:
        # _PaletteSwatch(entry=None) reads theme.colors() fresh at paint
        # time (palette_picker.py) -- unlike _ThemeToggle, this one survives
        # Milestone 21b-e, so it's the live widget worth pinning here.
        from saat.ui.palette_picker import _PaletteSwatch

        swatch = _PaletteSwatch(entry=None)
        apply_theme(_app, "nord")
        swatch.repaint()
        QApplication.processEvents()
        nord_pixel = swatch.grab().toImage().pixelColor(3, 3)

        apply_theme(_app, "catppuccin-latte")
        swatch.repaint()
        QApplication.processEvents()
        latte_pixel = swatch.grab().toImage().pixelColor(3, 3)

        # Sampled pixel (the leftmost "plate" dot) must actually change
        # colour, and match each palette's own plate exactly -- not just
        # "differ", which a rendering glitch could also produce.
        self.assertNotEqual(nord_pixel.name(), latte_pixel.name())
        self.assertEqual(nord_pixel.name(), QColor(theme.palette("nord").palette.plate).name())
        self.assertEqual(latte_pixel.name(), QColor(theme.palette("catppuccin-latte").palette.plate).name())


class ConfigPaletteIdTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-theme-config-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_unset_palette_id_defaults_to_default_dark(self) -> None:
        config = Config(self.tmp / "config.toml")
        self.assertEqual(config.palette_id(), "default-dark")

    def test_palette_id_round_trips_through_save_and_reload(self) -> None:
        path = self.tmp / "config.toml"
        config = Config(path)
        config.set_palette_id("default-light")
        config.save()

        reloaded = Config(path)
        self.assertEqual(reloaded.palette_id(), "default-light")

    def test_old_theme_mode_light_migrates_once_to_default_light(self) -> None:
        path = self.tmp / "config.toml"
        path.write_text('[theme]\nmode = "light"\n', encoding="utf-8")

        config = Config(path)
        self.assertEqual(config.palette_id(), "default-light")

        on_disk = path.read_text(encoding="utf-8")
        self.assertIn("[palette]", on_disk)
        self.assertIn('id = "default-light"', on_disk)
        self.assertNotIn("[theme]", on_disk)

    def test_old_theme_mode_dark_migrates_once_to_default_dark(self) -> None:
        path = self.tmp / "config.toml"
        path.write_text('[theme]\nmode = "dark"\n', encoding="utf-8")

        config = Config(path)
        self.assertEqual(config.palette_id(), "default-dark")

    def test_migration_never_reclobbers_a_later_explicit_palette_choice(self) -> None:
        path = self.tmp / "config.toml"
        path.write_text('[theme]\nmode = "light"\n', encoding="utf-8")

        Config(path)  # first load: migrates to default-light
        again = Config(path)
        again.set_palette_id("nord")
        again.save()

        reloaded = Config(path)
        self.assertEqual(reloaded.palette_id(), "nord")

    def test_a_fresh_config_never_writes_a_palette_table(self) -> None:
        path = self.tmp / "config.toml"
        Config(path)
        self.assertFalse(path.exists())


class EndToEndPaletteSelectionTests(ThemeModeResetMixin, unittest.TestCase):
    """Milestone 21b-e: the top bar's binary sun/moon toggle (_ThemeToggle,
    TopBar.theme_toggle_requested, CollectionView's relay of it) is retired
    in favor of the bottom bar's PalettePickerButton, wired directly at
    MainWindow (BottomBar lives outside CollectionView's own widget tree
    entirely, via QMainWindow.setStatusBar() -- there is nothing left for
    CollectionView to bubble). This replaces the old TopBarToggleTests /
    CollectionViewBubblesToggleTests / EndToEndThemeToggleTests trio with
    coverage of the real replacement path end to end, picking a genuinely
    non-default, non-binary palette (nord) -- proving "any of ten presets,"
    not just "the other one of two," actually persists and restores."""

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

    def test_selecting_a_palette_through_the_real_window_persists_and_a_fresh_launch_restores_it(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))

        config = Config(self.config_path)
        apply_theme(_app, config.palette_id())
        window = MainWindow(self.watches_dir, self.backups_dir, config)

        self.assertEqual(theme.current_palette_id(), "default-dark")
        window._bottom_bar.palette_selected.emit("nord")

        self.assertEqual(theme.current_palette_id(), "nord")
        reloaded_config = Config(self.config_path)
        self.assertEqual(reloaded_config.palette_id(), "nord")

        # Simulate a fresh process launch: reset the in-memory palette to
        # what a new process would start with, then run main.py's exact
        # startup sequence against the same config path.
        theme.set_palette("default-dark")
        fresh_config = Config(self.config_path)
        apply_theme(_app, fresh_config.palette_id())
        MainWindow(self.watches_dir, self.backups_dir, fresh_config)

        self.assertEqual(theme.current_palette_id(), "nord")


class BundledFontLoadingTests(unittest.TestCase):
    """Guards the exact failure mode SPEC.md's font swap called out: a font
    that fails to load (or loads but doesn't provide the weight requested)
    falls back silently and looks almost right. QFontInfo reports what Qt
    actually matched, not what was requested, so it catches both a missing
    family and a family present but missing the SemiBold instance."""

    @classmethod
    def setUpClass(cls) -> None:
        theme.load_bundled_fonts()

    def test_load_bundled_fonts_registers_all_three_families(self) -> None:
        families = set(theme.load_bundled_fonts())
        self.assertIn(theme.FONT_SANS, families)
        self.assertIn(theme.FONT_SANS_CONDENSED, families)
        self.assertIn(theme.FONT_MONO, families)

    def test_resolve_fonts_picks_the_bundled_families_not_the_fallback(self) -> None:
        resolved = theme.resolve_fonts()
        self.assertEqual(resolved["sans"], theme.FONT_SANS)
        self.assertEqual(resolved["sans_condensed"], theme.FONT_SANS_CONDENSED)
        self.assertEqual(resolved["mono"], theme.FONT_MONO)

    def test_sans_condensed_at_weight_600_resolves_to_the_semibold_instance(self) -> None:
        font = QFont(theme.FONT_SANS_CONDENSED)
        font.setWeight(QFont.Weight(600))
        info = QFontInfo(font)
        self.assertEqual(info.family(), theme.FONT_SANS_CONDENSED)
        self.assertEqual(info.styleName(), "SemiBold")

    def test_sans_condensed_at_weight_400_resolves_to_the_regular_instance(self) -> None:
        font = QFont(theme.FONT_SANS_CONDENSED)
        font.setWeight(QFont.Weight(400))
        info = QFontInfo(font)
        self.assertEqual(info.styleName(), "Regular")

    def test_sans_at_weight_600_resolves_to_the_semibold_instance(self) -> None:
        font = QFont(theme.FONT_SANS)
        font.setWeight(QFont.Weight(600))
        info = QFontInfo(font)
        self.assertEqual(info.family(), theme.FONT_SANS)
        self.assertEqual(info.styleName(), "SemiBold")


if __name__ == "__main__":
    unittest.main()
