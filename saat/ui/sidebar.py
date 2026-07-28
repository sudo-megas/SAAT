from typing import Callable

from PySide6.QtCore import QCoreApplication, QEvent, QLocale, QT_TRANSLATE_NOOP, Qt, Signal
from PySide6.QtGui import QBrush, QPaintEvent, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from saat.storage import WatchRecord
from saat.ui.collection_summary import compute_collection_summary, compute_wishlist_summary
from saat.ui.facets import Facet, VALUE_FACETS, is_not_worn_90d
from saat.ui.form_fields import ENUM_CHOICES_CONTEXT, enum_label
from saat.ui.formatting import fmt_price
from saat.ui.i18n import build_language_menu
from saat.ui import icons, motion, perlage, theme
from saat.ui.theme import GROUP_SPACING, SIDEBAR_COLLAPSED_WIDTH, SIDEBAR_WIDTH

# QT_TRANSLATE_NOOP-marked, same reason as every other module-level constant
# in this sweep -- consumed via QCoreApplication.translate("Sidebar", ...)
# below, never as a bare self.tr(NOT_WORN_LABEL) (a variable, invisible to
# lupdate).
NOT_WORN_LABEL = QT_TRANSLATE_NOOP("Sidebar", "Not worn in 90 days")


def _facet_value_label(facet: Facet, value: str) -> str:
    """The checkbox TEXT is translated when the facet's values are enum*
    vocabulary; the checkbox's identity -- the dict key in
    Sidebar._checkboxes, and everything active_facets()/update_counts()
    look up by -- always stays the canonical `value` itself. Same
    display/data split as form_fields.py's combo boxes, just for a
    checkbox instead of a combo item."""
    return QCoreApplication.translate(ENUM_CHOICES_CONTEXT, value) if facet.translate_values else value


