from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from saat.storage import WatchRecord
from saat.ui import theme
from saat.ui.compare import (
    SilhouetteEntry,
    build_silhouette_entries,
    should_show_silhouette,
    silhouette_profile_entries,
    silhouette_scale,
)
from saat.ui.formatting import fmt_number
from saat.ui.theme import SIZE_XS, resolve_fonts
from saat.ui.year_view import slug_color

# A bounded, fixed drawing width — a compact technical diagram, not
# something that should balloon to a maximized window's full content
# width (a 46mm lug-to-lug at "fit self.width()" would draw a ~1500px
# circle on a 1440p window). silhouette_scale() is still the thing that
# turns this into px-per-mm, so every measurement below stays derived,
# never hardcoded twice.
DRAWING_WIDTH = 280
TOP_DOWN_PADDING = 12
STROKE_WIDTH = 2  # 1px reads too faint for a hue at this size — see groundwork note in SPEC.md M15
FALLBACK_LUG_BLOCK_FRACTION = 0.4  # when lug_width_mm is absent, a plausible lug-block width relative to the case
PROFILE_ROW_PADDING = 4
PROFILE_GAP = 4
SCALE_BAR_MM = 10
SCALE_BAR_HEIGHT = 28
LEGEND_ROW_HEIGHT = 18


def drawing_scale(entries: list[SilhouetteEntry]) -> float:
    """The shared px-per-mm actually used to draw — silhouette_scale()
    against the drawing width *minus* padding on both sides, not the full
    DRAWING_WIDTH. Without that margin, whichever watch's own extent sets
    the scale draws with its edge landing exactly on the widget's boundary
    pixel — same problem as the vertical padding already avoids, just on
    the axis a lug-to-lug-less watch (scaled by diameter alone) actually
    exercises."""
    return silhouette_scale(entries, DRAWING_WIDTH - 2 * TOP_DOWN_PADDING)


def _lug_block_width_mm(entry: SilhouetteEntry) -> float:
    return entry.lug_width_mm if entry.lug_width_mm is not None else entry.diameter_mm * FALLBACK_LUG_BLOCK_FRACTION


def _mono_font(size: int = SIZE_XS) -> QFont:
    font = QFont(resolve_fonts()["mono"])
    font.setPixelSize(size)
    return font


def _sans_font(size: int = SIZE_XS, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont(resolve_fonts()["sans_condensed"])
    font.setPixelSize(size)
    font.setWeight(weight)
    return font


def _section_heading(text: str) -> QLabel:
    """Matches calendar_stats.py's own section headings — plain, muted,
    condensed, uppercase. Not a spec group, so deliberately not a
    MinuteTrackHeader: SPEC.md §6 reserves that flourish for the detail
    page's actual spec groups, and calendar_stats.py's derived sections
    already set the precedent of a plainer heading for this kind of
    computed, non-spec-group section."""
    heading = QLabel(text.upper())
    heading.setProperty("class", "spec-row-label")
    return heading


class _TopDownSilhouette(QWidget):
    """Concentric, to-scale outlines sharing one centre point — differences
    read as offsets, not as separate side-by-side drawings. Stroke only, no
    fill, so smaller circles are never hidden behind larger ones. See
    SPEC.md §5.4."""

    def __init__(self, entries: list[SilhouetteEntry], scale: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries = entries
        self._scale = scale
        max_extent_mm = max(
            (e.lug_to_lug_mm if e.lug_to_lug_mm is not None else e.diameter_mm) for e in entries
        )
        self.setFixedSize(DRAWING_WIDTH, round(max_extent_mm * scale) + 2 * TOP_DOWN_PADDING)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Explicit, not inherited from the app stylesheet — same reasoning
        # as _RotationBar/_ChipSwatch (calendar_stats.py): a widget that
        # draws its own scene should not depend on ambient QSS state for
        # what counts as "empty", which also keeps pixel sampling reliable.
        painter.fillRect(self.rect(), QColor(theme.colors().plate))
        cx, cy = self.width() / 2, self.height() / 2

        for entry in self._entries:
            color = slug_color(entry.record.slug)
            painter.setPen(QPen(color, STROKE_WIDTH))
            painter.setBrush(Qt.BrushStyle.NoBrush)

            radius = (entry.diameter_mm / 2) * self._scale
            painter.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))

            if entry.lug_to_lug_mm is None:
                continue
            lug_half_span = (entry.lug_to_lug_mm / 2) * self._scale
            lug_height = lug_half_span - radius
            if lug_height <= 0:
                continue
            block_width = _lug_block_width_mm(entry) * self._scale
            painter.drawRect(QRectF(cx - block_width / 2, cy - lug_half_span, block_width, lug_height))
            painter.drawRect(QRectF(cx - block_width / 2, cy + radius, block_width, lug_height))

        painter.end()


