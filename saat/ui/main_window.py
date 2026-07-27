import dataclasses
from datetime import date
from pathlib import Path

from PySide6.QtCore import QSize, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QSystemTrayIcon,
)

from saat import __version__, autostart
from saat.config import Config
from saat.paths import data_dir
from saat.selection import MODE_WEIGHTED
from saat.sellers import Seller, load_sellers
from saat.sellers import sellers_path as default_sellers_path
from saat.storage import WatchRecord, create_watch, delete_watch, load_collection, save_watch
from saat.ui.collection_view import CollectionView
from saat.ui.compare_view import CompareView
from saat.ui.detail_view import DetailView
from saat.ui.dialogs import DeleteConfirmDialog
from saat.ui.empty_state import EmptyStateView
from saat.ui.image_viewer import ImageViewerOverlay
from saat.ui import motion
from saat.ui.pdf_renderer import ExportError, export_pdf
from saat.ui.sellers_dialog import SellersDialog
from saat.ui import theme
from saat.ui.today_picker import TodayPickerDialog
from saat.ui.top_bar import SCOPE_WISHLIST
from saat.ui.tray import TrayController
from saat.ui.watch_form import WatchForm
from saat.wear import assign_worn, clear_worn, mark_worn_today

MIN_SIZE = QSize(1100, 700)
DEFAULT_SIZE = QSize(1600, 1000)
TRAY_AVAILABILITY_POLL_MS = 3000