class Sidebar(QWidget):
    """Left sidebar: multi-select filter facets with live counts, collapsible.
    See SPEC.md §5.1. The value list per facet is fixed at construction time
    from the full collection — only update_counts() runs on every filter
    change, so checkboxes never reflow while the user is mid-click. The
    §5.10 summary footer is the same: nothing that feeds it (count, movement
    kind, price) changes on a wear-only refresh, so it's computed once here
    rather than threaded through update_counts()."""

    changed = Signal()
    language_selected = Signal(object)  # str | None -- None means English

    def __init__(
        self,
        records: list[WatchRecord],
        is_wishlist: bool = False,
        parent: QWidget | None = None,
        language_code_getter: Callable[[], str | None] = lambda: None,
        tray_available: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setProperty("class", "sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._collapsed = False
        self._checkboxes: dict[tuple[str, str], QCheckBox] = {}
        self._not_worn_checkbox: QCheckBox | None = None
        self._facet_headings: list[tuple[Facet, QLabel]] = []
        self._records = records
        self._is_wishlist = is_wishlist
        self._language_code_getter = language_code_getter

        self._toggle_button = QPushButton(self.tr("Hide filters"))
        self._toggle_button.setProperty("variant", "link")
        icons.set_icon(self._toggle_button, "sidebar")
        self._toggle_button.clicked.connect(self._toggle_collapsed)

        self._clear_filters_button = QPushButton()
        self._clear_filters_button.setProperty("variant", "link")
        self._clear_filters_button.setToolTip(self.tr("Clear filters"))
        icons.set_icon(self._clear_filters_button, "clear-filters")
        self._clear_filters_button.clicked.connect(self._clear_all_filters)
        self._clear_filters_button.setVisible(False)

        valid_watches = [r.watch for r in records if r.watch is not None]

        self._groups_container = QWidget()
        groups_layout = QVBoxLayout(self._groups_container)
        groups_layout.setContentsMargins(0, 0, 0, 0)
        groups_layout.setSpacing(GROUP_SPACING)

        for facet in VALUE_FACETS:
            # SPEC.md §5.12: Status is degenerate in Wishlist scope — scope
            # itself already fixed every record's status, so the facet would
            # only ever offer one, always-checked-feeling value.
            if is_wishlist and facet.key == "status":
                continue
            values = sorted({v for w in valid_watches for v in facet.extract(w)}, key=facet.sort_key)
            if values:
                groups_layout.addWidget(self._build_value_group(facet, values))

        # SPEC.md §5.12: every Wishlist watch trivially qualifies as "not
        # worn" once wear tracking excludes non-Owned watches — the facet
        # would carry zero filtering value there.
        if not is_wishlist and any(is_not_worn_90d(w) for w in valid_watches):
            checkbox = QCheckBox(QCoreApplication.translate("Sidebar", NOT_WORN_LABEL))
            checkbox.toggled.connect(lambda _checked: self._on_facet_toggled())
            self._not_worn_checkbox = checkbox
            groups_layout.addWidget(checkbox)

        groups_layout.addStretch()

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidget(self._groups_container)

        self._summary_footer = (
            self._build_wishlist_summary_footer(records) if is_wishlist else self._build_summary_footer(records)
        )

        # No tray control is reachable when there's no tray (SPEC.md's
        # localisation section) -- this fallback covers that case, hidden
        # by default since most sessions do have a tray. Lives beside the
        # footer, not inside it: _toggle_collapsed() hides the footer along
        # with the facet list, and language must stay reachable regardless
        # of collapse state -- the always-visible toggle button is one
        # click away either way.
        self._language_button = QPushButton(self.tr("Language"))
        self._language_button.setProperty("variant", "link")
        self._language_button.clicked.connect(self._show_language_menu)
        self._language_button.setVisible(not tray_available)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self._toggle_button)
        header.addStretch()
        header.addWidget(self._clear_filters_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        layout.addLayout(header)
        layout.addWidget(self._scroll, stretch=1)
        layout.addWidget(self._summary_footer)
        layout.addWidget(self._language_button)

        self.setFixedWidth(SIDEBAR_WIDTH)

    def paintEvent(self, event: QPaintEvent) -> None:
        # QSS background/border first (WA_StyledBackground), then perlage
        # layered on top -- the same "paint a custom layer over QSS chrome"
        # idiom WatchCard's own paintEvent already uses for its hover wash.
        super().paintEvent(event)
        colors = theme.colors()
        tile = perlage.render_perlage_tile(colors.plate_high, colors.rule)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QBrush(tile))
        painter.end()

    def _watch_count_text(self, n: int) -> str:
        # Not Qt's %n/numerus mechanism: that's entirely translator-driven
        # with no source-language plural rule of its own, and this app
        # never loads an English translator ("absent means English") --
        # verified empirically (self.tr("%n watch(es)", "", n) returns the
        # literal string "1 watch(es)" with no translator installed, for
        # every n). Two ordinary literals instead, picked by a plain
        # Python ternary exactly like every other translated string in the
        # sweep. Both map to the same Turkish word either way -- Turkish
        # doesn't pluralize a noun after a cardinal ("5 saat", not
        # "5 saatler") -- so seeing two .ts entries with identical Turkish
        # values is correct, not a copy-paste error.
        return self.tr("1 watch") if n == 1 else self.tr("{count} watches").format(count=n)

    def _build_summary_footer(self, records: list[WatchRecord]) -> QWidget:
        summary = compute_collection_summary(records)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(4)

        rule = QWidget()
        rule.setFixedHeight(1)
        rule.setProperty("class", "sidebar-summary-rule")
        layout.addWidget(rule)

        count_label = QLabel(self._watch_count_text(summary.total))
        layout.addWidget(count_label)

        if summary.by_movement_kind:
            # movement_kind is enum* vocabulary (see columns.py's
            # translate_values=True on the same field) -- found during
            # Commit C, not Commit A's sweep: this summary line is a
            # separate display site from the facet checkboxes beside it,
            # which were already correctly translated.
            kinds = QLabel(" · ".join(f"{enum_label(kind)} {count}" for kind, count in summary.by_movement_kind))
            kinds.setProperty("muted", True)
            kinds.setWordWrap(True)
            layout.addWidget(kinds)

        if summary.value_by_currency:
            values = QLabel(" · ".join(fmt_price((total, currency)) for currency, total in summary.value_by_currency))
            values.setProperty("muted", True)
            values.setWordWrap(True)
            layout.addWidget(values)

        return container

    def _build_wishlist_summary_footer(self, records: list[WatchRecord]) -> QWidget:
        """SPEC.md §5.12: Wishlist scope's summary strip — sibling to
        §5.10's footer, same plain-figures restraint, swapped in instead of
        it rather than added alongside."""
        summary = compute_wishlist_summary(records)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(4)

        rule = QWidget()
        rule.setFixedHeight(1)
        rule.setProperty("class", "sidebar-summary-rule")
        layout.addWidget(rule)

        count_label = QLabel(self._watch_count_text(summary.total))
        layout.addWidget(count_label)

        if summary.target_value_by_currency:
            values = QLabel(
                " · ".join(fmt_price((total, currency)) for currency, total in summary.target_value_by_currency)
            )
            values.setProperty("muted", True)
            values.setWordWrap(True)
            layout.addWidget(values)

        if summary.has_any_target_date:
            if summary.due_next_12_months_by_currency:
                due_text = self.tr("Due within 12mo: ") + " · ".join(
                    fmt_price((total, currency)) for currency, total in summary.due_next_12_months_by_currency
                )
            else:
                due_text = self.tr("Due within 12mo: 0")
            due = QLabel(due_text)
            due.setProperty("muted", True)
            due.setWordWrap(True)
            layout.addWidget(due)

        return container

    def _facet_heading_text(self, facet: Facet) -> str:
        # QLocale().toUpper(), not plain Python .upper(): Turkish casing
        # turns lowercase "i" into dotted "İ" (capital dotted i), which
        # ASCII-style .upper() gets wrong (produces plain "I") -- verified
        # this PySide6 build actually applies the ICU-backed rule rather
        # than silently falling back to ASCII casing. Bare QLocale() (no
        # code passed in): install_language()/uninstall_language() are the
        # only two places that ever call QLocale.setDefault(), so this
        # always reflects the actual active language with no getter
        # threaded through, and never QLocale.system().
        return QLocale().toUpper(QCoreApplication.translate("Facets", facet.label))

    def _build_value_group(self, facet: Facet, values: list[str]) -> QWidget:
        group = QWidget()
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        heading = QLabel(self._facet_heading_text(facet))
        heading.setProperty("class", "spec-row-label")
        layout.addWidget(heading)
        self._facet_headings.append((facet, heading))

        for value in values:
            checkbox = QCheckBox(_facet_value_label(facet, value))
            checkbox.toggled.connect(lambda _checked: self._on_facet_toggled())
            self._checkboxes[(facet.key, value)] = checkbox
            layout.addWidget(checkbox)

        return group

    def active_facets(self) -> dict[str, set[str]]:
        active: dict[str, set[str]] = {}
        for (facet_key, value), checkbox in self._checkboxes.items():
            if checkbox.isChecked():
                active.setdefault(facet_key, set()).add(value)
        return active

    def not_worn_only(self) -> bool:
        return self._not_worn_checkbox is not None and self._not_worn_checkbox.isChecked()

    def _has_active_filters(self) -> bool:
        return bool(self.active_facets()) or self.not_worn_only()

    def _on_facet_toggled(self) -> None:
        self._clear_filters_button.setVisible(self._has_active_filters())
        self.changed.emit()

    def _clear_all_filters(self) -> None:
        all_checkboxes = list(self._checkboxes.values())
        if self._not_worn_checkbox is not None:
            all_checkboxes.append(self._not_worn_checkbox)
        for checkbox in all_checkboxes:
            checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(False)
        self._on_facet_toggled()

    def update_counts(self, counts: dict[str, dict[str, int]], not_worn_count: int) -> None:
        facets_by_key = {facet.key: facet for facet in VALUE_FACETS}
        for (facet_key, value), checkbox in self._checkboxes.items():
            label = _facet_value_label(facets_by_key[facet_key], value)
            checkbox.setText(f"{label} ({counts.get(facet_key, {}).get(value, 0)})")
        if self._not_worn_checkbox is not None:
            not_worn_label = QCoreApplication.translate("Sidebar", NOT_WORN_LABEL)
            self._not_worn_checkbox.setText(f"{not_worn_label} ({not_worn_count})")

    def _toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        self._toggle_button.setText(self.tr("Show filters") if self._collapsed else self.tr("Hide filters"))
        self._scroll.setVisible(not self._collapsed)
        self._summary_footer.setVisible(not self._collapsed)
        motion.animate_width(self, SIDEBAR_COLLAPSED_WIDTH if self._collapsed else SIDEBAR_WIDTH)

    def set_tray_available(self, available: bool) -> None:
        self._language_button.setVisible(not available)

    def _show_language_menu(self) -> None:
        menu = build_language_menu(self._language_code_getter(), self.language_selected.emit)
        menu.exec(self._language_button.mapToGlobal(self._language_button.rect().bottomLeft()))

    def _rebuild_summary_footer(self) -> None:
        old = self._summary_footer
        self._summary_footer = (
            self._build_wishlist_summary_footer(self._records)
            if self._is_wishlist
            else self._build_summary_footer(self._records)
        )
        self.layout().replaceWidget(old, self._summary_footer)
        old.deleteLater()
        # A freshly built widget defaults to visible -- reapply the
        # collapsed state's own invariant, or a language switch while
        # collapsed would make the footer pop back into view on its own.
        self._summary_footer.setVisible(not self._collapsed)

    def _retranslate(self) -> None:
        self._toggle_button.setText(self.tr("Show filters") if self._collapsed else self.tr("Hide filters"))
        self._clear_filters_button.setToolTip(self.tr("Clear filters"))
        for facet, heading in self._facet_headings:
            heading.setText(self._facet_heading_text(facet))
        self._language_button.setText(self.tr("Language"))
        self._rebuild_summary_footer()
        # Per-value checkbox text (and the not-worn checkbox's label) isn't
        # retranslated here -- update_counts() already re-evaluates every
        # QCoreApplication.translate() call fresh, and CollectionView's own
        # changeEvent re-invokes it via _recompute() for exactly this
        # reason. Retranslating it a second time here would just repeat
        # that work with stale counts (this widget doesn't own the counts
        # dict update_counts() needs).

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
