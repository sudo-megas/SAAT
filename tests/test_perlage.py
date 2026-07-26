import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from saat.ui import theme
from saat.ui.perlage import TILE_SIZE, render_perlage_tile
from saat.ui.theme import MODE_DARK, MODE_LIGHT

_app = QApplication.instance() or QApplication([])

CONTRAST_CEILING = 0.03  # SPEC.md §6: perceptible as texture, never as pattern


def _max_channel_delta(image, base: QColor) -> float:
    """The literal reading of the "3% contrast ceiling": the largest
    per-channel deviation from bare base anywhere in the rendered tile,
    normalised to 0-1 -- not a WCAG ratio, which has no natural "3%" reading
    at all. See tests/test_theme_contrast.py for the (unrelated) WCAG
    helper used elsewhere in this app."""
    worst = 0.0
    for y in range(image.height()):
        for x in range(image.width()):
            pixel = image.pixelColor(x, y)
            delta = max(
                abs(pixel.red() - base.red()),
                abs(pixel.green() - base.green()),
                abs(pixel.blue() - base.blue()),
            )
            worst = max(worst, delta / 255)
    return worst


class ContrastCeilingTests(unittest.TestCase):
    """The two real surface/grain pairings this milestone actually uses --
    the empty state's plate@/rule@ and the sidebar's plate-high@/rule@ --
    in both themes. Not exhaustive over arbitrary colour pairs: unlike
    slug_color()'s 360 possible hues, perlage's grain colour is always
    rule@, so the only real degrees of freedom are the four (surface, mode)
    combinations this app actually renders."""

    def tearDown(self) -> None:
        theme.set_mode(MODE_DARK)

    def test_every_real_surface_and_mode_combination_stays_under_the_ceiling(self) -> None:
        for mode in (MODE_DARK, MODE_LIGHT):
            theme.set_mode(mode)
            colors = theme.colors()
            for surface_name, base_hex in (("plate", colors.plate), ("plate_high", colors.plate_high)):
                with self.subTest(mode=mode, surface=surface_name):
                    tile = render_perlage_tile(base_hex, colors.rule)
                    worst = _max_channel_delta(tile.toImage(), QColor(base_hex))
                    self.assertLessEqual(
                        worst, CONTRAST_CEILING,
                        f"{surface_name}@ ({base_hex}) + rule@ grain in {mode}: {worst:.3f} exceeds {CONTRAST_CEILING}",
                    )


class TileCachingTests(unittest.TestCase):
    def test_identical_parameters_return_the_identical_pixmap(self) -> None:
        first = render_perlage_tile("#1C1B19", "#38352F")
        second = render_perlage_tile("#1C1B19", "#38352F")
        self.assertIs(first, second)

    def test_different_base_colour_returns_a_different_pixmap(self) -> None:
        first = render_perlage_tile("#1C1B19", "#38352F")
        different = render_perlage_tile("#F1EEE6", "#38352F")
        self.assertIsNot(first, different)

    def test_a_theme_toggle_naturally_invalidates_the_cache(self) -> None:
        """No manual cache-clear anywhere -- new hex strings are simply a
        new key, the same self-invalidating pattern icons.py's own pixmap
        cache already relies on."""
        dark_tile = render_perlage_tile(theme.colors().plate, theme.colors().rule)
        theme.set_mode(MODE_LIGHT)
        light_tile = render_perlage_tile(theme.colors().plate, theme.colors().rule)
        theme.set_mode(MODE_DARK)
        self.assertIsNot(dark_tile, light_tile)


class TileRenderingTests(unittest.TestCase):
    def test_tile_is_the_requested_size(self) -> None:
        tile = render_perlage_tile("#1C1B19", "#38352F")
        self.assertEqual(tile.size().toTuple(), (TILE_SIZE, TILE_SIZE))

    def test_tile_is_not_just_flat_base_colour(self) -> None:
        base = QColor("#1C1B19")
        tile = render_perlage_tile(base.name(), "#38352F")
        image = tile.toImage()
        distinct_colours = {image.pixelColor(x, y).rgb() for x in range(0, TILE_SIZE, 2) for y in range(0, TILE_SIZE, 2)}
        self.assertGreater(len(distinct_colours), 1, "expected visible grain, not a flat fill")


if __name__ == "__main__":
    unittest.main()
