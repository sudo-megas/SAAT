import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

from saat.config import Config
from saat.models import Watch
from saat.storage import create_watch, load_collection
from saat.ui.compare_view import CompareView
from saat.ui.main_window import MainWindow
from saat.ui.watch_form import WatchForm

_app = QApplication.instance() or QApplication([])


def _shortcuts(window: MainWindow, sequence: str) -> list[QShortcut]:
    target = QKeySequence(sequence)
    return [sc for sc in window.findChildren(QShortcut) if sc.key() == target]


class UITestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-shortcuts-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _config(self) -> Config:
        return Config(self.tmp / "config.toml")

    def _window(self, count: int = 1) -> MainWindow:
        for model in "ABCDEF"[:count]:
            create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model=model))
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        window.show()
        return window


class GlobalShortcutRegistrationTests(UITestCase):
    def test_each_expected_shortcut_is_registered_exactly_once(self) -> None:
        window = self._window()
        for sequence in ("Ctrl+N", "Ctrl+F", "Ctrl+E", "Ctrl+W", "Ctrl+P", "Ctrl+Q", "Esc"):
            with self.subTest(sequence=sequence):
                self.assertEqual(len(_shortcuts(window, sequence)), 1)

    def test_ctrl_n_shortcut_is_wired_to_open_the_add_form(self) -> None:
        window = self._window()
        [shortcut] = _shortcuts(window, "Ctrl+N")

        with patch.object(WatchForm, "exec", return_value=QDialog.DialogCode.Rejected) as mock_exec:
            shortcut.activated.emit()

        mock_exec.assert_called_once()


class EditCurrentShortcutTests(UITestCase):
    def test_ctrl_e_while_on_detail_view_edits_the_shown_record(self) -> None:
        window = self._window()
        [record] = load_collection(self.watches_dir)
        window._show_detail(record)

        with patch.object(window, "_show_edit_form") as mock_edit:
            window._edit_current()

        mock_edit.assert_called_once_with(record)

    def test_ctrl_e_while_on_collection_view_does_nothing(self) -> None:
        window = self._window()

        with patch.object(window, "_show_edit_form") as mock_edit:
            window._edit_current()

        mock_edit.assert_not_called()


class WoreTodayCurrentShortcutTests(UITestCase):
    def test_ctrl_w_while_on_detail_view_marks_the_shown_record_worn(self) -> None:
        window = self._window()
        [record] = load_collection(self.watches_dir)
        window._show_detail(record)

        with patch.object(window, "_on_wore_today") as mock_wore:
            window._wore_today_current()

        mock_wore.assert_called_once_with(record)

    def test_ctrl_w_while_on_collection_view_does_nothing(self) -> None:
        window = self._window()

        with patch.object(window, "_on_wore_today") as mock_wore:
            window._wore_today_current()

        mock_wore.assert_not_called()

    def test_ctrl_w_end_to_end_persists_a_real_wear_record(self) -> None:
        window = self._window()
        [record] = load_collection(self.watches_dir)
        window._show_detail(record)

        window._wore_today_current()

        [reloaded] = load_collection(self.watches_dir)
        self.assertEqual(reloaded.watch.worn, [date.today()])


class FocusSearchShortcutTests(UITestCase):
    def test_ctrl_f_while_on_collection_view_focuses_the_search_field(self) -> None:
        window = self._window()
        QApplication.processEvents()

        window._focus_search()
        QApplication.processEvents()

        self.assertTrue(window._collection_view._top_bar._search_field.hasFocus())

    def test_ctrl_f_while_on_detail_view_does_nothing(self) -> None:
        window = self._window()
        [record] = load_collection(self.watches_dir)
        window._show_detail(record)
        QApplication.processEvents()

        window._focus_search()
        QApplication.processEvents()

        self.assertFalse(window._collection_view._top_bar._search_field.hasFocus())


