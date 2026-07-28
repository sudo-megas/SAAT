from collections.abc import Callable

from PySide6.QtCore import QCoreApplication, QEvent, QLocale, QModelIndex, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
)

from saat.storage import WatchRecord
from saat.ui import theme
from saat.ui.columns import COLUMNS, COLUMNS_BY_KEY, GROUP_ORDER
from saat.ui.formatting import EM_DASH, is_numeric_value
from saat.ui.images import cropped_pixmap, first_image
from saat.ui.theme import SIZE_SM, SIZE_XS, resolve_fonts

_THUMBNAIL_COLUMN_WIDTH = 44
_THUMBNAIL_MARGIN = 6
_THUMBNAIL_RADIUS = 4
_GILT_BAR_WIDTH = 3
_CELL_HORIZONTAL_PADDING = 8
_MIN_SECTION_SIZE = 40
_MAX_SECTION_SIZE = 220  # ceiling for user drag-resize only -- confirmed empirically not to clamp the Stretch name column

# SPEC.md §6, milestone 21b: explicit Interactive widths for the default
# data columns -- deliberately not ResizeToContents anywhere (see
# TableView._apply_column_sizing's docstring). A key absent here (a column
# a user has added via the header menu, or a non-Identity preset) falls
# back to QHeaderView's own defaultSectionSize -- reasonable for a column
# outside the shipped default set, which was never part of the 1100px-
# floor no-scrollbar guarantee to begin with.
#
# diameter_mm/water_resistance_m widened from the milestone brief's
# original 60/92 after a real screenshot (not just the no-scrollbar
# assertions, which can't see this) showed their own English header label
# -- "Diameter", "Water Resistance" -- eliding mid-word at that width.
# Measured via QFontMetrics against the actual header font/weight/letter-
# spacing: "Diameter" needs 64px, "Water Resistance" needs 104px including
# the 16px of QSS padding; widened a further ~6px past each for margin.
# The 840px 1100px-floor budget absorbs +18px total with room to spare
# (name's Stretch remainder drops from ~336px to ~318px).
_COLUMN_WIDTHS = {
    "style": 64,
    "movement_kind": 88,
    "diameter_mm": 70,
    "lug_width_mm": 72,
    "water_resistance_m": 110,
    "acquired_date": 84,
}


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


