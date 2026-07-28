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
from saat.ui.year_view import SlugColorBar, slug_chip_saturation_value, slug_color
from tests.contrast import contrast_ratio, relative_luminance

_app = QApplication.instance() or QApplication([])


class ContrastRatioHelperTests(unittest.TestCase):
    """The formula itself, checked against known reference values — a test
    that only proves the palette meets a bar is worthless if the bar-checker
    is wrong."""

    def test_black_on_white_is_21_to_1(self) -> None:
        self.assertAlmostEqual(contrast_ratio("#000000", "#FFFFFF"), 21.0, places=1)

    def test_identical_colors_are_1_to_1(self) -> None:
        self.assertAlmostEqual(contrast_ratio("#808080", "#808080"), 1.0, places=6)

    def test_ratio_is_symmetric_regardless_of_argument_order(self) -> None:
        self.assertAlmostEqual(contrast_ratio("#1C1B19", "#E8E4DC"), contrast_ratio("#E8E4DC", "#1C1B19"))


# SPEC.md §6: "4.5:1 for body text, 3:1 for large text and UI components...
# a starting point, not measured output." The app's type scale (11-28px,
# weights 400/600 only) never qualifies as "large text", so text/text-muted
# are held to 4.5:1. gilt/ruby only ever appear as interactive accents —
# buttons, active-filter indicators, focus rings — never as paragraphs, so
# 3:1 applies. This now applies PER PALETTE (SPEC.md §6, milestone 21b item
# 10), not just the original two.
TEXT_FIELDS = ["text", "text_muted"]
UI_FIELDS = ["gilt", "ruby"]
BACKGROUND_FIELDS = ["plate", "plate_high"]

# Documented, honest exceptions where no fully-compliant same-family
# substitution exists (SPEC.md §6 items 10/37) — see each palette's own
# TOML comment for the full reasoning and every alternative considered.
# Thresholds are the exact measured ratio (so a future regression still
# fails loudly); every other (palette, field, background) combination not
# listed here is held to the unrelaxed bar, and this must never grow into a
# blanket relaxation.
KNOWN_CONTRAST_SHORTFALLS = {
    # Subtext 1 is Catppuccin's next-nearest step after Subtext 0; nothing
    # in the family beyond it but Text itself, which would erase the
    # muted/primary distinction.
    ("catppuccin-latte", "text_muted", "plate_high"): 4.050294139498451,
    # `subtle`, Rosé Pine's own next-brighter foreground step after `muted`.
    ("rose-pine-dawn", "text_muted", "plate"): 4.0235765161349795,
    ("rose-pine-dawn", "text_muted", "plate_high"): 4.231263400289407,
    # nord3 is Nord's own designated "comments/disabled" role; the 16-color
    # system has no intermediate step between it and nord4 (primary text).
    ("nord", "text_muted", "plate"): 1.692958248266498,
    ("nord", "text_muted", "plate_high"): 1.3638806389111493,
    # nord11 is Nord's only red -- no substitute exists in the Aurora group.
    ("nord", "ruby", "plate_high"): 2.4595398617071926,
    # lotusGray2, the next step toward text after lotusGray3 (Kanagawa's own
    # comment/deprecated role); coincides with `rule`'s own value.
    ("kanagawa-lotus", "text_muted", "plate"): 4.262911999110539,
    ("kanagawa-lotus", "text_muted", "plate_high"): 3.2122309256423045,
}


def _minimum_ratio_for(palette_id: str, field: str, background: str, default: float) -> float:
    return KNOWN_CONTRAST_SHORTFALLS.get((palette_id, field, background), default)


