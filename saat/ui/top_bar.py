import weakref

from PySide6.QtCore import QCoreApplication, QEvent, Qt, Signal
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
    compare_requested = Signal()
    export_requested = Signal()
    pick_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "top-bar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._scope = SCOPE_COLLECTION
        self._sort_descending = False

        self._collection_button = QPushButton(self.tr("Collection"))
        self._collection_button.setCheckable(True)
        icons.set_checkable_icon(self._collection_button, "collection")
        self._wishlist_button = QPushButton(self.tr("Wishlist"))
        self._wishlist_button.setCheckable(True)
        icons.set_checkable_icon(self._wishlist_button, "star")
        self._collection_button.clicked.connect(lambda: self._set_scope(SCOPE_COLLECTION))
        self._wishlist_button.clicked.connect(lambda: self._set_scope(SCOPE_WISHLIST))

        self._search_field = QLineEdit()
        self._search_field.setPlaceholderText(self.tr("Search brand, model, reference, caliber, tags…"))
        self._search_field.setMinimumWidth(120)
        search_action = self._search_field.addAction(
            icons.icon("search", theme.colors().text_muted), QLineEdit.ActionPosition.LeadingPosition
        )

        # Weakref for the same reason icons.set_icon() uses one: the hook
        # hangs on the field, the action is parented to the field, so a
        # strong capture would close the loop into a reference cycle.
        action_ref = weakref.ref(search_action)

        def _refresh_search_icon() -> None:
            action = action_ref()
            if action is not None:
                action.setIcon(icons.icon("search", theme.colors().text_muted))

        # QAction isn't a QWidget, so apply_theme()'s sweep can't reach it
        # directly -- hang the hook on the field itself, which the sweep does visit.
        self._search_field._refresh_icon = _refresh_search_icon
        self._search_field.textChanged.connect(self.search_changed.emit)

        self._grid_button = QPushButton(self.tr("Grid"))
        self._grid_button.setCheckable(True)
        icons.set_checkable_icon(self._grid_button, "grid")
        self._table_button = QPushButton(self.tr("Table"))
        self._table_button.setCheckable(True)
        icons.set_checkable_icon(self._table_button, "table")
        self._calendar_button = QPushButton(self.tr("Calendar"))
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
        self._sort_direction_button.setToolTip(self.tr("Sort ascending"))
        self._sort_direction_button.clicked.connect(self._toggle_sort_direction)
        self._refresh_sort_direction_icon()

        self._preset_combo = QComboBox()
        # Milestone 21: text is the translated label, itemData is the
        # canonical value -- same split as form_fields.py's enum combos.
        # PRESET_DEFAULT/GROUP_ORDER's values are what collection_view.py's
        # _on_preset_changed() compares against and looks COLUMN_PRESETS up
        # by; the old currentTextChanged.connect(...emit) emitted display
        # text directly, which would have silently broken that lookup the
        # moment this combo's items became translated (every non-English
        # preset selection would have quietly fallen back to the default
        # columns instead of applying the chosen preset).
        self._rebuild_preset_combo()
        self._preset_combo.currentIndexChanged.connect(
            lambda i: self.preset_changed.emit(self._preset_combo.itemData(i))
        )

        self._add_button = QPushButton(self.tr("Add watch"))
        self._add_button.setProperty("variant", "primary")
        icons.set_icon(self._add_button, "add", color_role="plate")
        self._add_button.clicked.connect(self.add_watch_requested.emit)
        self._compare_count = 0

        self._compare_button = QPushButton()
        icons.set_icon(self._compare_button, "compare")
        self._compare_button.clicked.connect(self.compare_requested.emit)
        self._compare_button.setVisible(False)

        self._export_button = QPushButton()
        self._export_button.setToolTip(self.tr("Export to PDF (Ctrl+P)"))
        icons.set_icon(self._export_button, "export")
        self._export_button.clicked.connect(self.export_requested.emit)

        self._pick_button = QPushButton()
        self._pick_button.setToolTip(self.tr("Pick a watch for today"))
        icons.set_icon(self._pick_button, "pick")
        self._pick_button.clicked.connect(self.pick_requested.emit)

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
        row2.addWidget(self._add_button)
        row2.addWidget(self._pick_button)
        row2.addWidget(self._export_button)

        outer.addLayout(row1)
        outer.addLayout(row2)

        self._set_view(VIEW_GRID)
        self._set_scope(SCOPE_COLLECTION)

    def set_compare_count(self, count: int) -> None:
        """SPEC.md §5.4: 'Select two to four watches.' Hidden below the
        minimum rather than shown disabled — a conditional action, not a
        permanent control."""
        self._compare_count = count
        self._compare_button.setText(self.tr("Compare ({count})").format(count=count))
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
        self._sort_direction_button.setToolTip(self.tr("Sort descending") if self._sort_descending else self.tr("Sort ascending"))

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
        # offer genuinely different option lists (SPEC.md §5.12). Both
        # lists lead with "brand", so this also resets sort to the default
        # on scope change -- unlike a language change (_retranslate()),
        # which rebuilds the same list of keys and must preserve whichever
        # one is currently selected.
        self._rebuild_sort_combo(preserve_selection=False)
        self._sort_descending = False
        self._refresh_sort_direction_icon()

        self.scope_changed.emit(scope)

    def _rebuild_sort_combo(self, preserve_selection: bool) -> None:
        # Signals are blocked so a mid-rebuild currentIndexChanged can't
        # fire against a half-populated combo and trigger a recompute
        # against stale state -- callers read current_sort_key() explicitly
        # once this returns, rather than relying on a signal fired here.
        current_key = self.current_sort_key() if preserve_selection else None
        is_wishlist = self._scope == SCOPE_WISHLIST
        self._sort_combo.blockSignals(True)
        self._sort_combo.clear()
        for key in WISHLIST_SORT_OPTIONS if is_wishlist else SORT_OPTIONS:
            label = QCoreApplication.translate("Columns", COLUMNS_BY_KEY[key].label)
            self._sort_combo.addItem(self.tr("Sort: {label}").format(label=label), key)
        if current_key is not None:
            index = self._sort_combo.findData(current_key)
            if index >= 0:
                self._sort_combo.setCurrentIndex(index)
        self._sort_combo.blockSignals(False)

    def _rebuild_preset_combo(self) -> None:
        current = self._preset_combo.itemData(self._preset_combo.currentIndex()) if self._preset_combo.count() else PRESET_DEFAULT
        self._preset_combo.blockSignals(True)
        self._preset_combo.clear()
        self._preset_combo.addItem(self.tr("Default"), PRESET_DEFAULT)
        for group in GROUP_ORDER:
            self._preset_combo.addItem(QCoreApplication.translate("Columns", group), group)
        index = self._preset_combo.findData(current)
        self._preset_combo.setCurrentIndex(index if index >= 0 else 0)
        self._preset_combo.blockSignals(False)

    def _retranslate(self) -> None:
        self._collection_button.setText(self.tr("Collection"))
        self._wishlist_button.setText(self.tr("Wishlist"))
        self._search_field.setPlaceholderText(self.tr("Search brand, model, reference, caliber, tags…"))
        self._grid_button.setText(self.tr("Grid"))
        self._table_button.setText(self.tr("Table"))
        self._calendar_button.setText(self.tr("Calendar"))
        self._refresh_sort_direction_icon()
        self._rebuild_preset_combo()
        self._rebuild_sort_combo(preserve_selection=True)
        self._add_button.setText(self.tr("Add watch"))
        self.set_compare_count(self._compare_count)
        self._export_button.setToolTip(self.tr("Export to PDF (Ctrl+P)"))
        self._pick_button.setToolTip(self.tr("Pick a watch for today"))

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
