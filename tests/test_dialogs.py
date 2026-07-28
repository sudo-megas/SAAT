import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from saat.ui import theme
from saat.ui.dialogs import confirm_discard_changes
from saat.ui.theme import apply_theme

_app = QApplication.instance() or QApplication([])


def _close(a: QColor, b: QColor, tolerance: int = 30) -> bool:
    return abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue()) < tolerance


class ConfirmDiscardChangesDestructiveStylingTests(unittest.TestCase):
    """Regression: discard_button.setProperty("variant", "destructive") lands
    on an already-live QMessageBox button (unlike DeleteConfirmDialog's,
    which is set before the dialog's first show/polish), so it needs an
    explicit repolish or Qt never re-evaluates the QSS selector and the
    button silently renders as plain plate-high instead of ruby -- SPEC.md
    §6's second of exactly two ruby usages in the app."""

    def setUp(self) -> None:
        self.addCleanup(apply_theme, _app, "default-dark")
        apply_theme(_app, "default-dark")

    def test_discard_button_renders_ruby_background(self) -> None:
        sampled = {}

        def _grab_and_close() -> None:
            box = QApplication.activeModalWidget()
            discard = next(b for b in box.buttons() if b.property("variant") == "destructive")
            image = discard.grab().toImage()
            sampled["color"] = image.pixelColor(image.width() // 2, image.height() // 2)
            box.close()

        QTimer.singleShot(0, _grab_and_close)
        confirm_discard_changes(None)

        self.assertIn("color", sampled)
        self.assertTrue(_close(sampled["color"], QColor(theme.colors().ruby)))


if __name__ == "__main__":
    unittest.main()
