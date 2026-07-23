from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QScrollArea, QWidget

from saat.storage import WatchRecord
from saat.ui.cards import CARD_WIDTH, WatchCard
from saat.ui.theme import CARD_PADDING, PAGE_MARGIN


class GridView(QScrollArea):
    """Reflowing card grid. See SPEC.md §5.2 — four to five cards per row on a
    1440p display, not capped to a fixed content width."""

    record_activated = Signal(object)
    compare_toggled = Signal(object, bool)
    wore_today_requested = Signal(object)

    _ARROW_DELTA_KEYS = (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._container = QWidget()
        self._layout = QGridLayout(self._container)
        self._layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        self._layout.setSpacing(CARD_PADDING)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setWidget(self._container)

        self._cards: list[WatchCard] = []
        self._columns = 1
        self._focus_index: int | None = None

    def set_records(self, records: list[WatchRecord], compare_selection: frozenset[str] = frozenset()) -> None:
        for card in self._cards:
            self._layout.removeWidget(card)
            card.deleteLater()
        self._cards = [WatchCard(record, record.slug in compare_selection) for record in records]
        for card in self._cards:
            card.activated.connect(self.record_activated.emit)
            card.compare_toggled.connect(self.compare_toggled.emit)
            card.wore_today_requested.connect(self.wore_today_requested.emit)
        # Cards are destroyed and rebuilt on every search/sort/facet/compare
        # change — a stale index (or worse, a widget reference) from before
        # the rebuild would point at deleted objects, so the keyboard cursor
        # always resets rather than trying to track the same watch across it.
        self._focus_index = None
        self._relayout()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout()

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        if self._focus_index is None and self._cards:
            self._focus_index = 0
        self._paint_focus_ring()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self._paint_focus_ring()

    def keyPressEvent(self, event) -> None:
        if not self._cards:
            super().keyPressEvent(event)
            return

        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            index = self._focus_index if self._focus_index is not None else 0
            record = self._cards[index].record
            if record is not None:
                self.record_activated.emit(record)
            return

        if key in self._ARROW_DELTA_KEYS:
            delta = {
                Qt.Key.Key_Left: -1,
                Qt.Key.Key_Right: 1,
                Qt.Key.Key_Up: -self._columns,
                Qt.Key.Key_Down: self._columns,
            }[key]
            current = self._focus_index if self._focus_index is not None else 0
            candidate = current + delta
            if 0 <= candidate < len(self._cards):
                self._focus_index = candidate
                self._paint_focus_ring()
                self.ensureWidgetVisible(self._cards[candidate])
            return

        super().keyPressEvent(event)

    def _paint_focus_ring(self) -> None:
        """Only shows the ring while the grid itself actually has keyboard
        focus — otherwise every render would carry a permanent gilt outline
        around card 0 even before the user ever tabbed or clicked in."""
        has_focus = self.hasFocus()
        for index, card in enumerate(self._cards):
            card.set_cursor_focused(has_focus and index == self._focus_index)

    def _relayout(self) -> None:
        if not self._cards:
            return
        for card in self._cards:
            self._layout.removeWidget(card)

        available = max(self.viewport().width() - 2 * PAGE_MARGIN, CARD_WIDTH)
        column_width = CARD_WIDTH + CARD_PADDING
        self._columns = max(1, (available + CARD_PADDING) // column_width)

        for index, card in enumerate(self._cards):
            row, col = divmod(index, self._columns)
            self._layout.addWidget(card, row, col)
