import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from saat.ui import theme
from saat.ui.theme import MODE_DARK, MODE_LIGHT
from saat.ui.year_view import slug_chip_saturation_value

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


if __name__ == "__main__":
    unittest.main()
