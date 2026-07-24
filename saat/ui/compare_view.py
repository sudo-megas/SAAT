from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPaintEvent, QPainter
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from saat.storage import WatchRecord
from saat.ui.accuracy_ranges import build_accuracy_section
from saat.ui.case_silhouette import build_case_silhouette_section
from saat.ui.compare import RowContrast, build_compare_groups
from saat.ui.dimension_bars import build_dimension_bars_section
from saat.ui import icons
from saat.ui.minute_track import MinuteTrackHeader
from saat.ui.theme import GROUP_SPACING, PAGE_MARGIN
from saat.ui.year_view import slug_color

COLOR_SWATCH_HEIGHT = 4


class _ColorSwatchBar(QWidget):
    """A thin per-watch colour bar atop a compare column header, reusing
    year_view's slug_color() — links these headers to the visuals above
    the table (silhouette outlines, accuracy spans, dimension bars all use
    the same hue per watch). See SPEC.md M15 groundwork."""

    def __init__(self, slug: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._slug = slug
        self.setFixedHeight(COLOR_SWATCH_HEIGHT)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(slug_color(self._slug))
        painter.drawRect(self.rect())
        painter.end()


def _build_column_header(record: WatchRecord) -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    layout.addWidget(_ColorSwatchBar(record.slug))

    overline = QLabel(record.watch.brand.upper())
    overline.setProperty("class", "detail-overline")
    layout.addWidget(overline)

    title = QLabel(record.watch.model)
    title.setProperty("class", "detail-title")
    title.setWordWrap(True)
    layout.addWidget(title)

    return container


class CompareView(QScrollArea):
    """Side-by-side comparison, opened from a selection of two to four
    watches — a MainWindow-level swap with a back affordance, like
    DetailView, not a persistent view mode. See SPEC.md §5.4. Built directly
    on saat.ui.compare's data (itself built on the table view's Column
    objects), so this isn't a second implementation of the data access."""

    back_requested = Signal()

    def __init__(self, records: list[WatchRecord], parent: QWidget | None = None, is_wishlist: bool = False) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        layout.setSpacing(GROUP_SPACING)

        back_button = QPushButton("Back")
        back_button.setObjectName("back-button")
        back_button.setProperty("variant", "link")
        back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        icons.set_icon(back_button, "back")
        back_button.clicked.connect(self.back_requested.emit)
        layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignLeft)

        silhouette_section = build_case_silhouette_section(records)
        if silhouette_section is not None:
            layout.addWidget(silhouette_section)

        accuracy_section = build_accuracy_section(records)
        if accuracy_section is not None:
            layout.addWidget(accuracy_section)

        dimension_bars_section = build_dimension_bars_section(records, is_wishlist)
        if dimension_bars_section is not None:
            layout.addWidget(dimension_bars_section)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(6)
        num_columns = len(records) + 1
        for col in range(1, num_columns):
            grid.setColumnStretch(col, 1)

        for col, record in enumerate(records, start=1):
            grid.addWidget(_build_column_header(record), 0, col, Qt.AlignmentFlag.AlignTop)

        row_index = 1
        for group in build_compare_groups(records):
            grid.addWidget(MinuteTrackHeader(group.title), row_index, 0, 1, num_columns)
            row_index += 1
            for row in group.rows:
                label = QLabel(row.label)
                label.setProperty("class", "spec-row-label")
                grid.addWidget(label, row_index, 0, Qt.AlignmentFlag.AlignTop)

                for col, text in enumerate(row.values, start=1):
                    value = QLabel(text)
                    value.setProperty("class", "spec-row-value-mono" if row.numeric else "spec-row-value")
                    value.setProperty("muted", row.contrast == RowContrast.DIMMED)
                    value.setWordWrap(True)
                    grid.addWidget(value, row_index, col, Qt.AlignmentFlag.AlignTop)
                row_index += 1

        layout.addWidget(grid_widget)
        layout.addStretch()
        self.setWidget(content)
