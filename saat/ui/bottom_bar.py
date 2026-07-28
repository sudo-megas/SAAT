"""Persistent bottom bar (SPEC.md §6, milestone 21b-e): a live, current-view
collection summary plus the app's palette control. Lives at the
QMainWindow level (setStatusBar()) so it stays on screen across every
central page — MainWindow blanks the summary text (not the palette
button) whenever it navigates away from CollectionView, and restores it
on return.

Deliberately a different number from the sidebar's own §5.10 footer: that
one reflects the whole active scope, recomputed only when the sidebar
itself rebuilds (a scope change); this one reflects the current filtered/
searched view, recomputed on every CollectionView._recompute(). Two
summaries on screen at once by design — "your collection" beside "what
you're looking at right now" — not a bug."""

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QLabel, QStatusBar, QWidget

from saat.ui.collection_summary import CollectionSummary, WishlistSummary
from saat.ui.form_fields import enum_label
from saat.ui.formatting import fmt_price
from saat.ui.palette_picker import PalettePickerButton
from saat.ui.theme import PAGE_MARGIN


class BottomBar(QStatusBar):
    palette_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "bottom-bar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizeGripEnabled(False)
        # QStatusBar's own internal layout has no margin of its own --
        # PAGE_MARGIN matches the horizontal margin TopBar and the grid's
        # own page edges already use, so the palette control lines up with
        # the same right-hand edge those do, rather than sitting flush
        # against the window border.
        self.setContentsMargins(PAGE_MARGIN, 8, PAGE_MARGIN, 8)
        self._summary: CollectionSummary | WishlistSummary | None = None

        self._summary_label = QLabel()
        self._summary_label.setProperty("muted", True)
        self.addWidget(self._summary_label, 1)

        self._palette_button = PalettePickerButton()
        self._palette_button.palette_selected.connect(self.palette_selected.emit)
        self.addPermanentWidget(self._palette_button)

    def set_summary(self, summary: CollectionSummary | WishlistSummary | None) -> None:
        self._summary = summary
        self._render_summary()

    def _watch_count_text(self, n: int) -> str:
        # Same reasoning as Sidebar._watch_count_text (sidebar.py): Qt's
        # %n/numerus mechanism is entirely translator-driven with no
        # source-language plural rule of its own, and this app never loads
        # an English translator ("absent means English") -- verified
        # empirically there. Two ordinary literals instead, both mapping
        # to the same Turkish word either way, since Turkish doesn't
        # pluralize a noun after a cardinal ("5 saat", not "5 saatler").
        return self.tr("1 watch") if n == 1 else self.tr("{count} watches").format(count=n)

    def _render_summary(self) -> None:
        if self._summary is None:
            self._summary_label.setText("")
            return

        parts = [self._watch_count_text(self._summary.total)]
        if isinstance(self._summary, WishlistSummary):
            if self._summary.target_value_by_currency:
                parts.append(
                    " · ".join(fmt_price((total, currency)) for currency, total in self._summary.target_value_by_currency)
                )
            if self._summary.has_any_target_date:
                if self._summary.due_next_12_months_by_currency:
                    due_text = self.tr("Due within 12mo: ") + " · ".join(
                        fmt_price((total, currency)) for currency, total in self._summary.due_next_12_months_by_currency
                    )
                else:
                    due_text = self.tr("Due within 12mo: 0")
                parts.append(due_text)
        else:
            if self._summary.by_movement_kind:
                parts.append(
                    " · ".join(f"{enum_label(kind)} {count}" for kind, count in self._summary.by_movement_kind)
                )
            if self._summary.value_by_currency:
                parts.append(" · ".join(fmt_price((total, currency)) for currency, total in self._summary.value_by_currency))

        self._summary_label.setText("   ·   ".join(parts))

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self._render_summary()
        super().changeEvent(event)
