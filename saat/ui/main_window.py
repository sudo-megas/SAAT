import dataclasses
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QDialog, QMainWindow, QStackedWidget

from saat.config import Config
from saat.paths import app_dir
from saat.storage import WatchRecord, create_watch, delete_watch, load_collection, save_watch
from saat.ui.collection_view import CollectionView
from saat.ui.detail_view import DetailView
from saat.ui.dialogs import DeleteConfirmDialog
from saat.ui.empty_state import EmptyStateView
from saat.ui.watch_form import WatchForm

MIN_SIZE = QSize(1100, 700)
DEFAULT_SIZE = QSize(1600, 1000)


class MainWindow(QMainWindow):
    def __init__(
        self,
        watches_dir: Path | None = None,
        backups_dir: Path | None = None,
        config: Config | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("SAAT")
        self.setMinimumSize(MIN_SIZE)

        self._watches_dir = watches_dir if watches_dir is not None else app_dir() / "watches"
        self._backups_dir = backups_dir if backups_dir is not None else app_dir() / "backups"
        self._config = config if config is not None else Config()
        self._restore_geometry()

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)
        self._collection_view: CollectionView | None = None
        self._detail_view: DetailView | None = None

        self._load_and_show_collection()

    def _load_and_show_collection(self) -> None:
        while self._stack.count():
            widget = self._stack.widget(0)
            self._stack.removeWidget(widget)
            widget.deleteLater()
        self._collection_view = None
        self._detail_view = None

        records = load_collection(self._watches_dir)
        if records:
            self._collection_view = CollectionView(records, self._config, self)
            self._collection_view.record_activated.connect(self._show_detail)
            self._collection_view.add_watch_requested.connect(self._show_add_form)
            self._stack.addWidget(self._collection_view)
            self._stack.setCurrentWidget(self._collection_view)
        else:
            empty_state = EmptyStateView(self._watches_dir, self)
            empty_state.add_watch_requested.connect(self._show_add_form)
            self._stack.addWidget(empty_state)
            self._stack.setCurrentWidget(empty_state)

    def _show_detail(self, record: WatchRecord) -> None:
        if self._detail_view is not None:
            self._stack.removeWidget(self._detail_view)
            self._detail_view.deleteLater()

        self._detail_view = DetailView(record, self)
        self._detail_view.back_requested.connect(self._show_collection)
        self._detail_view.edit_requested.connect(self._show_edit_form)
        self._detail_view.delete_requested.connect(self._show_delete_confirm)
        self._stack.addWidget(self._detail_view)
        self._stack.setCurrentWidget(self._detail_view)

    def _show_collection(self) -> None:
        if self._collection_view is not None:
            self._stack.setCurrentWidget(self._collection_view)

    def _current_records(self) -> list[WatchRecord]:
        return self._collection_view.records if self._collection_view is not None else []

    def _find_record(self, slug: str) -> WatchRecord | None:
        return next((r for r in self._current_records() if r.slug == slug), None)

    def _show_add_form(self) -> None:
        form = WatchForm(self._current_records(), record=None, parent=self)
        if form.exec() != QDialog.DialogCode.Accepted:
            return
        create_watch(self._watches_dir, self._backups_dir, form.saved_watch())
        self._load_and_show_collection()

    def _show_edit_form(self, record: WatchRecord) -> None:
        form = WatchForm(self._current_records(), record=record, parent=self)
        if form.exec() != QDialog.DialogCode.Accepted:
            return
        updated_record = dataclasses.replace(record, watch=form.saved_watch())
        save_watch(self._backups_dir, updated_record)
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
