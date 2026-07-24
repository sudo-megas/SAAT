import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from pathlib import Path

from PySide6.QtGui import QImage
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QPushButton

from saat.paths import resource_dir
from saat.ui import icons, theme
from saat.ui.theme import MODE_DARK, MODE_LIGHT

_app = QApplication.instance() or QApplication([])

ICONS_DIR = resource_dir() / "resources" / "icons"


def _has_pixel_matching(pixmap, hex_color: str) -> bool:
    image: QImage = pixmap.toImage()
    target = hex_color.lower()
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixelColor(x, y).name().lower() == target:
                return True
    return False


class ThemeModeResetMixin:
    def tearDown(self) -> None:
        theme.set_mode(MODE_DARK)
        super().tearDown()


class IconAssetTests(unittest.TestCase):
    """The audit's own deliverable: every shipped SVG must actually parse and
    render, not merely exist as a file — a malformed one fails silently
    otherwise (QSvgRenderer just paints nothing)."""

    def test_every_shipped_svg_is_non_empty(self) -> None:
        svg_files = list(ICONS_DIR.glob("*.svg"))
        self.assertGreater(len(svg_files), 0, "no icons found in saat/resources/icons/")
        for path in svg_files:
            with self.subTest(icon=path.name):
                renderer = QSvgRenderer(str(path))
                self.assertTrue(renderer.isValid(), f"{path.name} did not parse as valid SVG")

    def test_every_shipped_svg_renders_to_a_non_null_pixmap(self) -> None:
        for path in ICONS_DIR.glob("*.svg"):
            name = path.stem
            with self.subTest(icon=name):
                result = icons.pixmap(name, "#E8E4DC", size=18)
                self.assertFalse(result.isNull())


class PixmapRecolorTests(unittest.TestCase):
    def test_recolored_pixmap_contains_the_requested_color(self) -> None:
        result = icons.pixmap("star", "#C9A227", size=32)
        self.assertTrue(_has_pixel_matching(result, "#c9a227"))

    def test_different_color_requests_produce_different_pixel_content(self) -> None:
        gilt = icons.pixmap("star", "#C9A227", size=32)
        ruby = icons.pixmap("star", "#CF3931", size=32)
        self.assertTrue(_has_pixel_matching(gilt, "#c9a227"))
        self.assertTrue(_has_pixel_matching(ruby, "#cf3931"))
        self.assertFalse(_has_pixel_matching(gilt, "#cf3931"))

    def test_same_arguments_are_served_from_cache(self) -> None:
        first = icons.pixmap("search", "#E8E4DC", size=18)
        second = icons.pixmap("search", "#E8E4DC", size=18)
        self.assertIs(first, second)

    def test_icon_wraps_a_non_null_qicon(self) -> None:
        result = icons.icon("search", "#E8E4DC")
        self.assertFalse(result.isNull())


class SetIconRefreshTests(ThemeModeResetMixin, unittest.TestCase):
    """SPEC.md §6: icons follow the theme toggle without shipping a second
    colour variant per file — apply_theme()'s existing widget sweep is what
    makes that happen, via the _refresh_icon hook set_icon() attaches."""

    def test_set_icon_gives_the_widget_a_non_null_icon(self) -> None:
        button = QPushButton()
        icons.set_icon(button, "search")
        self.assertFalse(button.icon().isNull())

    def test_theme_toggle_repaints_the_icon_in_the_new_palettes_color(self) -> None:
        theme.set_mode(MODE_DARK)
        button = QPushButton()
        icons.set_icon(button, "search", color_role="text")

        theme.apply_theme(_app, MODE_LIGHT)

        repainted = button.icon().pixmap(icons.ICON_SIZE, icons.ICON_SIZE)
        self.assertTrue(_has_pixel_matching(repainted, theme.colors().text.lower()))

    def test_widgets_without_a_themed_icon_are_unaffected_by_the_sweep(self) -> None:
        """The sweep's getattr(widget, "_refresh_icon", None) must be a
        true no-op for the hundreds of plain widgets that never called
        set_icon — nothing to assert beyond "this doesn't raise"."""
        QPushButton("Plain button, no icon")
        theme.apply_theme(_app, MODE_DARK)


class SetCheckableIconTests(ThemeModeResetMixin, unittest.TestCase):
    def test_unchecked_uses_the_unchecked_color_role(self) -> None:
        theme.set_mode(MODE_DARK)
        button = QPushButton()
        button.setCheckable(True)
        icons.set_checkable_icon(button, "grid")

        rendered = button.icon().pixmap(icons.ICON_SIZE, icons.ICON_SIZE)
        self.assertTrue(_has_pixel_matching(rendered, theme.colors().text_muted.lower()))

    def test_checking_it_switches_to_the_checked_color_role(self) -> None:
        theme.set_mode(MODE_DARK)
        button = QPushButton()
        button.setCheckable(True)
        icons.set_checkable_icon(button, "grid")

        button.setChecked(True)

        rendered = button.icon().pixmap(icons.ICON_SIZE, icons.ICON_SIZE)
        self.assertTrue(_has_pixel_matching(rendered, theme.colors().gilt.lower()))

    def test_unchecking_it_again_reverts_the_color(self) -> None:
        theme.set_mode(MODE_DARK)
        button = QPushButton()
        button.setCheckable(True)
        icons.set_checkable_icon(button, "grid")

        button.setChecked(True)
        button.setChecked(False)

        rendered = button.icon().pixmap(icons.ICON_SIZE, icons.ICON_SIZE)
        self.assertTrue(_has_pixel_matching(rendered, theme.colors().text_muted.lower()))


if __name__ == "__main__":
    unittest.main()
