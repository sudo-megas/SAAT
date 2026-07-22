from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QAbstractItemView, QMenu, QTableWidget, QTableWidgetItem

from saat.storage import WatchRecord
from saat.ui.columns import COLUMNS, COLUMNS_BY_KEY, GROUP_ORDER
from saat.ui.formatting import EM_DASH, is_numeric_value
from saat.ui.theme import SIZE_SM, resolve_fonts


class _SortableItem(QTableWidgetItem):
    def __init__(self, text: str, sort_value: object) -> None:
        super().__init__(text)
        self.sort_value = sort_value
        self.setFlags(self.flags() & ~Qt.ItemFlag.ItemIsEditable)

    def __lt__(self, other: object) -> bool:
        a = self.sort_value
        b = other.sort_value if isinstance(other, _SortableItem) else None
        if a is None:
            return b is not None
        if b is None:
            return False
        try:
            return a < b
        except TypeError:
            return str(a) < str(b)


class TableView(QTableWidget):
    """Dense, sortable table with configurable columns. See SPEC.md §5.3."""

    record_activated = Signal(object)

    def __init__(self, on_columns_changed: Callable[[list[str]], None], parent=None) -> None:
        super().__init__(parent)
        self._on_columns_changed = on_columns_changed
        self._records: list[WatchRecord] = []
        self._column_keys: list[str] = []
        self._mono_font = QFont(resolve_fonts()["mono"])
        self._mono_font.setPixelSize(SIZE_SM)

        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSortingEnabled(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(44)  # SPEC.md §6: 12px vertical padding per row
        self.horizontalHeader().setSectionsMovable(True)
        self.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.horizontalHeader().customContextMenuRequested.connect(self._show_header_menu)
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)

    def set_columns(self, column_keys: list[str]) -> None:
        self._column_keys = list(column_keys)
        self._render()

    def set_records(self, records: list[WatchRecord]) -> None:
        self._records = records
        self._render()

    def _render(self) -> None:
        self.setSortingEnabled(False)
        self.setColumnCount(len(self._column_keys))
        self.setHorizontalHeaderLabels([COLUMNS_BY_KEY[k].label for k in self._column_keys])
        self.setRowCount(len(self._records))

        for row, record in enumerate(self._records):
            if record.watch is None:
                self._render_error_row(row, record)
            else:
                for col, key in enumerate(self._column_keys):
                    column = COLUMNS_BY_KEY[key]
                    value = column.value(record.watch)
                    item = _SortableItem(column.text(record.watch), value)
                    if is_numeric_value(value):
                        item.setFont(self._mono_font)
                    self.setItem(row, col, item)
                # Sorting reorders rows, so the record for a visual row can only
                # be recovered by data attached to its items, not by row index.
                self.item(row, 0).setData(Qt.ItemDataRole.UserRole, record)

        # Qt's generic default column width truncates longer headers/values
        # ("Water Resistance", full DD.MM.YYYY dates) instead of sizing to
        # what's actually in the table.
        self.resizeColumnsToContents()
        self.setSortingEnabled(True)

    def _render_error_row(self, row: int, record: WatchRecord) -> None:
        item = _SortableItem(f"⚠ Couldn't load {record.slug}", record.slug)
        item.setToolTip(record.load_error or "")
        item.setData(Qt.ItemDataRole.UserRole, record)
        self.setItem(row, 0, item)
        for col in range(1, len(self._column_keys)):
            self.setItem(row, col, _SortableItem(EM_DASH, None))

    def _on_cell_double_clicked(self, row: int, column: int) -> None:
        record = self.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if record is not None and record.watch is not None:
            self.record_activated.emit(record)

    def _show_header_menu(self, pos) -> None:
        menu = QMenu(self)
        for group in GROUP_ORDER:
            submenu = menu.addMenu(group)
            for column in COLUMNS:
                if column.group != group:
                    continue
                action = submenu.addAction(column.label)
                action.setCheckable(True)
                action.setChecked(column.key in self._column_keys)
                action.toggled.connect(lambda checked, k=column.key: self._toggle_column(k, checked))
        menu.exec(self.horizontalHeader().mapToGlobal(pos))

    def _toggle_column(self, key: str, checked: bool) -> None:
        if checked:
            if key in self._column_keys:
                return
            self._column_keys.append(key)
        else:
            if key not in self._column_keys or len(self._column_keys) <= 1:
                return
            self._column_keys.remove(key)
        self._render()
        self._on_columns_changed(self._column_keys)
