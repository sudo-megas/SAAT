import math

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPainterPath, QPen
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget

from saat.ui import icons, theme
from saat.ui.columns import COLUMNS_BY_KEY, GROUP_ORDER, SORT_OPTIONS, WISHLIST_SORT_OPTIONS
from saat.ui.compare import MIN_COMPARE

SORT_ASCENDING = "asc"
SORT_DESCENDING = "desc"

VIEW_GRID = "grid"
VIEW_TABLE = "table"
VIEW_CALENDAR = "calendar"
PRESET_DEFAULT = "Default"

# SPEC.md §5.12: scope is orthogonal to view — Collection is everything
# except Wishlist-status watches, Wishlist is only Wishlist-status watches.
SCOPE_COLLECTION = "collection"
SCOPE_WISHLIST = "wishlist"

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
    scope_changed = Signal(str)
    sort_changed = Signal(str)
    sort_direction_changed = Signal(str)
    preset_changed = Signal(str)
    search_changed = Signal(str)
    add_watch_requested = Signal()
    theme_toggle_requested = Signal()
    compare_requested = Signal()
    export_requested = Signal()
    pick_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "top-bar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._scope = SCOPE_COLLECTION
        self._sort_descending = False

        self._collection_button = QPushButton("Collection")
        self._collection_button.setCheckable(True)
        icons.set_checkable_icon(self._collection_button, "collection")
        self._wishlist_button = QPushButton("Wishlist")
        self._wishlist_button.setCheckable(True)
        icons.set_checkable_icon(self._wishlist_button, "star")
        self._collection_button.clicked.connect(lambda: self._set_scope(SCOPE_COLLECTION))
        self._wishlist_button.clicked.connect(lambda: self._set_scope(SCOPE_WISHLIST))

        self._search_field = QLineEdit()
        self._search_field.setPlaceholderText("Search brand, model, reference, caliber, tags…")
        self._search_field.setMinimumWidth(120)
        self._search_field.addAction(
            icons.icon("search", theme.colors().text_muted), QLineEdit.ActionPosition.LeadingPosition
        )
        self._search_field.textChanged.connect(self.search_changed.emit)

        self._grid_button = QPushButton("Grid")
        self._grid_button.setCheckable(True)
        icons.set_checkable_icon(self._grid_button, "grid")
        self._table_button = QPushButton("Table")
        self._table_button.setCheckable(True)
        icons.set_checkable_icon(self._table_button, "table")
        self._calendar_button = QPushButton("Calendar")
        self._calendar_button.setCheckable(True)
        icons.set_checkable_icon(self._calendar_button, "calendar")
        self._grid_button.clicked.connect(lambda: self._set_view(VIEW_GRID))
        self._table_button.clicked.connect(lambda: self._set_view(VIEW_TABLE))
        self._calendar_button.clicked.connect(lambda: self._set_view(VIEW_CALENDAR))

        self._sort_combo = QComboBox()
        self._sort_combo.currentIndexChanged.connect(
            lambda i: self.sort_changed.emit(self._sort_combo.itemData(i))
        )

        self._sort_direction_button = QPushButton()
        self._sort_direction_button.setProperty("variant", "link")
        self._sort_direction_button.setToolTip("Sort ascending")
        self._sort_direction_button.clicked.connect(self._toggle_sort_direction)
        self._refresh_sort_direction_icon()

        self._preset_combo = QComboBox()
        self._preset_combo.addItem(PRESET_DEFAULT)
        for group in GROUP_ORDER:
            self._preset_combo.addItem(group)
        self._preset_combo.currentTextChanged.connect(self.preset_changed.emit)

        add_button = QPushButton("Add watch")
        add_button.setProperty("variant", "primary")
        icons.set_icon(add_button, "add", color_role="plate")
        add_button.clicked.connect(self.add_watch_requested.emit)

        self._compare_button = QPushButton()
        icons.set_icon(self._compare_button, "compare")
        self._compare_button.clicked.connect(self.compare_requested.emit)
        self._compare_button.setVisible(False)

        self._export_button = QPushButton()
        self._export_button.setToolTip("Export to PDF (Ctrl+P)")
        icons.set_icon(self._export_button, "export")
        self._export_button.clicked.connect(self.export_requested.emit)

        self._pick_button = QPushButton()
        self._pick_button.setToolTip("Pick a watch for today")
        icons.set_icon(self._pick_button, "pick")
        self._pick_button.clicked.connect(self.pick_requested.emit)

        self._theme_toggle = _ThemeToggle()
        self._theme_toggle.clicked.connect(self.theme_toggle_requested.emit)

        # Two rows, not one -- SPEC.md's "minimum 1100x700" only holds if the
        # bar actually fits it. A single row cramming scope + search + view
        # toggle + sort + presets + every action button overflowed that
        # floor by hundreds of pixels once milestones 19 and 20 added their
        # own buttons on top of what was already there. Row 1 answers "what
        # subset of the collection am I looking at, and how"; row 2 answers
        # "how is it ordered, and what can I do."
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 12, 24, 12)
        outer.setSpacing(8)

        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(12)
        row1.addWidget(self._collection_button)
        row1.addWidget(self._wishlist_button)
        row1.addSpacing(12)
        row1.addWidget(self._search_field, 1)
        row1.addSpacing(12)
        row1.addWidget(self._grid_button)
        row1.addWidget(self._table_button)
        row1.addWidget(self._calendar_button)

        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(12)
        row2.addWidget(self._sort_combo)
        row2.addWidget(self._sort_direction_button)
        row2.addWidget(self._preset_combo)
        row2.addStretch()
        row2.addWidget(self._compare_button)
        row2.addWidget(add_button)
        row2.addWidget(self._pick_button)
        row2.addWidget(self._export_button)
        row2.addWidget(self._theme_toggle)

        outer.addLayout(row1)
        outer.addLayout(row2)

        self._set_view(VIEW_GRID)
        self._set_scope(SCOPE_COLLECTION)

    def set_compare_count(self, count: int) -> None:
        """SPEC.md §5.4: 'Select two to four watches.' Hidden below the
        minimum rather than shown disabled — a conditional action, not a
        permanent control."""
        self._compare_button.setText(f"Compare ({count})")
        self._compare_button.setVisible(count >= MIN_COMPARE)

    def set_export_enabled(self, enabled: bool) -> None:
        """Disabled for the duration of a PDF render (main_window.py) --
        export_pdf() is synchronous, so this mostly guards against a
        second click queued up right as the first finishes, rather than
        one arriving mid-render while the event loop is blocked anyway."""
        self._export_button.setEnabled(enabled)

    def set_view(self, view: str) -> None:
        self._set_view(view)

    def set_scope(self, scope: str) -> None:
        self._set_scope(scope)

    def scope(self) -> str:
        return self._scope

    def current_sort_key(self) -> str:
        return self._sort_combo.itemData(self._sort_combo.currentIndex())

    def current_sort_descending(self) -> bool:
        return self._sort_descending

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
        self._sort_direction_button.setEnabled(view != VIEW_CALENDAR)
        self._search_field.setEnabled(view != VIEW_CALENDAR)
        self.view_changed.emit(view)

    def _toggle_sort_direction(self) -> None:
        self._sort_descending = not self._sort_descending
        self._refresh_sort_direction_icon()
        self.sort_direction_changed.emit(SORT_DESCENDING if self._sort_descending else SORT_ASCENDING)

    def _refresh_sort_direction_icon(self) -> None:
        name = "sort-desc" if self._sort_descending else "sort-asc"
        icons.set_icon(self._sort_direction_button, name)
        self._sort_direction_button.setToolTip("Sort descending" if self._sort_descending else "Sort ascending")

    def _set_scope(self, scope: str) -> None:
        self._scope = scope
        self._collection_button.setChecked(scope == SCOPE_COLLECTION)
        self._wishlist_button.setChecked(scope == SCOPE_WISHLIST)

        is_wishlist = scope == SCOPE_WISHLIST
        # SPEC.md §5.12: Calendar/Stats are Collection-only, hidden (not
        # disabled) in Wishlist scope. Fall back to Grid rather than leaving
        # a hidden view active if it was the current one.
        if is_wishlist and self._calendar_button.isChecked():
            self._set_view(VIEW_GRID)
        self._calendar_button.setVisible(not is_wishlist)
        # Milestone 20: the picker only ever draws from Owned watches (§5.12)
        # -- meaningless in Wishlist scope, so hidden the same way Calendar is.
        self._pick_button.setVisible(not is_wishlist)

        # Rebuilt rather than filtered in place — Wishlist and Collection
        # offer genuinely different option lists (SPEC.md §5.12). Signals
        # are blocked so a mid-rebuild currentIndexChanged can't race
        # scope_changed below and trigger a recompute against the old
        # scope; the listener reads current_sort_key() explicitly from its
        # scope_changed handler instead. Both lists lead with "brand", so
        # this also resets sort to the default on scope change.
        self._sort_combo.blockSignals(True)
        self._sort_combo.clear()
        for key in WISHLIST_SORT_OPTIONS if is_wishlist else SORT_OPTIONS:
            self._sort_combo.addItem(f"Sort: {COLUMNS_BY_KEY[key].label}", key)
        self._sort_combo.blockSignals(False)
        self._sort_descending = False
        self._refresh_sort_direction_icon()

        self.scope_changed.emit(scope)