class _SideProfileRow(QWidget):
    """One watch's side profile at the shared scale: width = diameter,
    height = thickness — the dimension people misjudge most from numbers
    alone. Stacked vertically (not side by side) so the strip can never
    overflow: each row is at most DRAWING_WIDTH wide, the same bound the
    top-down view already respects, rather than n-times-diameter wide."""

    def __init__(self, entry: SilhouetteEntry, scale: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry = entry
        self._scale = scale
        # Sized to its own rectangle, not a shared fixed height: thickness is
        # a real fraction of the same mm-to-px scale as everything else
        # here (a 14mm thickness at ~5px/mm is ~70px, nowhere near "thin"),
        # so a fixed PROFILE_ROW_HEIGHT would clip the rectangle's top and
        # bottom edges down to two bare vertical strokes — caught by
        # actually looking at a rendered screenshot, not by the pixel tests
        # above (which only ever checked width, never this height).
        drawn_height = round(entry.thickness_mm * scale)
        self.setFixedSize(DRAWING_WIDTH, drawn_height + 2 * PROFILE_ROW_PADDING)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(theme.colors().plate))
        color = slug_color(self._entry.record.slug)

        width = self._entry.diameter_mm * self._scale
        height = self._entry.thickness_mm * self._scale
        cx = self.width() / 2
        top = (self.height() - height) / 2
        painter.setPen(QPen(color, STROKE_WIDTH))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(cx - width / 2, top, width, height))

        painter.setFont(_mono_font())
        painter.setPen(QColor(theme.colors().text_muted))
        label = fmt_number(self._entry.thickness_mm, " mm")
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label)

        painter.end()


class _ScaleBar(QWidget):
    """A fixed-length mm reference so the viewer can judge the drawing is
    true scale, not just relatively proportioned. See SPEC.md §5.4."""

    def __init__(self, scale: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scale = scale
        self.setFixedSize(DRAWING_WIDTH, SCALE_BAR_HEIGHT)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(theme.colors().plate))
        length = SCALE_BAR_MM * self._scale
        y = 6
        pen = QPen(QColor(theme.colors().text_muted), 1)
        painter.setPen(pen)
        painter.drawLine(0, y, round(length), y)
        painter.drawLine(0, y - 4, 0, y + 4)
        painter.drawLine(round(length), y - 4, round(length), y + 4)

        painter.setFont(_mono_font())
        painter.drawText(0, y + 6, round(length) + 40, 14, Qt.AlignmentFlag.AlignLeft, f"{SCALE_BAR_MM} mm")
        painter.end()


class _LegendRow(QWidget):
    """Watch name in its slug colour, diameter and lug-to-lug in monospace —
    or, for a watch missing case data entirely, its name muted alongside a
    plain note that it isn't drawn above. See SPEC.md §5.4."""

    def __init__(self, record: WatchRecord, entry: SilhouetteEntry | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._record = record
        self._entry = entry
        self.setFixedHeight(LEGEND_ROW_HEIGHT)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(theme.colors().plate))
        name = f"{self._record.watch.brand} {self._record.watch.model}"
        name_font = _sans_font(SIZE_XS, QFont.Weight.DemiBold)
        painter.setFont(name_font)

        muted = QColor(theme.colors().text_muted)
        painter.setPen(muted if self._entry is None else slug_color(self._record.slug))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        name_width = QFontMetrics(name_font).horizontalAdvance(name)
        detail_rect = self.rect().adjusted(name_width + 12, 0, 0, 0)
        painter.setPen(muted)
        if self._entry is None:
            painter.setFont(_sans_font())
            painter.drawText(detail_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "No case data")
        else:
            painter.setFont(_mono_font())
            diameter = fmt_number(self._entry.diameter_mm, " mm")
            lug_to_lug = fmt_number(self._entry.lug_to_lug_mm, " mm") if self._entry.lug_to_lug_mm is not None else "—"
            painter.drawText(
                detail_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"⌀ {diameter}   L2L {lug_to_lug}",
            )
        painter.end()


def build_case_silhouette_section(records: list[WatchRecord]) -> QWidget | None:
    """The whole Commit A visual: to-scale top-down silhouette, side-profile
    strip, mm scale bar and legend. None hides it entirely — SPEC.md §5.4:
    'Hide the whole section when fewer than 2 selected watches have
    diameter data.'"""
    if not should_show_silhouette(records):
        return None

    entries, _ = build_silhouette_entries(records)
    scale = drawing_scale(entries)

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addWidget(_section_heading("Case Silhouette"))
    layout.addWidget(_TopDownSilhouette(entries, scale))

    profile_entries = silhouette_profile_entries(entries)
    if len(profile_entries) >= 2:
        profile_container = QWidget()
        profile_layout = QVBoxLayout(profile_container)
        profile_layout.setContentsMargins(0, 0, 0, 0)
        profile_layout.setSpacing(PROFILE_GAP)
        for entry in profile_entries:
            profile_layout.addWidget(_SideProfileRow(entry, scale))
        layout.addWidget(profile_container)

    layout.addWidget(_ScaleBar(scale))

    legend = QWidget()
    legend_layout = QVBoxLayout(legend)
    legend_layout.setContentsMargins(0, 0, 0, 0)
    legend_layout.setSpacing(2)
    entries_by_slug = {e.record.slug: e for e in entries}
    for record in records:
        if record.watch is None:
            continue
        legend_layout.addWidget(_LegendRow(record, entries_by_slug.get(record.slug)))
    layout.addWidget(legend)

    return container