class ExportPdfShortcutTests(UITestCase):
    def test_ctrl_p_while_on_detail_view_does_nothing(self) -> None:
        window = self._window()
        [record] = load_collection(self.watches_dir)
        window._show_detail(record)

        with patch("saat.ui.main_window.export_pdf") as mock_export:
            window._export_pdf()

        mock_export.assert_not_called()

    def test_ctrl_p_with_nothing_visible_shows_a_message_and_never_opens_the_save_dialog(self) -> None:
        """A search that matches nothing (SPEC.md milestone 19 §11/§12) is
        refused with a plain message before ever reaching the save dialog
        -- the user shouldn't have to pick a path for something that will
        fail. A real CollectionView with a real watch, filtered down to
        zero visible matches -- not an empty collection, which shows the
        empty state instead of a CollectionView at all."""
        window = self._window(count=1)
        window._collection_view._top_bar._search_field.setText("zzz-no-such-watch-zzz")
        QApplication.processEvents()
        self.assertEqual(window._collection_view.visible_records(), [])

        with patch.object(QFileDialog, "getSaveFileName") as mock_dialog, \
             patch.object(QMessageBox, "information") as mock_message:
            window._export_pdf()

        mock_dialog.assert_not_called()
        mock_message.assert_called_once()

    def test_ctrl_p_end_to_end_writes_a_real_pdf_to_the_chosen_path(self) -> None:
        window = self._window(count=2)
        out_path = self.tmp / "chosen.pdf"

        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(out_path), "")):
            window._export_pdf()

        self.assertTrue(out_path.exists())
        self.assertGreater(out_path.stat().st_size, 0)
        self.assertEqual(out_path.read_bytes()[:5], b"%PDF-")

    def test_ctrl_p_cancelling_the_save_dialog_writes_nothing(self) -> None:
        window = self._window()

        with patch.object(QFileDialog, "getSaveFileName", return_value=("", "")):
            window._export_pdf()

        self.assertEqual(list(self.tmp.glob("*.pdf")), [])

    def test_ctrl_p_exports_only_the_currently_visible_subset(self) -> None:
        """SPEC.md milestone 19 §11: whatever is currently visible -- the
        active search included -- not the full collection. Filtering down
        to one match and exporting must pass only that one record through,
        proven here via the actual call args rather than by re-parsing the
        rendered PDF (saat.ui.pdf_renderer's own tests already cover
        rendering correctness)."""
        window = self._window(count=3)
        window._collection_view._top_bar._search_field.setText("B")
        QApplication.processEvents()
        visible = window._collection_view.visible_records()
        self.assertEqual(len(visible), 1)

        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(self.tmp / "out.pdf"), "")), \
             patch("saat.ui.main_window.export_pdf") as mock_export:
            window._export_pdf()

        passed_records = mock_export.call_args.args[1]
        self.assertEqual([r.slug for r in passed_records], [r.slug for r in visible])

    def test_ctrl_p_failure_shows_a_message_and_restores_the_cursor_and_button(self) -> None:
        window = self._window()

        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(self.tmp / "out.pdf"), "")), \
             patch("saat.ui.main_window.export_pdf", side_effect=RuntimeError("disk full")), \
             patch.object(QMessageBox, "critical") as mock_critical:
            window._export_pdf()

        mock_critical.assert_called_once()
        self.assertEqual(QApplication.overrideCursor(), None)
        self.assertTrue(window._collection_view._top_bar._export_button.isEnabled())


class EscapeShortcutTests(UITestCase):
    def test_escape_from_detail_view_returns_to_collection(self) -> None:
        window = self._window()
        [record] = load_collection(self.watches_dir)
        window._show_detail(record)

        window._on_escape()

        self.assertIs(window.centralWidget().currentWidget(), window._collection_view)

    def test_escape_from_compare_view_returns_to_collection(self) -> None:
        window = self._window(count=2)
        collection_view = window.centralWidget().currentWidget()
        for card in collection_view._grid_view._cards:
            card._checkbox.setChecked(True)
        collection_view._top_bar._compare_button.click()
        self.assertIsInstance(window.centralWidget().currentWidget(), CompareView)

        window._on_escape()

        self.assertIs(window.centralWidget().currentWidget(), window._collection_view)

    def test_escape_while_on_collection_view_is_a_no_op(self) -> None:
        window = self._window()
        collection_view = window.centralWidget().currentWidget()

        window._on_escape()

        self.assertIs(window.centralWidget().currentWidget(), collection_view)

    def test_escape_clears_calendar_rotation_emphasis_without_changing_the_current_view(self) -> None:
        """SPEC.md §5.5: the Rotation click-through's emphasis clears on
        Escape. Driven through the real MainWindow, not the calendar widget
        directly, since the whole point is that _on_escape's single global
        dispatch point is what has to route this."""
        window = self._window()
        collection_view = window.centralWidget().currentWidget()
        [record] = load_collection(self.watches_dir)
        calendar_view = collection_view._calendar_view
        calendar_view._on_rotation_clicked(record.slug)
        self.assertEqual(calendar_view._emphasized_slug, record.slug)

        window._on_escape()

        self.assertIsNone(calendar_view._emphasized_slug)
        self.assertIs(window.centralWidget().currentWidget(), collection_view)


