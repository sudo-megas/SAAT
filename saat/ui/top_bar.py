from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QPushButton, QWidget

from saat.ui.columns import COLUMNS_BY_KEY, GROUP_ORDER, SORT_OPTIONS

VIEW_GRID = "grid"
VIEW_TABLE = "table"
VIEW_CALENDAR = "calendar"
PRESET_DEFAULT = "Default"


class TopBar(QWidget):
    """Search, view toggle, sort, column presets, and the one primary-weight
    control in the app. See SPEC.md §5.1."""

    view_changed = Signal(str)
    sort_changed = Signal(str)
    preset_changed = Signal(str)
    search_changed = Signal(str)
    add_watch_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "top-bar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._search_field = QLineEdit()
        self._search_field.setPlaceholderText("Search brand, model, reference, caliber, tags…")
        self._search_field.setMinimumWidth(240)
        self._search_field.textChanged.connect(self.search_changed.emit)

        self._grid_button = QPushButton("Grid")
        self._grid_button.setCheckable(True)
        self._table_button = QPushButton("Table")
        self._table_button.setCheckable(True)
        self._calendar_button = QPushButton("Calendar")
        self._calendar_button.setCheckable(True)
        self._grid_button.clicked.connect(lambda: self._set_view(VIEW_GRID))
        self._table_button.clicked.connect(lambda: self._set_view(VIEW_TABLE))
        self._calendar_button.clicked.connect(lambda: self._set_view(VIEW_CALENDAR))

        self._sort_combo = QComboBox()
        for key in SORT_OPTIONS:
            self._sort_combo.addItem(f"Sort: {COLUMNS_BY_KEY[key].label}", key)
        self._sort_combo.currentIndexChanged.connect(
            lambda i: self.sort_changed.emit(self._sort_combo.itemData(i))
        )

        self._preset_combo = QComboBox()
        self._preset_combo.addItem(PRESET_DEFAULT)
        for group in GROUP_ORDER:
            self._preset_combo.addItem(group)
        self._preset_combo.currentTextChanged.connect(self.preset_changed.emit)

        add_button = QPushButton("Add watch")
        add_button.setProperty("variant", "primary")
        add_button.clicked.connect(self.add_watch_requested.emit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(12)
        layout.addWidget(self._search_field)
        layout.addSpacing(12)
        layout.addWidget(self._grid_button)
        layout.addWidget(self._table_button)
        layout.addWidget(self._calendar_button)
        layout.addSpacing(12)
        layout.addWidget(self._sort_combo)
        layout.addWidget(self._preset_combo)
        layout.addStretch()
        layout.addWidget(add_button)

        self._set_view(VIEW_GRID)

    def set_view(self, view: str) -> None:
        self._set_view(view)

    def search_text(self) -> str:
        return self._search_field.text()

    def _set_view(self, view: str) -> None:
        self._grid_button.setChecked(view == VIEW_GRID)
        self._table_button.setChecked(view == VIEW_TABLE)
        self._calendar_button.setChecked(view == VIEW_CALENDAR)
        self._preset_combo.setEnabled(view == VIEW_TABLE)
        # Sort and search are meaningless against a date-indexed view — the
        # calendar always shows the whole collection's wear history.
        self._sort_combo.setEnabled(view != VIEW_CALENDAR)
        self._search_field.setEnabled(view != VIEW_CALENDAR)
        self.view_changed.emit(view)