class PaletteSchemaTests(unittest.TestCase):
    """Milestone 21b item 12: an incomplete palette must fail loudly, not
    fall back silently. This is the completeness half of that contract —
    every one of the ten TOML files parses and defines all seven roles.
    PAPER is deliberately excluded: it's a hardcoded module constant outside
    the ten-preset registry (SPEC.md §9), not user-selectable, so this
    schema contract doesn't apply to it."""

    def test_exactly_ten_palettes_are_registered(self) -> None:
        self.assertEqual(len(theme.palettes()), 10)

    def test_every_palette_defines_all_seven_roles_as_non_empty_hex(self) -> None:
        for entry in theme.palettes():
            with self.subTest(palette=entry.id):
                for field in ("plate", "plate_high", "rule", "text", "text_muted", "gilt", "ruby"):
                    value = getattr(entry.palette, field)
                    self.assertTrue(value.startswith("#"), f"{entry.id}.{field} = {value!r}")
                    self.assertEqual(len(value), 7, f"{entry.id}.{field} = {value!r}")

    def test_no_placeholder_values_remain(self) -> None:
        """Guards against exactly the state this test suite was built
        against mid-Commit-B: eight of the ten TOML files temporarily
        mirrored default-dark/default-light while the palette engine was
        built, before real researched values existed."""
        palettes_dir = Path(theme.__file__).resolve().parent.parent / "resources" / "palettes"
        for path in sorted(palettes_dir.glob("*.toml")):
            with self.subTest(file=path.name):
                self.assertNotIn("PLACEHOLDER", path.read_text(encoding="utf-8"))

    def test_declared_is_dark_agrees_with_measured_plate_luminance(self) -> None:
        """A mislabeled is_dark flag would silently select the wrong
        slug-chip saturation/value bucket (year_view.py) while the
        exhaustive hue test below still passes against the WRONG palette's
        own plate -- this catches the mislabeling directly."""
        for entry in theme.palettes():
            with self.subTest(palette=entry.id):
                measured_dark = relative_luminance(entry.palette.plate) < 0.5
                self.assertEqual(
                    entry.is_dark, measured_dark,
                    f"{entry.id}: is_dark={entry.is_dark} but plate {entry.palette.plate} "
                    f"measures luminance={relative_luminance(entry.palette.plate):.4f}",
                )


class PaletteContrastTests(unittest.TestCase):
    def tearDown(self) -> None:
        theme.set_palette("default-dark")

    def test_text_and_text_muted_meet_4_5_to_1_against_both_backgrounds(self) -> None:
        for entry in theme.palettes():
            theme.set_palette(entry.id)
            palette = theme.colors()
            for fg_name in TEXT_FIELDS:
                for bg_name in BACKGROUND_FIELDS:
                    fg, bg = getattr(palette, fg_name), getattr(palette, bg_name)
                    with self.subTest(palette=entry.id, foreground=fg_name, background=bg_name):
                        ratio = contrast_ratio(fg, bg)
                        minimum = _minimum_ratio_for(entry.id, fg_name, bg_name, 4.5)
                        self.assertGreaterEqual(
                            ratio, minimum,
                            f"{entry.id}: {fg_name} ({fg}) on {bg_name} ({bg}): {ratio:.2f}:1",
                        )

    def test_gilt_and_ruby_meet_3_to_1_against_both_backgrounds(self) -> None:
        for entry in theme.palettes():
            theme.set_palette(entry.id)
            palette = theme.colors()
            for fg_name in UI_FIELDS:
                for bg_name in BACKGROUND_FIELDS:
                    fg, bg = getattr(palette, fg_name), getattr(palette, bg_name)
                    with self.subTest(palette=entry.id, foreground=fg_name, background=bg_name):
                        ratio = contrast_ratio(fg, bg)
                        minimum = _minimum_ratio_for(entry.id, fg_name, bg_name, 3.0)
                        self.assertGreaterEqual(
                            ratio, minimum,
                            f"{entry.id}: {fg_name} ({fg}) on {bg_name} ({bg}): {ratio:.2f}:1",
                        )