class ImageViewerOverlayGuardTests(UITestCase):
    """The image viewer (saat/ui/image_viewer.py) is a raised sibling of the
    stack, not a page inside it — _on_escape, _edit_current,
    _wore_today_current, _focus_search and _show_add_form all key off
    self._stack.currentWidget() or fire regardless of focus (Ctrl+N is a
    WindowShortcut), so each needs its own guard against the overlay."""

    def test_resize_keeps_the_overlay_geometry_synced_to_the_window(self) -> None:
        window = self._window()
        window._open_image_viewer([Path("/nonexistent/a.jpg")], 0)

        window.resize(900, 650)
        QApplication.processEvents()

        self.assertEqual(window._image_viewer.geometry(), window.rect())

    def test_escape_closes_the_overlay_instead_of_navigating_back(self) -> None:
        window = self._window()
        [record] = load_collection(self.watches_dir)
        window._show_detail(record)
        window._open_image_viewer([Path("/nonexistent/a.jpg")], 0)

        window._on_escape()

        self.assertIsNone(window._image_viewer)
        self.assertIs(window.centralWidget().currentWidget(), window._detail_view)

    def test_escape_with_no_overlay_open_still_navigates_back_as_before(self) -> None:
        window = self._window()
        [record] = load_collection(self.watches_dir)
        window._show_detail(record)

        window._on_escape()

        self.assertIs(window.centralWidget().currentWidget(), window._collection_view)

    def test_edit_current_is_a_no_op_while_the_overlay_is_open(self) -> None:
        window = self._window()
        [record] = load_collection(self.watches_dir)
        window._show_detail(record)
        window._open_image_viewer([Path("/nonexistent/a.jpg")], 0)

        with patch.object(window, "_show_edit_form") as mock_edit:
            window._edit_current()
        mock_edit.assert_not_called()

    def test_wore_today_current_is_a_no_op_while_the_overlay_is_open(self) -> None:
        window = self._window()
        [record] = load_collection(self.watches_dir)
        window._show_detail(record)
        window._open_image_viewer([Path("/nonexistent/a.jpg")], 0)

        with patch.object(window, "_on_wore_today") as mock_wore:
            window._wore_today_current()
        mock_wore.assert_not_called()

    def test_focus_search_is_a_no_op_while_the_overlay_is_open(self) -> None:
        window = self._window()
        window._open_image_viewer([Path("/nonexistent/a.jpg")], 0)
        QApplication.processEvents()

        window._focus_search()
        QApplication.processEvents()

        self.assertFalse(window._collection_view._top_bar._search_field.hasFocus())

    def test_ctrl_n_is_a_no_op_while_the_overlay_is_open(self) -> None:
        window = self._window()
        window._open_image_viewer([Path("/nonexistent/a.jpg")], 0)

        with patch.object(WatchForm, "exec") as mock_exec:
            window._show_add_form()
        mock_exec.assert_not_called()

    def test_export_pdf_is_a_no_op_while_the_overlay_is_open(self) -> None:
        window = self._window()
        window._open_image_viewer([Path("/nonexistent/a.jpg")], 0)

        with patch("saat.ui.main_window.export_pdf") as mock_export:
            window._export_pdf()
        mock_export.assert_not_called()


if __name__ == "__main__":
    unittest.main()
