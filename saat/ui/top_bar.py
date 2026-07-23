import math

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPainterPath, QPen
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QPushButton, QWidget

from saat.ui import theme
from saat.ui.columns import COLUMNS_BY_KEY, GROUP_ORDER, SORT_OPTIONS
from saat.ui.compare import MIN_COMPARE

VIEW_GRID = "grid"
VIEW_TABLE = "table"
VIEW_CALENDAR = "calendar"
PRESET_DEFAULT = "Default"

_TOGGLE_SIZE = 28


class _ThemeToggle(QWidget):
    """Sun/moon glyph, hand-drawn to match the app's line weight rather than a
    font icon — SPEC.md §6 is explicit on that point. Shows the mode a click
    switches *to*: a sun while dark is active, a moon while light is active.
    Reads theme.colors()/current_mode() fresh every paint, so it's always
    correct after a toggle or after TopBar gets rebuilt from scratch."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(_TOGGLE_SIZE, _TOGGLE_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(theme.colors().text_muted)
        cx, cy = self.width() / 2, self.height() / 2

        if theme.current_mode() == theme.MODE_DARK:
            r = 5.0
            painter.setPen(QPen(color, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), r, r)
            for i in range(8):
                angle = i * math.pi / 4
                inner, outer = r + 3, r + 7
                painter.drawLine(
                    QPointF(cx + math.cos(angle) * inner, cy + math.sin(angle) * inner),
                    QPointF(cx + math.cos(angle) * outer, cy + math.sin(angle) * outer),
                )
        else:
            r = 7.0
            full = QPainterPath()
            full.addEllipse(QPointF(cx, cy), r, r)
            bite = QPainterPath()
            bite.addEllipse(QPointF(cx + r * 0.6, cy - r * 0.3), r, r)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawPath(full.subtracted(bite))

        painter.end()


class TopBar(QWidget):
    """Search, view toggle, sort, column presets, and the one primary-weight
    control in the app. See SPEC.md §5.1."""

    view_changed = Signal(str)
    sort_changed = Signal(str)
    preset_changed = Signal(str)
    search_changed = Signal(str)
    add_watch_requested = Signal()
    theme_toggle_requested = Signal()
    compare_requested = Signal()

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

        self._compare_button = QPushButton()
        self._compare_button.clicked.connect(self.compare_requested.emit)
        self._compare_button.setVisible(False)

        self._theme_toggle = _ThemeToggle()
        self._theme_toggle.clicked.connect(self.theme_toggle_requested.emit)

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
        layout.addWidget(self._compare_button)
        layout.addWidget(add_button)
        layout.addWidget(self._theme_toggle)

        self._set_view(VIEW_GRID)

    def set_compare_count(self, count: int) -> None:
        """SPEC.md §5.4: 'Select two to four watches.' Hidden below the
        minimum rather than shown disabled — a conditional action, not a
        permanent control."""
        self._compare_button.setText(f"Compare ({count})")
        self._compare_button.setVisible(count >= MIN_COMPARE)

    def set_view(self, view: str) -> None:
        self._set_view(view)

    def search_text(self) -> str:
        return self._search_field.text()

    def focus_search(self) -> None:
        self._search_field.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._search_field.selectAll()

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
