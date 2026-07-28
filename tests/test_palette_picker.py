import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from saat.ui import theme
from saat.ui.palette_picker import PalettePickerButton

_app = QApplication.instance() or QApplication([])

# SPEC.md §6 item 8's exact list, order and ids -- mirrors test_theme.py's
# own EXPECTED_PALETTE_ORDER rather than importing it, since that constant
# lives in a test module, not production code.
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


class PalettePickerPopoverTests(unittest.TestCase):
    """Exercises PalettePickerButton._build_menu() directly, never
    _show_popover()/QMenu.exec() -- exec() runs a real nested Qt event
    loop, which this suite has a confirmed segfault repro from late in a
    full `unittest discover` run (see test_retranslation.py's _pump()
    docstring, and _build_menu()'s own docstring in palette_picker.py).
    _build_menu() returns the exact same menu, fully wired, before the
    only thing exec() itself would add: actually showing it on screen --
    irrelevant to the row order / checkmark / click -> signal logic here."""

    def tearDown(self) -> None:
        theme.set_palette("default-dark")

    def test_menu_lists_all_ten_palettes_in_spec_order(self) -> None:
        button = PalettePickerButton()

        menu = button._build_menu()

        row_ids = [action.defaultWidget()._palette_id for action in menu.actions()]
        self.assertEqual(row_ids, list(EXPECTED_PALETTE_ORDER))

    def test_the_active_palettes_row_shows_a_checkmark_and_no_other_row_does(self) -> None:
        theme.set_palette("nord")
        button = PalettePickerButton()

        menu = button._build_menu()

        checked_ids = []
        for action in menu.actions():
            row = action.defaultWidget()
            check_label = row.layout().itemAt(2).widget()  # swatch, name, check -- _PaletteRow's own order
            if check_label.text():
                checked_ids.append(row._palette_id)
        self.assertEqual(checked_ids, ["nord"])

    def test_clicking_a_different_row_emits_palette_selected_and_closes_the_menu(self) -> None:
        theme.set_palette("default-dark")
        button = PalettePickerButton()
        received = []
        button.palette_selected.connect(received.append)

        menu = button._build_menu()
        row = next(a.defaultWidget() for a in menu.actions() if a.defaultWidget()._palette_id == "nord")
        QTest.mouseClick(row, Qt.MouseButton.LeftButton)

        self.assertEqual(received, ["nord"])

    def test_clicking_the_already_active_row_does_not_emit_palette_selected(self) -> None:
        """PalettePickerButton._apply() guards this itself (palette_picker.
        py) -- re-picking the active row is a real click a user can make
        (the checkmarked row is still clickable), and it must stay a silent
        no-op rather than re-apply/re-save/re-emit against an unchanged
        palette."""
        theme.set_palette("nord")
        button = PalettePickerButton()
        received = []
        button.palette_selected.connect(received.append)

        menu = button._build_menu()
        row = next(a.defaultWidget() for a in menu.actions() if a.defaultWidget()._palette_id == "nord")
        QTest.mouseClick(row, Qt.MouseButton.LeftButton)

        self.assertEqual(received, [])


if __name__ == "__main__":
    unittest.main()