class _RowPaintingDelegate(QStyledItemDelegate):
    """Paints every cell in TableView. Two jobs QSS alone can't do:

    1. A shared plate-high row wash on hover and the active selection, with
       a 3px gilt left bar on the selected row's first cell -- QSS's ::item
       pseudo-states style one cell at a time, not a row-spanning border
       (SPEC.md §6: no OS blue selection highlight).
    2. Fully custom foreground content for the thumbnail and name columns,
       neither of which is plain text.

    Every other column keeps Qt's own text/font/alignment/eliding via a
    de-selected super().paint() call -- this is what lets the numeric
    right-alignment _render() already sets via item.setTextAlignment() go
    on working unmodified, and lets QSS's QTableWidget::item padding keep
    applying, rather than hand-rolling text layout for every column here
    too. An error row (record.watch is None) always takes this plain-text
    path regardless of column key, since _render_error_row() already fills
    every one of its cells with plain text (the error message, or an
    em-dash) that has nothing to do with the key at that position."""

    def __init__(self, table: "TableView", parent=None) -> None:
        super().__init__(parent)
        self._table = table
        fonts = resolve_fonts()
        self._title_font = QFont(fonts["sans"])
        self._title_font.setPixelSize(SIZE_SM)
        self._title_font.setWeight(QFont.Weight.DemiBold)
        self._subtitle_font = QFont(fonts["sans"])
        self._subtitle_font.setPixelSize(SIZE_XS)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        opt = QStyleOptionViewItem(option)
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        hovered = index.row() == self._table._hover_row
        opt.state = opt.state & ~QStyle.StateFlag.State_Selected & ~QStyle.StateFlag.State_MouseOver

        painter.save()
        if selected or hovered:
            painter.fillRect(opt.rect, QColor(theme.colors().plate_high))
        if selected and index.column() == 0:
            bar = QRect(opt.rect.left(), opt.rect.top(), _GILT_BAR_WIDTH, opt.rect.height())
            painter.fillRect(bar, QColor(theme.colors().gilt))
        painter.restore()

        record = index.siblingAtColumn(0).data(Qt.ItemDataRole.UserRole)
        is_error_row = record is not None and record.watch is None
        key = self._table._column_keys[index.column()]
        if not is_error_row and key == "thumbnail":
            self._paint_thumbnail(painter, opt, index)
        elif not is_error_row and key == "name":
            self._paint_name(painter, opt, record.watch)
        else:
            super().paint(painter, opt, index)

    def _paint_thumbnail(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        path = index.siblingAtColumn(0).data(Qt.ItemDataRole.UserRole + 1)
        rect = option.rect.adjusted(_THUMBNAIL_MARGIN, _THUMBNAIL_MARGIN, -_THUMBNAIL_MARGIN, -_THUMBNAIL_MARGIN)
        if path is None or rect.width() <= 0 or rect.height() <= 0:
            return
        pixmap = cropped_pixmap(path, rect.width(), rect.height())
        if pixmap is None:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(rect), _THUMBNAIL_RADIUS, _THUMBNAIL_RADIUS)
        painter.setClipPath(clip)
        painter.drawPixmap(rect.topLeft(), pixmap)
        painter.restore()

    def _paint_name(self, painter: QPainter, option: QStyleOptionViewItem, watch) -> None:
        rect = option.rect.adjusted(_CELL_HORIZONTAL_PADDING, 0, -_CELL_HORIZONTAL_PADDING, 0)
        painter.save()
        painter.setClipRect(option.rect)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setFont(self._title_font)
        title_metrics = painter.fontMetrics()
        title_text = title_metrics.elidedText(watch.model, Qt.TextElideMode.ElideRight, rect.width())

        # Same optional-parts-joined-with-a-separator shape as cards.py's
        # _build_info() (brand/style meta line) -- reference is the only
        # optional half here, brand is a required field so never empty.
        parts = [watch.brand] + ([watch.reference] if watch.reference else [])
        painter.setFont(self._subtitle_font)
        subtitle_metrics = painter.fontMetrics()
        subtitle_text = subtitle_metrics.elidedText(" · ".join(parts), Qt.TextElideMode.ElideRight, rect.width())

        total_height = title_metrics.height() + subtitle_metrics.height()
        top = rect.top() + max(0, (rect.height() - total_height) // 2)

        painter.setFont(self._title_font)
        painter.setPen(QColor(theme.colors().text))
        painter.drawText(
            QRect(rect.left(), top, rect.width(), title_metrics.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title_text,
        )
        painter.setFont(self._subtitle_font)
        painter.setPen(QColor(theme.colors().text_muted))
        painter.drawText(
            QRect(rect.left(), top + title_metrics.height(), rect.width(), subtitle_metrics.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, subtitle_text,
        )
        painter.restore()


class TableView(QTableWidget):
    """Dense, sortable table with configurable columns. See SPEC.md §5.3.
    Multi-select feeds the compare view (§5.4) — up to four rows selected at
    once, tracked by slug rather than row index since sorting reorders rows."""

    record_activated = Signal(object)
    selection_changed = Signal(set)  # set[str] of slugs

    def __init__(self, on_columns_changed: Callable[[list[str]], None], parent=None) -> None:
        super().__init__(parent)
        self._on_columns_changed = on_columns_changed
        self._records: list[WatchRecord] = []
        self._column_keys: list[str] = []
        self._hover_row = -1
        self._mono_font = QFont(resolve_fonts()["mono"])
        self._mono_font.setPixelSize(SIZE_SM)

        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSortingEnabled(True)
        self.setShowGrid(False)  # SPEC.md §6: rows separate by height/whitespace only
        self.setMouseTracking(True)  # drives _hover_row for _RowPaintingDelegate's row wash
        self.setItemDelegate(_RowPaintingDelegate(self))
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(44)  # SPEC.md §6: 12px vertical padding per row
        self.horizontalHeader().setSectionsMovable(True)
        # Qt's own default header painting hard-clips overflowing text
        # mid-word with no "…" -- confirmed by screenshot, fixed by setting
        # this explicitly rather than assuming QHeaderView's default
        # (which turned out not to be this).
        self.horizontalHeader().setTextElideMode(Qt.TextElideMode.ElideRight)
        self.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.horizontalHeader().customContextMenuRequested.connect(self._show_header_menu)
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.itemSelectionChanged.connect(lambda: self.selection_changed.emit(self.selected_slugs()))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        row = self.indexAt(event.pos()).row()  # -1 for an invalid index, Qt's own convention
        if row != self._hover_row:
            self._hover_row = row
            self.viewport().update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        if self._hover_row != -1:
            self._hover_row = -1
            self.viewport().update()
        super().leaveEvent(event)

    def set_columns(self, column_keys: list[str]) -> None:
        self._column_keys = list(column_keys)
        self._render()

    def set_records(self, records: list[WatchRecord]) -> None:
        self._records = records
        self._render()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            # _render() already re-evaluates every QCoreApplication.translate()
            # call fresh (header labels, cell text via Column.text(), the
            # error-row message) -- it's already a full rebuild-from-current-
            # state function, called after every other change too, so a
            # language switch just needs to trigger the same call. Harmless
            # if CollectionView's own changeEvent also triggers this
            # indirectly via _recompute() -> set_records() -- redundant, not
            # wrong, and this way TableView is correct on its own regardless
            # of what its container does.
            self._render()
        super().changeEvent(event)

    def _render(self) -> None:
        self.setSortingEnabled(False)
        self._hover_row = -1  # rows are rebuilt wholesale below -- a stale index would tint the wrong row
        self.setColumnCount(len(self._column_keys))
        locale = QLocale()  # bare QLocale(), never QLocale.system() -- see minute_track.py
        for col, key in enumerate(self._column_keys):
            # thumbnail is a 44px icon-only column -- even "Photo" doesn't
            # fit legibly there, and the images themselves need no label.
            # Still individually named ("Photo") in the header menu, via
            # Column.label directly -- only the on-table header text blanks.
            label = "" if key == "thumbnail" else locale.toUpper(QCoreApplication.translate("Columns", COLUMNS_BY_KEY[key].label))
            item = QTableWidgetItem(label)
            item.setToolTip(label)
            self.setHorizontalHeaderItem(col, item)
        self._apply_column_sizing()
        self.setRowCount(len(self._records))

        # A directory scan (list_images(), inside first_image()) is real
        # I/O -- resolved once per row here, stashed on column 0's item
        # (alongside the record itself), never inside the delegate's
        # paint(). Skipped entirely when the thumbnail column isn't even
        # part of this render.
        needs_thumbnail_path = "thumbnail" in self._column_keys
        for row, record in enumerate(self._records):
            if record.watch is None:
                self._render_error_row(row, record)
                continue
            for col, key in enumerate(self._column_keys):
                column = COLUMNS_BY_KEY[key]
                value = column.value(record.watch)
                item = _SortableItem(column.text(record.watch), value)
                if is_numeric_value(value):
                    item.setFont(self._mono_font)
                    # SPEC.md §6: tabular figures are for scanning a
                    # column at a glance -- that only works right-aligned,
                    # so digits (and em-dash placeholders) land on a
                    # shared trailing edge instead of a ragged one.
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if key != "thumbnail":  # no text of its own -- the delegate paints an image, not a cell string
                    item.setToolTip(item.text())
                self.setItem(row, col, item)
            # Sorting reorders rows, so the record for a visual row can only
            # be recovered by data attached to its items, not by row index.
            self.item(row, 0).setData(Qt.ItemDataRole.UserRole, record)
            if needs_thumbnail_path:
                self.item(row, 0).setData(Qt.ItemDataRole.UserRole + 1, first_image(record))

        self.setSortingEnabled(True)

    def _apply_column_sizing(self) -> None:
        """Interactive everywhere except the Stretch name column and the
        Fixed thumbnail one -- deliberately never ResizeToContents, whose
        natural width is driven by header-label length, and real translated
        strings move unpredictably per language (SPEC.md §5: no horizontal
        scrollbar at the 1100px floor, in any shipped language). Every
        column instead gets an explicit width (falling back to
        QHeaderView's own defaultSectionSize for a key with no entry in
        _COLUMN_WIDTHS); Qt.ElideRight plus each item's own tooltip absorb
        whatever the fixed width doesn't fit."""
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(_MIN_SECTION_SIZE)
        header.setMaximumSectionSize(_MAX_SECTION_SIZE)
        # QHeaderView's own default is centred, which clips a long label
        # (e.g. "Diameter"/"Water Resistance") symmetrically on BOTH edges
        # once it overflows a narrow Interactive column -- left-aligned
        # means the same overflow only ever clips the trailing edge,
        # matching Qt.ElideRight's own direction everywhere else in this
        # table. Confirmed by screenshot: centred clipped "Diameter" to
        # "IAMETER" at the 60px width from _COLUMN_WIDTHS.
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for col, key in enumerate(self._column_keys):
            if key == "thumbnail":
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
                header.resizeSection(col, _THUMBNAIL_COLUMN_WIDTH)
            elif key == "name":
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
                width = _COLUMN_WIDTHS.get(key)
                if width is not None:
                    header.resizeSection(col, width)

    def _render_error_row(self, row: int, record: WatchRecord) -> None:
        item = _SortableItem(self.tr("⚠ Couldn't load {slug}").format(slug=record.slug), record.slug)
        item.setToolTip(record.load_error or "")
        item.setData(Qt.ItemDataRole.UserRole, record)
        self.setItem(row, 0, item)
        for col in range(1, len(self._column_keys)):
            self.setItem(row, col, _SortableItem(EM_DASH, None))

    def _on_cell_double_clicked(self, row: int, column: int) -> None:
        record = self.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if record is not None and record.watch is not None:
            self.record_activated.emit(record)

    def selected_slugs(self) -> set[str]:
        slugs = set()
        for index in self.selectionModel().selectedRows():
            item = self.item(index.row(), 0)
            record = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
            if record is not None:
                slugs.add(record.slug)
        return slugs

    def set_selected_slugs(self, slugs: set[str]) -> None:
        """Programmatic sync (from a grid checkbox, or re-selecting after a
        _render() rebuild) — blocked so it doesn't loop back through
        selection_changed as if the user had clicked in the table."""
        self.blockSignals(True)
        try:
            self.clearSelection()
            for row in range(self.rowCount()):
                item = self.item(row, 0)
                record = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
                if record is not None and record.slug in slugs:
                    self.selectRow(row)
        finally:
            self.blockSignals(False)

    def _show_header_menu(self, pos) -> None:
        menu = QMenu(self)
        for group in GROUP_ORDER:
            submenu = menu.addMenu(QCoreApplication.translate("Columns", group))
            for column in COLUMNS:
                if column.group != group:
                    continue
                action = submenu.addAction(QCoreApplication.translate("Columns", column.label))
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