class MainWindow(QMainWindow):
    def __init__(
        self,
        watches_dir: Path | None = None,
        backups_dir: Path | None = None,
        config: Config | None = None,
        sellers_path: Path | None = None,
        tray_available: bool | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle(f"SAAT v{__version__}")
        self.setMinimumSize(MIN_SIZE)

        self._watches_dir = watches_dir if watches_dir is not None else data_dir() / "watches"
        self._backups_dir = backups_dir if backups_dir is not None else data_dir() / "backups"
        self._config = config if config is not None else Config()
        self._sellers_path = sellers_path if sellers_path is not None else default_sellers_path(data_dir())
        self._sellers: list[Seller] = load_sellers(self._sellers_path)
        self._restore_geometry()

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)
        self._collection_view: CollectionView | None = None
        self._detail_view: DetailView | None = None
        self._compare_view: CompareView | None = None
        self._image_viewer: ImageViewerOverlay | None = None

        # Capability detection before any UI (SPEC.md milestone 18 §5):
        # checked once, here, and treated as authoritative for the rest of
        # this window's life except for _poll_tray_availability's own
        # narrow resilience carve-out.
        self._tray_available = (
            tray_available if tray_available is not None else QSystemTrayIcon.isSystemTrayAvailable()
        )
        self._tray: TrayController | None = None
        self._tray_poll_timer: QTimer | None = None
        if self._tray_available:
            self._setup_tray()

        self._load_and_show_collection()
        self._install_shortcuts()

    def _setup_tray(self) -> None:
        self._tray = TrayController(
            window_visible_getter=self.isVisible,
            autostart_available=autostart.is_available(),
            parent=self,
        )
        self._tray.show_hide_requested.connect(self._on_tray_show_hide)
        self._tray.wore_today_requested.connect(self._on_wore_today)
        self._tray.close_to_tray_toggled.connect(self._on_close_to_tray_toggled)
        self._tray.start_minimised_toggled.connect(self._on_start_minimised_toggled)
        self._tray.start_at_login_toggled.connect(self._on_start_at_login_toggled)
        self._tray.quit_requested.connect(self._quit)
        self._tray.set_close_to_tray_checked(self._config.close_to_tray())
        self._tray.set_start_minimised_checked(self._config.start_minimised())
        self._tray.show()

        self._tray_poll_timer = QTimer(self)
        self._tray_poll_timer.setInterval(TRAY_AVAILABILITY_POLL_MS)
        self._tray_poll_timer.timeout.connect(self._poll_tray_availability)
        self._tray_poll_timer.start()

    def bring_to_front(self) -> None:
        """Raise and focus this window regardless of its current state --
        hidden, minimized, or merely behind another window. Used by a second
        launch signalling the first instance (single_instance.py) and by
        the tray icon's own restore actions (left click, Show/Hide)."""
        if self.isMinimized():
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # The image viewer is a raised sibling of the QStackedWidget, not a
        # page inside it -- Qt's own "current stack page fills the central
        # widget" layout management doesn't reach it, so it needs the same
        # geometry hand-tracking motion.fade_transition's transient overlay
        # already does for its own short-lived pixmap snapshot, just kept
        # alive for as long as the viewer stays open.
        if self._image_viewer is not None:
            self._image_viewer.setGeometry(self.rect())

    def _install_shortcuts(self) -> None:
        """SPEC.md §5.11. WindowShortcut (QShortcut's default context) only
        fires while this window itself is the focused top-level — WatchForm,
        DeleteConfirmDialog, and WatchPicker are modal QDialogs running their
        own exec() loop, so none of these can fire while one is open, and
        Escape there is already QDialog's own default (reject on Escape).
        That's also why Ctrl+N needs no "is a dialog already open" guard."""
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._show_add_form)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self._focus_search)
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self._edit_current)
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(self._wore_today_current)
        QShortcut(QKeySequence("Ctrl+P"), self).activated.connect(self._export_pdf)
        # Connects to _quit(), not self.close(): Ctrl+Q must always quit
        # (SPEC.md §5.11), even with close-to-tray ON, when closeEvent
        # itself would otherwise hide instead of accepting the close.
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self._quit)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self._on_escape)

    def _focus_search(self) -> None:
        if self._image_viewer is not None:
            return
        if self._collection_view is not None and self._stack.currentWidget() is self._collection_view:
            self._collection_view.focus_search()

    def _edit_current(self) -> None:
        # "Current watch" is the detail view's watch — routes to the exact
        # handler the detail page's own Edit button calls, not a parallel path.
        if self._image_viewer is not None:
            return
        if self._detail_view is not None and self._stack.currentWidget() is self._detail_view:
            self._show_edit_form(self._detail_view.record)

    def _wore_today_current(self) -> None:
        if self._image_viewer is not None:
            return
        if self._detail_view is not None and self._stack.currentWidget() is self._detail_view:
            self._on_wore_today(self._detail_view.record)

    def _on_escape(self) -> None:
        if self._image_viewer is not None:
            self._close_image_viewer()
            return
        current = self._stack.currentWidget()
        if current is self._detail_view or current is self._compare_view:
            self._show_collection()
        elif current is self._collection_view and self._collection_view is not None:
            self._collection_view.clear_calendar_emphasis()

    def _open_image_viewer(self, images: list[Path], start_index: int) -> None:
        if self._image_viewer is not None:
            self._close_image_viewer()
        viewer = ImageViewerOverlay(images, start_index, self)
        viewer.setGeometry(self.rect())
        viewer.closed.connect(self._close_image_viewer)
        self._image_viewer = viewer
        viewer.show()
        viewer.raise_()
        viewer.setFocus()

    def _close_image_viewer(self) -> None:
        if self._image_viewer is None:
            return
        viewer = self._image_viewer
        self._image_viewer = None
        viewer.hide()
        viewer.deleteLater()

    def _load_and_show_collection(self) -> None:
        while self._stack.count():
            widget = self._stack.widget(0)
            self._stack.removeWidget(widget)
            widget.deleteLater()
        self._collection_view = None
        self._detail_view = None
        self._compare_view = None

        records = load_collection(self._watches_dir)
        if records:
            self._collection_view = CollectionView(records, self._config, self)
            self._collection_view.record_activated.connect(self._show_detail)
            self._collection_view.add_watch_requested.connect(self._show_add_form)
            self._collection_view.assign_worn_requested.connect(self._on_assign_worn)
            self._collection_view.clear_worn_requested.connect(self._on_clear_worn)
            self._collection_view.theme_toggle_requested.connect(self._on_theme_toggle)
            self._collection_view.wore_today_requested.connect(self._on_wore_today)
            self._collection_view.compare_requested.connect(self._show_compare)
            self._collection_view.export_requested.connect(self._export_pdf)
            self._collection_view.pick_requested.connect(self._on_pick_requested)
            self._stack.addWidget(self._collection_view)
            self._stack.setCurrentWidget(self._collection_view)
        else:
            empty_state = EmptyStateView(self._watches_dir, self)
            empty_state.add_watch_requested.connect(self._show_add_form)
            self._stack.addWidget(empty_state)
            self._stack.setCurrentWidget(empty_state)

        self._sync_tray_records()

    def _show_detail(self, record: WatchRecord) -> None:
        def _apply() -> None:
            if self._detail_view is not None:
                self._stack.removeWidget(self._detail_view)
                self._detail_view.deleteLater()

            self._detail_view = DetailView(record, self._current_records(), self, sellers=self._sellers)
            self._detail_view.back_requested.connect(self._show_collection)
            self._detail_view.edit_requested.connect(self._show_edit_form)
            self._detail_view.delete_requested.connect(self._show_delete_confirm)
            self._detail_view.wore_today_requested.connect(self._on_wore_today)
            self._detail_view.move_to_owned_requested.connect(self._on_move_to_owned)
            self._detail_view.image_viewer_requested.connect(self._open_image_viewer)
            self._stack.addWidget(self._detail_view)
            self._stack.setCurrentWidget(self._detail_view)

        motion.fade_transition(self._stack, _apply)

    def _show_collection(self) -> None:
        if self._collection_view is not None:
            motion.fade_transition(self._stack, lambda: self._stack.setCurrentWidget(self._collection_view))

    def _show_compare(self, records: list[WatchRecord]) -> None:
        def _apply() -> None:
            if self._compare_view is not None:
                self._stack.removeWidget(self._compare_view)
                self._compare_view.deleteLater()

            scope = self._collection_view.current_scope() if self._collection_view is not None else None
            self._compare_view = CompareView(records, self, is_wishlist=(scope == SCOPE_WISHLIST))
            self._compare_view.back_requested.connect(self._show_collection)
            self._stack.addWidget(self._compare_view)
            self._stack.setCurrentWidget(self._compare_view)

        motion.fade_transition(self._stack, _apply)

    def _current_records(self) -> list[WatchRecord]:
        return self._collection_view.records if self._collection_view is not None else []

    def _find_record(self, slug: str) -> WatchRecord | None:
        return next((r for r in self._current_records() if r.slug == slug), None)

    def _on_assign_worn(self, dates: list[date], target: WatchRecord) -> None:
        self._apply_worn_update(assign_worn(self._backups_dir, self._current_records(), dates, target))

    def _on_clear_worn(self, dates: list[date]) -> None:
        self._apply_worn_update(clear_worn(self._backups_dir, self._current_records(), dates))

    def _on_wore_today(self, target: WatchRecord) -> None:
        self._apply_worn_update(mark_worn_today(self._backups_dir, self._current_records(), target))

    def _on_pick_requested(self) -> None:
        """Milestone 20: the top bar's picker button. wore_today_requested
        routes to the same _on_wore_today handler every other "Wore this
        today" affordance already uses — this dialog only ever emits a
        request, never writes on its own."""
        mode = self._config.picker_mode() or MODE_WEIGHTED
        dialog = TodayPickerDialog(self._current_records(), mode, on_mode_changed=self._on_picker_mode_changed, parent=self)
        dialog.wore_today_requested.connect(self._on_wore_today)
        dialog.exec()

    def _on_picker_mode_changed(self, mode: str) -> None:
        self._config.set_picker_mode(mode)
        self._config.save()

    def _apply_worn_update(self, records: list[WatchRecord]) -> None:
        """Wear edits use the light set_records() path — unlike add/edit/
        delete, this must not reset sort, search, facets, or which calendar
        month is on screen (see CollectionView.set_records)."""
        if self._collection_view is not None:
            self._collection_view.set_records(records)
        if self._detail_view is not None:
            refreshed = next((r for r in records if r.slug == self._detail_view.record.slug), None)
            if refreshed is not None:
                self._show_detail(refreshed)
        self._sync_tray_records()

    def _sync_tray_records(self) -> None:
        if self._tray is not None:
            self._tray.set_records(self._current_records())

    def _export_pdf(self) -> None:
        """SPEC.md milestone 19 §9: exports whatever is currently visible
        in the collection view -- the active scope, active filters, active
        search, current sort order -- with no options of its own. Only
        meaningful while the collection view is actually on screen, same
        guard Ctrl+F's _focus_search already applies, since Ctrl+P is a
        window-level shortcut that could otherwise fire over the detail or
        compare page."""
        if self._image_viewer is not None:
            return
        if self._collection_view is None or self._stack.currentWidget() is not self._collection_view:
            return

        records = self._collection_view.visible_records()
        if not any(r.watch is not None for r in records):
            QMessageBox.information(self, "SAAT", self.tr("There is nothing to export in the current view."))
            return

        is_wishlist = self._collection_view.current_scope() == SCOPE_WISHLIST
        # Flows straight into the rendered PDF's title/footer text
        # (export_pdf()'s document_title param) -- part of the sweep like
        # pdf_renderer.py's own strings, not left in English.
        document_title = self.tr("SAAT Wishlist") if is_wishlist else self.tr("SAAT Collection")

        documents_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        default_name = f"SAAT-collection-{date.today():%d-%m-%Y}.pdf"
        default_path = str(Path(documents_dir) / default_name) if documents_dir else default_name

        path_str, _ = QFileDialog.getSaveFileName(self, self.tr("Export to PDF"), default_path, self.tr("PDF files (*.pdf)"))
        if not path_str:
            return

        self._collection_view.set_export_enabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            export_pdf(Path(path_str), records, is_wishlist, document_title)
        except Exception as exc:
            QMessageBox.critical(self, "SAAT", self.tr("Could not export the PDF: {error}").format(error=exc))
        finally:
            QApplication.restoreOverrideCursor()
            self._collection_view.set_export_enabled(True)

    def _on_theme_toggle(self) -> None:
        new_mode = theme.MODE_LIGHT if theme.current_mode() == theme.MODE_DARK else theme.MODE_DARK
        theme.apply_theme(QApplication.instance(), new_mode)
        self._config.set_theme_mode(new_mode)
        self._config.save()

    def _manage_sellers(self) -> list[Seller]:
        """Passed into WatchForm as a callback so it can open the dialog
        without needing to know about backups_dir/sellers_path itself —
        MainWindow owns all disk I/O, WatchForm stays a pure UI component.
        Updates self._sellers so every subsequently-opened form/detail page
        sees the change, not just the one that triggered it."""
        dialog = SellersDialog(self._sellers, self._backups_dir, self._sellers_path, parent=self)
        dialog.exec()
        self._sellers = dialog.sellers()
        return self._sellers

    def _show_add_form(self) -> None:
        # Mouse can't reach this while the image viewer covers the window --
        # only Ctrl+N (a WindowShortcut, active regardless of focus) could
        # otherwise open it over the overlay and then tear down the page
        # underneath via _load_and_show_collection(), leaving the viewer
        # orphaned above a rebuilt collection. Same blind spot as the four
        # handlers guarded in _edit_current/_wore_today_current/_focus_search
        # /_on_escape, just missed there since this one isn't a "current
        # watch" action.
        if self._image_viewer is not None:
            return
        scope = self._collection_view.current_scope() if self._collection_view is not None else None
        default_status = "Wishlist" if scope == SCOPE_WISHLIST else None
        form = WatchForm(
            self._current_records(), record=None, parent=self, default_status=default_status,
            sellers=self._sellers, manage_sellers=self._manage_sellers,
        )
        if form.exec() != QDialog.DialogCode.Accepted:
            return
        created = create_watch(self._watches_dir, self._backups_dir, form.saved_watch())
        form.images_tab().commit(created.path / "images")
        self._load_and_show_collection()

    def _show_edit_form(self, record: WatchRecord) -> None:
        form = WatchForm(
            self._current_records(), record=record, parent=self,
            sellers=self._sellers, manage_sellers=self._manage_sellers,
        )
        if form.exec() != QDialog.DialogCode.Accepted:
            return
        updated_record = dataclasses.replace(record, watch=form.saved_watch())
        save_watch(self._backups_dir, updated_record)
        form.images_tab().commit(updated_record.path / "images")
        self._load_and_show_collection()

        refreshed = self._find_record(record.slug)
        if refreshed is not None:
            self._show_detail(refreshed)

    def _on_move_to_owned(self, record: WatchRecord) -> None:
        """SPEC.md §5.12: one click, no dialog. Carries target_price into
        price as the default — only when price isn't already set, never
        overwriting a real paid price — and leaves target_price/target_date
        in place afterward rather than discarding them."""
        watch = record.watch
        new_price = watch.acquisition.price if watch.acquisition.price is not None else watch.acquisition.target_price
        updated_watch = dataclasses.replace(
            watch, status="Owned", acquisition=dataclasses.replace(watch.acquisition, price=new_price)
        )
        save_watch(self._backups_dir, dataclasses.replace(record, watch=updated_watch))
        self._load_and_show_collection()

        refreshed = self._find_record(record.slug)
        if refreshed is not None:
            self._show_detail(refreshed)

    def _show_delete_confirm(self, record: WatchRecord) -> None:
        dialog = DeleteConfirmDialog(record.watch, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        delete_watch(self._backups_dir, record)
        self._load_and_show_collection()

    def _restore_geometry(self) -> None:
        geometry = self._config.window_geometry()
        if not geometry or "width" not in geometry or "height" not in geometry:
            self.resize(DEFAULT_SIZE)
            return

        width = max(int(geometry["width"]), MIN_SIZE.width())
        height = max(int(geometry["height"]), MIN_SIZE.height())
        self.resize(width, height)

        x, y = geometry.get("x"), geometry.get("y")
        if x is not None and y is not None:
            self.move(int(x), int(y))

        if geometry.get("maximized"):
            self.setWindowState(Qt.WindowState.WindowMaximized)

    def closeEvent(self, event: QCloseEvent) -> None:
        # Close-to-tray only intercepts the window-manager close button --
        # Ctrl+Q and the tray menu's own Quit call _quit() directly and
        # never reach this method, so both always quit regardless of the
        # setting (SPEC.md milestone 18 §7's "Quit always quits").
        if self._tray is not None and self._config.close_to_tray():
            event.ignore()
            self._hide_to_tray()
            return

        self._save_geometry()
        super().closeEvent(event)

    def _save_geometry(self) -> None:
        self._config.set_window_geometry({
            "width": self.width(),
            "height": self.height(),
            "x": self.x(),
            "y": self.y(),
            "maximized": self.isMaximized(),
        })
        self._config.save()

    def _quit(self) -> None:
        self._save_geometry()
        QApplication.instance().quit()

    def _hide_to_tray(self) -> None:
        self.hide()
        if self._tray is None:
            return
        # Once, ever (SPEC.md milestone 18 §10) -- and only actually
        # persisted as shown when the host could deliver it, so a platform
        # that can't show tray messages today doesn't burn the one chance
        # a future session (a shell restart, a new tray host) might have.
        if not self._config.tray_hint_shown() and self._tray.supports_messages():
            self._tray.show_hint_message()
            self._config.set_tray_hint_shown(True)
            self._config.save()

    def _on_tray_show_hide(self) -> None:
        if self.isVisible():
            self._hide_to_tray()
        else:
            self.bring_to_front()

    def _on_close_to_tray_toggled(self, checked: bool) -> None:
        self._config.set_close_to_tray(checked)
        self._config.save()

    def _on_start_minimised_toggled(self, checked: bool) -> None:
        self._config.set_start_minimised(checked)
        self._config.save()

    def _on_start_at_login_toggled(self, checked: bool) -> None:
        # No local bookkeeping on success -- the checkbox re-reads
        # autostart.is_enabled() from disk the next time the menu opens
        # (TrayController._refresh_menu), per SPEC.md milestone 18 §14.
        # Surfaced on failure rather than swallowed (SPEC.md §2 rule 7);
        # the checkbox itself will fall back to whatever actually happened
        # on disk the same way, with no separate revert needed here.
        try:
            if checked:
                autostart.enable()
            else:
                autostart.disable()
        except Exception as exc:
            QMessageBox.critical(self, "SAAT", self.tr("Could not update the autostart entry: {error}").format(error=exc))

    def should_start_hidden(self, started_via_autostart: bool) -> bool:
        """SPEC.md milestone 18 §15: 'Start minimised' only ever affects an
        autostarted launch, never a manual one -- a user who runs the app
        expects a window. Also requires a tray to exist right now: starting
        hidden with nothing to restore from would strand the user exactly
        as badly as anything else in this milestone."""
        return self._tray_available and started_via_autostart and self._config.start_minimised()

    def _poll_tray_availability(self) -> None:
        """SPEC.md milestone 18 §9: if the tray disappears (shell restart,
        compositor reload) while the window is hidden, a hidden window with
        a dead tray is unreachable -- the single most important requirement
        in the milestone. Restores the window and falls back to the same
        shape a fresh no-tray launch would have for the rest of this run,
        rather than leaving a half-torn-down tray around to reference
        again."""
        if self._tray is None or QSystemTrayIcon.isSystemTrayAvailable():
            return

        was_hidden = not self.isVisible()
        tray = self._tray
        self._tray = None
        self._tray_available = False
        if self._tray_poll_timer is not None:
            self._tray_poll_timer.stop()
        tray.hide()
        tray.deleteLater()
        if was_hidden:
            self.bring_to_front()
