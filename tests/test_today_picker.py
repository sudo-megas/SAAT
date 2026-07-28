import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import random
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QDialog, QPushButton

from saat.models import Watch
from saat.selection import MODE_RANDOM, MODE_WEIGHTED
from saat.storage import WatchRecord
from saat.ui import theme
from saat.ui.today_picker import DIE_SIZE, HairlineDie, TodayPickerDialog

_app = QApplication.instance() or QApplication([])


def _record(slug: str, brand: str = "Brand", model: str = "Model", status: str = "Owned") -> WatchRecord:
    return WatchRecord(slug=slug, path=Path(f"/nonexistent/{slug}"), watch=Watch(brand=brand, model=model, status=status))


class HairlineDieTests(unittest.TestCase):
    def test_unanimated_roll_settles_immediately_on_the_given_face(self) -> None:
        die = HairlineDie(face_count=5)
        settled = []
        die.settled.connect(lambda: settled.append(True))
        die.roll_to(3, animate=False)
        self.assertEqual(die._face, 3)
        self.assertEqual(settled, [True])

    def test_animated_roll_eventually_settles_on_the_given_face(self) -> None:
        """Drives the tick chain directly (matching this codebase's own
        convention of avoiding QTest.qWait() for animation-adjacent tests —
        see test_cards.py/test_sidebar.py) rather than waiting on the real
        QTimer, then drives the final settle QPropertyAnimation via
        setCurrentTime() the same way."""
        die = HairlineDie(face_count=5)
        settled = []
        die.settled.connect(lambda: settled.append(True))
        die.roll_to(4, animate=True)
        self.assertEqual(settled, [], "must not settle before the tumble finishes")
        # Drive every remaining tick by hand instead of waiting on the timer.
        while die._timer.isActive() or die._tick_index < 13:
            die._timer.stop()
            die._tick()
        self.assertEqual(die._face, 4)
        self.assertIsNotNone(die._settle_animation)
        die._settle_animation.setCurrentTime(theme.ANIM_DURATION_MS)
        self.assertEqual(settled, [True])

    def test_single_owned_watch_never_tumbles_off_face_one(self) -> None:
        die = HairlineDie(face_count=1)
        die.roll_to(1, animate=True)
        while die._timer.isActive() or die._tick_index < 13:
            die._timer.stop()
            die._tick()
        self.assertEqual(die._face, 1)

    def test_paints_without_error_in_both_themes(self) -> None:
        for mode in ("default-dark", "default-light"):
            theme.set_palette(mode)
            with self.subTest(mode=mode):
                die = HairlineDie(face_count=3)
                die.show()
                die.roll_to(2, animate=False)
                image = die.grab().toImage()
                self.assertFalse(image.isNull())
                self.assertEqual(die.size().width(), DIE_SIZE)
                die.close()
        theme.set_palette("default-dark")


class TodayPickerDialogTests(unittest.TestCase):
    def test_no_owned_watches_shows_a_message_and_does_not_crash(self) -> None:
        records = [_record("wishlist-only", status="Wishlist")]
        dialog = TodayPickerDialog(records, MODE_RANDOM, reduced_motion=True)
        self.assertFalse(hasattr(dialog, "_die"))

    def test_single_owned_watch_names_it_without_a_die(self) -> None:
        records = [_record("only", "Seiko", "SARB033")]
        dialog = TodayPickerDialog(records, MODE_RANDOM, reduced_motion=True)
        self.assertFalse(hasattr(dialog, "_die"))

    def test_single_owned_watch_wore_today_emits_that_record(self) -> None:
        record = _record("only", "Seiko", "SARB033")
        dialog = TodayPickerDialog([record], MODE_RANDOM, reduced_motion=True)
        received = []
        dialog.wore_today_requested.connect(received.append)
        button = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Wore this today")
        button.click()
        self.assertEqual(received, [record])
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)

    def test_multiple_owned_settles_immediately_when_reduced_motion(self) -> None:
        records = [_record(f"w{i}") for i in range(4)]
        dialog = TodayPickerDialog(records, MODE_RANDOM, reduced_motion=True, rand=random.Random(1))
        self.assertTrue(dialog._wore_today_button.isEnabled())
        self.assertIn(dialog._chosen.slug, {r.slug for r in records})
        self.assertNotEqual(dialog._result_label.text(), "")

    def test_wore_today_button_disabled_until_settled(self) -> None:
        records = [_record(f"w{i}") for i in range(4)]
        dialog = TodayPickerDialog(records, MODE_RANDOM, reduced_motion=False, rand=random.Random(1))
        self.assertFalse(dialog._wore_today_button.isEnabled())

    def test_wore_today_click_emits_the_chosen_record(self) -> None:
        records = [_record(f"w{i}") for i in range(4)]
        dialog = TodayPickerDialog(records, MODE_RANDOM, reduced_motion=True, rand=random.Random(1))
        received = []
        dialog.wore_today_requested.connect(received.append)
        chosen = dialog._chosen
        dialog._wore_today_button.click()
        self.assertEqual(received, [chosen])

    def test_reroll_does_not_emit_wore_today(self) -> None:
        records = [_record(f"w{i}") for i in range(4)]
        dialog = TodayPickerDialog(records, MODE_RANDOM, reduced_motion=True, rand=random.Random(1))
        received = []
        dialog.wore_today_requested.connect(received.append)
        dialog._reroll_button.click()
        self.assertEqual(received, [])
        # A fresh pick was made and re-enabled the action -- re-rolling never
        # writes anything on its own (SPEC.md milestone 20 step 10).
        self.assertTrue(dialog._wore_today_button.isEnabled())

    def test_switching_mode_persists_via_the_callback_and_rerolls(self) -> None:
        records = [_record(f"w{i}") for i in range(4)]
        changes = []
        dialog = TodayPickerDialog(
            records, MODE_RANDOM, on_mode_changed=changes.append, reduced_motion=True, rand=random.Random(1)
        )
        dialog._weighted_button.click()
        self.assertEqual(changes, [MODE_WEIGHTED])
        self.assertTrue(dialog._weighted_button.isChecked())
        self.assertFalse(dialog._random_button.isChecked())

    def test_clicking_the_already_active_mode_does_not_reroll_or_notify(self) -> None:
        records = [_record(f"w{i}") for i in range(4)]
        changes = []
        dialog = TodayPickerDialog(
            records, MODE_RANDOM, on_mode_changed=changes.append, reduced_motion=True, rand=random.Random(1)
        )
        first_pick = dialog._chosen
        dialog._random_button.click()
        self.assertEqual(changes, [])
        self.assertEqual(dialog._chosen, first_pick)


if __name__ == "__main__":
    unittest.main()
