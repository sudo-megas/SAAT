from PySide6.QtCore import Signal
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from saat.config import Config
from saat.storage import WatchRecord
from saat.ui.columns import COLUMN_PRESETS, DEFAULT_COLUMN_KEYS, sort_key
from saat.ui.grid_view import GridView
from saat.ui.table_view import TableView
from saat.ui.top_bar import PRESET_DEFAULT, VIEW_GRID, VIEW_TABLE, TopBar

DEFAULT_SORT_KEY = "brand"


class CollectionView(QWidget):
    """Top bar plus grid/table, switchable. Search and the filter sidebar
    land in a later milestone."""

    record_activated = Signal(object)
    add_watch_requested = Signal()

    def __init__(self, records: list[WatchRecord], config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._records = records
        self._config = config
        self._sort_field = DEFAULT_SORT_KEY

        self._top_bar = TopBar()
        self._grid_view = GridView()
        self._table_view = TableView(on_columns_changed=self._save_columns)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._grid_view)
        self._stack.addWidget(self._table_view)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._top_bar)
        layout.addWidget(self._stack, stretch=1)

        self._top_bar.view_changed.connect(self._on_view_changed)
        self._top_bar.sort_changed.connect(self._on_sort_changed)
        self._top_bar.preset_changed.connect(self._on_preset_changed)
        self._grid_view.record_activated.connect(self.record_activated.emit)
        self._table_view.record_activated.connect(self.record_activated.emit)
        self._top_bar.add_watch_requested.connect(self.add_watch_requested.emit)

        self._table_view.set_columns(self._config.column_keys() or DEFAULT_COLUMN_KEYS)
        self._apply_sort_and_render()

        last_view = self._config.last_view()
        self._top_bar.set_view(last_view if last_view in (VIEW_GRID, VIEW_TABLE) else VIEW_GRID)

    @property
    def records(self) -> list[WatchRecord]:
        return self._records

    def _apply_sort_and_render(self) -> None:
        valid = sorted(
            (r for r in self._records if r.watch is not None),
            key=lambda r: sort_key(self._sort_field)(r.watch),
        )
        broken = [r for r in self._records if r.watch is None]
        ordered = valid + broken
        self._grid_view.set_records(ordered)
        self._table_view.set_records(ordered)

    def _on_view_changed(self, view: str) -> None:
        self._stack.setCurrentWidget(self._grid_view if view == VIEW_GRID else self._table_view)
        self._config.set_last_view(view)
        self._config.save()

    def _on_sort_changed(self, key: str) -> None:
        self._sort_field = key
        self._apply_sort_and_render()

    def _on_preset_changed(self, preset: str) -> None:
        keys = DEFAULT_COLUMN_KEYS if preset == PRESET_DEFAULT else COLUMN_PRESETS.get(preset, DEFAULT_COLUMN_KEYS)
        self._table_view.set_columns(keys)
        self._save_columns(keys)

    def _save_columns(self, keys: list[str]) -> None:
        self._config.set_column_keys(keys)
        self._config.save()