class CardHoverAndSelectionContrastTests(unittest.TestCase):
    """Milestone 16e (SPEC.md §6): WatchCard.paintEvent washes the card's
    text-block strip on hover, eased in via _hover_progress toward
    plate_high@ at full alpha -- card-overline/title/meta text renders
    directly on top of it in the grid, so that endpoint is pinned here
    specifically (rather than relying only on PaletteContrastTests' generic
    matrix), in case a future change points hover's wash at a background
    that matrix no longer covers. Checked per palette (milestone 21b)."""

    def tearDown(self) -> None:
        theme.set_palette("default-dark")

    def test_text_on_hovers_fully_settled_wash_meets_4_5_to_1(self) -> None:
        for entry in theme.palettes():
            theme.set_palette(entry.id)
            palette = theme.colors()
            for fg_name in TEXT_FIELDS:
                fg = getattr(palette, fg_name)
                with self.subTest(palette=entry.id, foreground=fg_name):
                    ratio = contrast_ratio(fg, palette.plate_high)
                    minimum = _minimum_ratio_for(entry.id, fg_name, "plate_high", 4.5)
                    self.assertGreaterEqual(
                        ratio, minimum,
                        f"{entry.id}: {fg_name} ({fg}) on hover wash ({palette.plate_high}): {ratio:.2f}:1",
                    )


class SlugChipContrastTests(unittest.TestCase):
    """year_view.py's per-watch colour chips share one hue per slug but a
    fixed (saturation, value) pair keyed on the active palette's is_dark
    flag — so unlike the named palette tokens, the thing that must clear
    3:1 is every hue at that flag's fixed pair against every palette
    carrying that flag, not just the specific hues a handful of test slugs
    happen to hash to. Exhaustive over all 360 integer hues, across all ten
    palettes' own backgrounds accordingly."""

    def tearDown(self) -> None:
        theme.set_palette("default-dark")

    def test_every_hue_meets_3_to_1_against_every_palettes_own_backgrounds(self) -> None:
        for entry in theme.palettes():
            theme.set_palette(entry.id)
            saturation, value = slug_chip_saturation_value()
            backgrounds = [getattr(theme.colors(), name) for name in BACKGROUND_FIELDS]
            for hue in range(360):
                chip = QColor.fromHsv(hue, saturation, value).name()
                worst = min(contrast_ratio(chip, bg) for bg in backgrounds)
                if worst < 3.0:
                    self.fail(f"{entry.id}: hue={hue} sat={saturation} val={value} ({chip}): {worst:.2f}:1")

    def test_both_saturation_value_buckets_are_exercised_by_a_real_light_and_dark_palette(self) -> None:
        """Confirms the loop above actually reaches both branches of
        slug_chip_saturation_value(), not just one, by checking two
        concrete, always-present palettes rather than trusting flag
        coverage implicitly."""
        theme.set_palette("default-light")
        self.assertEqual(slug_chip_saturation_value(), (150, 110))
        theme.set_palette("default-dark")
        self.assertEqual(slug_chip_saturation_value(), (100, 255))


class DetailViewIdentityAccentContrastTests(unittest.TestCase):
    """SPEC.md §6: the detail page's identity-colour hairline (SlugColorBar,
    beneath the title) reuses slug_color() -- already checked exhaustively
    over all 360 hues by SlugChipContrastTests above, but that test only
    ever exercises the colour math in isolation, never a real rendered
    widget. This renders an actual DetailView, samples the bar's own pixel,
    and confirms it's genuinely slug_color() (not some other value) and
    genuinely clears 3:1 against the background it actually sits on.
    Scoped to the two defaults (a wiring check, not a re-run of the
    exhaustive math already covered above) rather than all ten."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-identity-accent-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)
        theme.set_palette("default-dark")

    def test_identity_bar_renders_the_watchs_slug_colour_at_3_to_1(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        [record] = load_collection(self.watches_dir)

        for palette_id in ("default-dark", "default-light"):
            theme.set_palette(palette_id)
            view = DetailView(record)
            view.resize(1200, 900)
            view.show()
            QApplication.processEvents()

            bar = view.findChild(SlugColorBar)
            self.assertIsNotNone(bar)
            sampled = bar.grab().toImage().pixelColor(bar.width() // 2, bar.height() // 2)
            expected = slug_color(record.slug)

            with self.subTest(palette=palette_id):
                self.assertEqual(sampled.name(), expected.name())
                ratio = contrast_ratio(sampled.name(), theme.colors().plate)
                self.assertGreaterEqual(ratio, 3.0, f"{sampled.name()} on {theme.colors().plate}: {ratio:.2f}:1")
            view.close()


if __name__ == "__main__":
    unittest.main()
