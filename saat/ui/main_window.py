import dataclasses
from datetime import date
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QStackedWidget

from saat import __version__
from saat.config import Config
from saat.paths import data_dir
from saat.sellers import Seller, load_sellers
from saat.sellers import sellers_path as default_sellers_path
from saat.storage import WatchRecord, create_watch, delete_watch, load_collection, save_watch
from saat.ui.collection_view import CollectionView
from saat.ui.compare_view import CompareView
from saat.ui.detail_view import DetailView
from saat.ui.dialogs import DeleteConfirmDialog
from saat.ui.empty_state import EmptyStateView
from saat.ui import motion
from saat.ui.sellers_dialog import SellersDialog
from saat.ui import theme
from saat.ui.top_bar import SCOPE_WISHLIST
from saat.ui.watch_form import WatchForm
from saat.wear import assign_worn, clear_worn, mark_worn_today

MIN_SIZE = QSize(1100, 700)
DEFAULT_SIZE = QSize(1600, 1000)


class MainWindow(QMainWindow):
    def __init__(
        self,
        watches_dir: Path | None = None,
        backups_dir: Path | None = None,
        config: Config | None = None,
        sellers_path: Path | None = None,
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

        self._load_and_show_collection()
        self._install_shortcuts()

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
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self.close)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self._on_escape)

    def _focus_search(self) -> None:
        if self._collection_view is not None and self._stack.currentWidget() is self._collection_view:
            self._collection_view.focus_search()

    def _edit_current(self) -> None:
        # "Current watch" is the detail view's watch — routes to the exact
        # handler the detail page's own Edit button calls, not a parallel path.
        if self._detail_view is not None and self._stack.currentWidget() is self._detail_view:
            self._show_edit_form(self._detail_view.record)

    def _wore_today_current(self) -> None:
        if self._detail_view is not None and self._stack.currentWidget() is self._detail_view:
            self._on_wore_today(self._detail_view.record)

    def _on_escape(self) -> None:
        current = self._stack.currentWidget()
        if current is self._detail_view or current is self._compare_view:
            self._show_collection()
        elif current is self._collection_view and self._collection_view is not None:
            self._collection_view.clear_calendar_emphasis()

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
            self._stack.addWidget(self._collection_view)
            self._stack.setCurrentWidget(self._collection_view)
        else:
            empty_state = EmptyStateView(self._watches_dir, self)
            empty_state.add_watch_requested.connect(self._show_add_form)
            self._stack.addWidget(empty_state)
            self._stack.setCurrentWidget(empty_state)

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
        self._config.set_window_geometry({
            "width": self.width(),
            "height": self.height(),
            "x": self.x(),
            "y": self.y(),
            "maximized": self.isMaximized(),
        })
        self._config.save()
        super().closeEvent(event)
