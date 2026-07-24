from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from saat.storage import WatchRecord
from saat.ui.collection_summary import compute_collection_summary, compute_wishlist_summary
from saat.ui.facets import Facet, VALUE_FACETS, is_not_worn_90d
from saat.ui.formatting import fmt_price
from saat.ui.theme import GROUP_SPACING, SIDEBAR_COLLAPSED_WIDTH, SIDEBAR_WIDTH

NOT_WORN_LABEL = "Not worn in 90 days"


class Sidebar(QWidget):
    """Left sidebar: multi-select filter facets with live counts, collapsible.
    See SPEC.md §5.1. The value list per facet is fixed at construction time
    from the full collection — only update_counts() runs on every filter
    change, so checkboxes never reflow while the user is mid-click. The
    §5.10 summary footer is the same: nothing that feeds it (count, movement
    kind, price) changes on a wear-only refresh, so it's computed once here
    rather than threaded through update_counts()."""

    changed = Signal()

    def __init__(self, records: list[WatchRecord], is_wishlist: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._collapsed = False
        self._checkboxes: dict[tuple[str, str], QCheckBox] = {}
        self._not_worn_checkbox: QCheckBox | None = None

        self._toggle_button = QPushButton("Hide filters")
        self._toggle_button.setProperty("variant", "link")
        self._toggle_button.clicked.connect(self._toggle_collapsed)

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
            checkbox = QCheckBox(NOT_WORN_LABEL)
            checkbox.toggled.connect(lambda _checked: self.changed.emit())
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        layout.addWidget(self._toggle_button, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._scroll, stretch=1)
        layout.addWidget(self._summary_footer)

        self.setFixedWidth(SIDEBAR_WIDTH)

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

        count_text = "1 watch" if summary.total == 1 else f"{summary.total} watches"
        count_label = QLabel(count_text)
        layout.addWidget(count_label)

        if summary.by_movement_kind:
            kinds = QLabel(" · ".join(f"{kind} {count}" for kind, count in summary.by_movement_kind))
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

        count_text = "1 watch" if summary.total == 1 else f"{summary.total} watches"
        count_label = QLabel(count_text)
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
                due_text = "Due within 12mo: " + " · ".join(
                    fmt_price((total, currency)) for currency, total in summary.due_next_12_months_by_currency
                )
            else:
                due_text = "Due within 12mo: 0"
            due = QLabel(due_text)
            due.setProperty("muted", True)
            due.setWordWrap(True)
            layout.addWidget(due)

        return container

    def _build_value_group(self, facet: Facet, values: list[str]) -> QWidget:
        group = QWidget()
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        heading = QLabel(facet.label.upper())
        heading.setProperty("class", "spec-row-label")
        layout.addWidget(heading)

        for value in values:
            checkbox = QCheckBox(value)
            checkbox.toggled.connect(lambda _checked: self.changed.emit())
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

    def update_counts(self, counts: dict[str, dict[str, int]], not_worn_count: int) -> None:
        for (facet_key, value), checkbox in self._checkboxes.items():
            checkbox.setText(f"{value} ({counts.get(facet_key, {}).get(value, 0)})")
        if self._not_worn_checkbox is not None:
            self._not_worn_checkbox.setText(f"{NOT_WORN_LABEL} ({not_worn_count})")

    def _toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        self._toggle_button.setText("Show filters" if self._collapsed else "Hide filters")
        self._scroll.setVisible(not self._collapsed)
        self._summary_footer.setVisible(not self._collapsed)
        self.setFixedWidth(SIDEBAR_COLLAPSED_WIDTH if self._collapsed else SIDEBAR_WIDTH)
