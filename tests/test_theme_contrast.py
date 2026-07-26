import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from saat.models import Watch
from saat.storage import create_watch, load_collection
from saat.ui import theme
from saat.ui.detail_view import DetailView
from saat.ui.theme import MODE_DARK, MODE_LIGHT
from saat.ui.year_view import SlugColorBar, slug_chip_saturation_value, slug_color

_app = QApplication.instance() or QApplication([])


def _channel(value: int) -> float:
    c = value / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def _contrast_ratio(hex_a: str, hex_b: str) -> float:
    """WCAG 2.x contrast ratio: (L1 + 0.05) / (L2 + 0.05), lighter over darker."""
    la, lb = _relative_luminance(hex_a), _relative_luminance(hex_b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


class ContrastRatioHelperTests(unittest.TestCase):
    """The formula itself, checked against known reference values — a test
    that only proves the palette meets a bar is worthless if the bar-checker
    is wrong."""

    def test_black_on_white_is_21_to_1(self) -> None:
        self.assertAlmostEqual(_contrast_ratio("#000000", "#FFFFFF"), 21.0, places=1)

    def test_identical_colors_are_1_to_1(self) -> None:
        self.assertAlmostEqual(_contrast_ratio("#808080", "#808080"), 1.0, places=6)

    def test_ratio_is_symmetric_regardless_of_argument_order(self) -> None:
        self.assertAlmostEqual(_contrast_ratio("#1C1B19", "#E8E4DC"), _contrast_ratio("#E8E4DC", "#1C1B19"))


# SPEC.md §6: "4.5:1 for body text, 3:1 for large text and UI components... a
# starting point, not measured output." The app's type scale (11-28px,
# weights 400/600 only) never qualifies as "large text", so text/text-muted
# are held to 4.5:1. gilt/ruby only ever appear as interactive accents —
# buttons, active-filter indicators, focus rings — never as paragraphs, so
# 3:1 applies. Every view is built from exactly these 7 tokens (confirmed:
# no hardcoded hex colors exist anywhere in saat/ui/*.py outside theme.py),
# so this pairing matrix is the full-app contrast pass, not a sample of it.
TEXT_FIELDS = ["text", "text_muted"]
UI_FIELDS = ["gilt", "ruby"]
BACKGROUND_FIELDS = ["plate", "plate_high"]


class PaletteContrastTests(unittest.TestCase):
    def tearDown(self) -> None:
        theme.set_mode(MODE_DARK)

    def test_text_and_text_muted_meet_4_5_to_1_against_both_backgrounds(self) -> None:
        for mode in (MODE_DARK, MODE_LIGHT):
            theme.set_mode(mode)
            palette = theme.colors()
            for fg_name in TEXT_FIELDS:
                for bg_name in BACKGROUND_FIELDS:
                    fg, bg = getattr(palette, fg_name), getattr(palette, bg_name)
                    with self.subTest(mode=mode, foreground=fg_name, background=bg_name):
                        ratio = _contrast_ratio(fg, bg)
                        self.assertGreaterEqual(ratio, 4.5, f"{fg_name} ({fg}) on {bg_name} ({bg}) in {mode}: {ratio:.2f}:1")

    def test_gilt_and_ruby_meet_3_to_1_against_both_backgrounds(self) -> None:
        for mode in (MODE_DARK, MODE_LIGHT):
            theme.set_mode(mode)
            palette = theme.colors()
            for fg_name in UI_FIELDS:
                for bg_name in BACKGROUND_FIELDS:
                    fg, bg = getattr(palette, fg_name), getattr(palette, bg_name)
                    with self.subTest(mode=mode, foreground=fg_name, background=bg_name):
                        ratio = _contrast_ratio(fg, bg)
                        self.assertGreaterEqual(ratio, 3.0, f"{fg_name} ({fg}) on {bg_name} ({bg}) in {mode}: {ratio:.2f}:1")


class CardHoverAndSelectionContrastTests(unittest.TestCase):
    """Milestone 16e (SPEC.md §6): WatchCard.paintEvent washes the card's
    text-block strip on hover, eased in via _hover_progress toward plate_high@
    at full alpha -- card-overline/title/meta text renders directly on top of
    it in the grid, so that endpoint is pinned here specifically (rather than
    relying only on PaletteContrastTests' generic matrix), in case a future
    change points hover's wash at a background that matrix no longer covers.

    Compare-selection was originally meant to get its own background tint
    too (a gilt@ wash, distinct from hover's), but no alpha makes that both
    visible and safe: reading as a wash at all needs roughly alpha>=45 over
    plate@, while text_muted's already-thin margin there (both palettes are
    tuned to just clear 4.5:1 against the plain backgrounds -- see this
    class's own comments) caps any *contrast-safe* gilt alpha at 8 in light
    mode. Visible and safe don't overlap. Compare-selection's distinct
    treatment is instead the 2px static gilt border (vs hover's 1px animated
    one) plus the ever-visible checked checkbox -- neither sits behind text,
    so neither runs into this."""

    def tearDown(self) -> None:
        theme.set_mode(MODE_DARK)

    def test_text_on_hovers_fully_settled_wash_meets_4_5_to_1_in_both_modes(self) -> None:
        for mode in (MODE_DARK, MODE_LIGHT):
            theme.set_mode(mode)
            palette = theme.colors()
            for fg_name in TEXT_FIELDS:
                fg = getattr(palette, fg_name)
                with self.subTest(mode=mode, foreground=fg_name):
                    ratio = _contrast_ratio(fg, palette.plate_high)
                    self.assertGreaterEqual(ratio, 4.5, f"{fg_name} ({fg}) on hover wash ({palette.plate_high}) in {mode}: {ratio:.2f}:1")


class SlugChipContrastTests(unittest.TestCase):
    """year_view.py's per-watch colour chips share one hue per slug but a
    fixed (saturation, value) across all hues in a given mode — so unlike the
    named palette tokens, the thing that must clear 3:1 is every hue at that
    mode's fixed pair, not just the specific hues a handful of test slugs
    happen to hash to. Exhaustive over all 360 integer hues accordingly."""

    def tearDown(self) -> None:
        theme.set_mode(MODE_DARK)

    def test_every_hue_meets_3_to_1_against_both_backgrounds_in_both_modes(self) -> None:
        for mode in (MODE_DARK, MODE_LIGHT):
            theme.set_mode(mode)
            saturation, value = slug_chip_saturation_value()
            backgrounds = [getattr(theme.colors(), name) for name in BACKGROUND_FIELDS]
            for hue in range(360):
                chip = QColor.fromHsv(hue, saturation, value).name()
                worst = min(_contrast_ratio(chip, bg) for bg in backgrounds)
                if worst < 3.0:
                    self.fail(f"hue={hue} sat={saturation} val={value} ({chip}) in {mode}: {worst:.2f}:1")


class DetailViewIdentityAccentContrastTests(unittest.TestCase):
    """SPEC.md §6: the detail page's identity-colour hairline (SlugColorBar,
    beneath the title) reuses slug_color() -- already checked exhaustively
    over all 360 hues by SlugChipContrastTests above, but that test only
    ever exercises the colour math in isolation, never a real rendered
    widget. This renders an actual DetailView, samples the bar's own pixel,
    and confirms it's genuinely slug_color() (not some other value) and
    genuinely clears 3:1 against the background it actually sits on."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-identity-accent-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)
        theme.set_mode(MODE_DARK)

    def test_identity_bar_renders_the_watchs_slug_colour_at_3_to_1_in_both_modes(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        [record] = load_collection(self.watches_dir)

        for mode in (MODE_DARK, MODE_LIGHT):
            theme.set_mode(mode)
            view = DetailView(record)
            view.resize(1200, 900)
            view.show()
            QApplication.processEvents()

            bar = view.findChild(SlugColorBar)
            self.assertIsNotNone(bar)
            sampled = bar.grab().toImage().pixelColor(bar.width() // 2, bar.height() // 2)
            expected = slug_color(record.slug)

            with self.subTest(mode=mode):
                self.assertEqual(sampled.name(), expected.name())
                ratio = _contrast_ratio(sampled.name(), theme.colors().plate)
                self.assertGreaterEqual(ratio, 3.0, f"{sampled.name()} on {theme.colors().plate} in {mode}: {ratio:.2f}:1")
            view.close()


if __name__ == "__main__":
    unittest.main()
