from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QScrollArea, QWidget

from saat.storage import WatchRecord
from saat.ui.cards import CARD_WIDTH, WatchCard
from saat.ui.theme import CARD_PADDING, PAGE_MARGIN


class GridView(QScrollArea):
    """Reflowing card grid. See SPEC.md §5.2 — four to five cards per row on a
    1440p display, not capped to a fixed content width."""

    record_activated = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QScrollArea.Shape.NoFrame)

        self._container = QWidget()
        self._layout = QGridLayout(self._container)
        self._layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        self._layout.setSpacing(CARD_PADDING)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setWidget(self._container)

        self._cards: list[WatchCard] = []

    def set_records(self, records: list[WatchRecord]) -> None:
        for card in self._cards:
            self._layout.removeWidget(card)
            card.deleteLater()
        self._cards = [WatchCard(record) for record in records]
        for card in self._cards:
            card.activated.connect(self.record_activated.emit)
        self._relayout()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self) -> None:
        if not self._cards:
            return
        for card in self._cards:
            self._layout.removeWidget(card)

        available = max(self.viewport().width() - 2 * PAGE_MARGIN, CARD_WIDTH)
        column_width = CARD_WIDTH + CARD_PADDING
        columns = max(1, (available + CARD_PADDING) // column_width)

        for index, card in enumerate(self._cards):
            row, col = divmod(index, columns)
            self._layout.addWidget(card, row, col)
