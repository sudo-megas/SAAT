from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QScrollArea, QWidget

from saat.storage import WatchRecord
from saat.ui.cards import DEFAULT_CARD_WIDTH, WatchCard
from saat.ui.flow_layout import FlowLayout
from saat.ui.theme import CARD_PADDING, PAGE_MARGIN

# SPEC.md §5.2, milestone 21b: a card renders up to this many px above
# DEFAULT_CARD_WIDTH to exactly fill a row with no leftover gap -- the
# provable bound behind "card size stays visually consistent, column
# count differs" (rather than the old fixed-columns/scaled-cards shape,
# where a wide screen got fewer, bigger cards instead of more columns of
# the same size).
MAX_FILL_STRETCH = 12


class GridView(QScrollArea):
    """Reflowing card grid. See SPEC.md §5.2 — target-width reflow (milestone
    21b): a wider screen gets more columns of roughly DEFAULT_CARD_WIDTH each,
    not fewer, bigger cards, and no fixed content-width cap."""

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
        self._layout = FlowLayout(self._container, margin=PAGE_MARGIN, spacing=CARD_PADDING)
        self.setWidget(self._container)

        self._cards: list[WatchCard] = []
        self._columns = 1
        self._focus_index: int | None = None

    def set_records(self, records: list[WatchRecord], compare_selection: frozenset[str] = frozenset()) -> None:
        for card in self._cards:
            self._layout.removeWidget(card)
            # removeWidget() only detaches the card from the layout, not
            # from the screen -- it stays a visible child of _container at
            # its old geometry until this deferred delete actually runs.
            card.hide()
            card.deleteLater()
        # Constructed directly at the current computed width (rather than
        # WatchCard's own DEFAULT_CARD_WIDTH default, corrected a moment
        # later by _relayout()'s set_render_width() calls below) -- avoids
        # decoding every photo once at the wrong size just to immediately
        # redo it at the right one.
        render_width = self._compute_render_width()
        self._cards = [
            WatchCard(record, record.slug in compare_selection, render_width=render_width) for record in records
        ]
        for card in self._cards:
            card.activated.connect(self.record_activated.emit)
            card.compare_toggled.connect(self.compare_toggled.emit)
            card.wore_today_requested.connect(self.wore_today_requested.emit)
            self._layout.addWidget(card)
            # A widget constructed with no parent (WatchCard(record, ...)
            # above) and only reparented afterward via addWidget() stays
            # QWidget-hidden until explicitly shown, even once its new
            # parent is itself visible -- Qt does not cascade visibility
            # onto a widget reparented after the fact. A hidden widget's
            # QWidgetItem.sizeHint() reads as (0, 0) regardless of its own
            # real sizeHint(), which silently breaks FlowLayout's wrap
            # decision (every "card" looks zero-width, so nothing ever
            # wraps) the first time _relayout() runs against freshly
            # (re)built cards -- confirmed directly: card.isHidden() was
            # still True immediately after addWidget() without this.
            card.show()
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

    def _compute_render_width(self) -> int:
        """Target-width reflow (SPEC.md §5.2, milestone 21b): a wider
        screen gets more columns of roughly DEFAULT_CARD_WIDTH, not fewer
        bigger cards -- the inverse of the old fixed-columns/scaled-cards
        formula this replaces. columns is picked first (how many
        DEFAULT_CARD_WIDTH-ish cards fit), then the leftover space is
        divided evenly across them and capped at
        DEFAULT_CARD_WIDTH + MAX_FILL_STRETCH, so a card never renders
        more than that many px above target -- the provable bound behind
        "card size stays visually consistent, column count differs."
        Quantized to a multiple of 8 to bound the thumbnail-cache key
        space (images.py's cropped_pixmap cache is keyed on exact pixel
        size) rather than a fresh size on every single pixel of resize.

        The lower-bound floor of columns=2 has no matching floor on
        render_width itself -- below usable=420px (viewport ~468px, once
        the 2*PAGE_MARGIN is added back), a forced two columns divides a
        too-small usable width and render_width drops below
        DEFAULT_CARD_WIDTH - MAX_FILL_STRETCH. That's unreachable in the
        shipped app: MainWindow enforces MIN_SIZE=(1100, 700)
        (main_window.py), which keeps this view's own viewport at
        ~826-840px even at that floor (measured directly, sidebar and
        scrollbar included) -- comfortably above the 468px breakpoint.
        A GridView used standalone below that width (as some tests do,
        deliberately, to probe the formula's own shape) is not a
        real-app scenario this method needs to guard against."""
        usable = max(self.viewport().width() - 2 * PAGE_MARGIN, DEFAULT_CARD_WIDTH)
        columns = max(2, (usable + CARD_PADDING) // (DEFAULT_CARD_WIDTH + CARD_PADDING))
        exact_fill = (usable - (columns - 1) * CARD_PADDING) // columns
        render_width = min(exact_fill, DEFAULT_CARD_WIDTH + MAX_FILL_STRETCH)
        return (render_width // 8) * 8

    def _relayout(self) -> None:
        if not self._cards:
            return
        render_width = self._compute_render_width()
        for card in self._cards:
            card.set_render_width(render_width)
        # Forces an immediate layout pass rather than Qt's own deferred
        # one, so _count_columns() below reads real, current geometry --
        # not stale positions from before this resize.
        self._layout.activate()
        # setWidgetResizable(True) does not correctly negotiate height
        # against a custom height-for-width QLayout like FlowLayout --
        # confirmed directly: left alone, _container's auto-computed
        # height answers as if squeezed to its narrowest possible single-
        # card width, not its real current width, badly undercounting
        # the true row count for any collection past the first screen.
        # Rows past that point were laid out correctly (FlowLayout itself
        # is right) but silently unreachable by scrolling, since
        # QScrollArea sizes its scroll range off _container's height, not
        # off where its deepest child actually sits. Setting the height
        # explicitly from the layout's own heightForWidth(), at
        # _container's real (already correctly width-synced) current
        # width, is what keeps every row reachable.
        self._container.setFixedHeight(self._layout.heightForWidth(self._container.width()))
        self._columns = self._count_columns()

    def _count_columns(self) -> int:
        """Derived from the FlowLayout's OWN actual post-layout geometry
        (row membership by matching y-position), not read back from the
        formula's columns variable above -- the vendored FlowLayout
        computes its wrap independently from each card's real sizeHint(),
        and a 1px disagreement between the two would otherwise silently
        break Key_Up/Key_Down's delta math below."""
        first_top = self._cards[0].y()
        return sum(1 for card in self._cards if card.y() == first_top)
