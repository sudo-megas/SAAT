from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from saat.config import Config
from saat.storage import WatchRecord
from saat.ui.calendar_view import CalendarView
from saat.ui.columns import COLUMN_PRESETS, DEFAULT_COLUMN_KEYS, sort_key
from saat.ui.facets import VALUE_FACETS, is_not_worn_90d
from saat.ui.filtering import NOT_WORN_FACET_KEY, FilterState, passes
from saat.ui.grid_view import GridView
from saat.ui.sidebar import Sidebar
from saat.ui.table_view import TableView
from saat.ui.top_bar import PRESET_DEFAULT, VIEW_CALENDAR, VIEW_GRID, VIEW_TABLE, TopBar

DEFAULT_SORT_KEY = "brand"


class CollectionView(QWidget):
    """Sidebar, top bar, and grid/table, switchable. See SPEC.md §5.1."""

    record_activated = Signal(object)
    add_watch_requested = Signal()
    theme_toggle_requested = Signal()
    assign_worn_requested = Signal(list, object)  # list[date], WatchRecord
    clear_worn_requested = Signal(list)  # list[date]

    def __init__(self, records: list[WatchRecord], config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._records = records
        self._config = config
        self._sort_field = DEFAULT_SORT_KEY

        self._sidebar = Sidebar(records)
        self._top_bar = TopBar()
        self._grid_view = GridView()
        self._table_view = TableView(on_columns_changed=self._save_columns)
        self._calendar_view = CalendarView(records)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._grid_view)
        self._stack.addWidget(self._table_view)
        self._stack.addWidget(self._calendar_view)

        main_column = QVBoxLayout()
        main_column.setContentsMargins(0, 0, 0, 0)
        main_column.setSpacing(0)
        main_column.addWidget(self._top_bar)
        main_column.addWidget(self._stack, stretch=1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar)
        layout.addLayout(main_column, 1)

        self._sidebar.changed.connect(self._recompute)
        self._top_bar.view_changed.connect(self._on_view_changed)
        self._top_bar.sort_changed.connect(self._on_sort_changed)
        self._top_bar.preset_changed.connect(self._on_preset_changed)
        self._top_bar.search_changed.connect(lambda _text: self._recompute())
        self._grid_view.record_activated.connect(self.record_activated.emit)
        self._table_view.record_activated.connect(self.record_activated.emit)
        self._top_bar.add_watch_requested.connect(self.add_watch_requested.emit)
        self._top_bar.theme_toggle_requested.connect(self.theme_toggle_requested.emit)
        self._calendar_view.assign_requested.connect(self.assign_worn_requested.emit)
        self._calendar_view.clear_requested.connect(self.clear_worn_requested.emit)

        self._table_view.set_columns(self._config.column_keys() or DEFAULT_COLUMN_KEYS)
        self._recompute()

        last_view = self._config.last_view()
        valid_views = (VIEW_GRID, VIEW_TABLE, VIEW_CALENDAR)
        self._top_bar.set_view(last_view if last_view in valid_views else VIEW_GRID)

    @property
    def records(self) -> list[WatchRecord]:
        """The full, unfiltered collection — WatchForm's enum* suggestions and
        slug lookups need every record, not just what search/facets show."""
        return self._records

    def set_records(self, records: list[WatchRecord]) -> None:
        """For a worn-date change: refreshes grid/table/sidebar/calendar from
        the updated records without touching sort, search, facet selections,
        or which calendar month is on screen. Add/edit/delete still go
        through MainWindow's full reload — this is only for wear edits,
        which are frequent and must not reset the calendar's navigation."""
        self._records = records
        self._recompute()
        self._calendar_view.set_records(records)

    def _filter_state(self) -> FilterState:
        return FilterState(
            active_values=self._sidebar.active_facets(),
            not_worn_only=self._sidebar.not_worn_only(),
            query=self._top_bar.search_text(),
        )

    def _recompute(self) -> None:
        valid = [r for r in self._records if r.watch is not None]
        state = self._filter_state()

        matching = sorted(
            (r for r in valid if passes(r.watch, state)),
            key=lambda r: sort_key(self._sort_field)(r.watch),
        )
        broken = [] if state.is_active() else [r for r in self._records if r.watch is None]
        ordered = matching + broken
        self._grid_view.set_records(ordered)
        self._table_view.set_records(ordered)

        self._sidebar.update_counts(*self._compute_counts(valid, state))

    def _compute_counts(self, valid: list[WatchRecord], state: FilterState) -> tuple[dict[str, dict[str, int]], int]:
        counts: dict[str, dict[str, int]] = {}
        for facet in VALUE_FACETS:
            tally: dict[str, int] = {}
            for record in valid:
                if not passes(record.watch, state, skip=facet.key):
                    continue
                for value in facet.extract(record.watch):
                    tally[value] = tally.get(value, 0) + 1
            counts[facet.key] = tally

        not_worn_count = sum(
            1
            for record in valid
            if passes(record.watch, state, skip=NOT_WORN_FACET_KEY) and is_not_worn_90d(record.watch)
        )
        return counts, not_worn_count

    def _on_view_changed(self, view: str) -> None:
        widget = {VIEW_GRID: self._grid_view, VIEW_TABLE: self._table_view, VIEW_CALENDAR: self._calendar_view}[view]
        self._stack.setCurrentWidget(widget)
        self._config.set_last_view(view)
        self._config.save()

    def _on_sort_changed(self, key: str) -> None:
        self._sort_field = key
        self._recompute()

    def _on_preset_changed(self, preset: str) -> None:
        keys = DEFAULT_COLUMN_KEYS if preset == PRESET_DEFAULT else COLUMN_PRESETS.get(preset, DEFAULT_COLUMN_KEYS)
        self._table_view.set_columns(keys)
        self._save_columns(keys)

    def _save_columns(self, keys: list[str]) -> None:
        self._config.set_column_keys(keys)
        self._config.save()
