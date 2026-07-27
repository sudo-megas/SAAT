"""Turns a saat.ui.export ExportPlan into an actual PDF via QPdfWriter and
QPainter -- the same painter API silhouettes and minute tracks already use
elsewhere in this app, just targeting a print device instead of a widget.
See SPEC.md §9.

All layout math below stays in points (1/72in), matching saat.ui.export's
height model exactly, and _px()/_rect()/_point() convert to device pixels
at the point of every actual painter call. This is deliberate, not
incidental: QFont's point size already resolves against the paint
device's real DPI (300 here) on its own, so a persistent
painter.scale(DPI/72, DPI/72) transform -- the more obvious-looking
approach -- double-scales every piece of text, while leaving pure
geometry (drawRect, drawLine) scaled correctly once. Confirmed empirically
before writing the rest of this file: identical drawText calls under a
scale() transform rendered text 3-4x too tall, overlapping every
adjacent row, while the same calls with coordinates pre-converted to
device pixels rendered correctly."""

import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PySide6.QtCore import QLocale, QMarginsF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPageSize, QPainter, QPainterPath, QPdfWriter

from saat.models import Watch
from saat.storage import WatchRecord
from saat.ui import theme
from saat.ui.detail_view import acquisition_rows_plain, case_rows, dial_rows, maintenance_rows, movement_rows
from saat.ui.export import (
    FOOTER_HEIGHT_PT,
    GROUP_HEADER_HEIGHT_PT,
    GROUP_SPACING_PT,
    IDENTITY_BLOCK_HEIGHT_PT,
    LINE_HEIGHT_PT,
    PAGE_A4,
    PAGE_LETTER,
    PAGE_MARGIN_PT,
    PHOTO_BLOCK_HEIGHT_PT,
    SUMMARY_HEADER_HEIGHT_PT,
    SUMMARY_ROW_HEIGHT_PT,
    TITLE_BLOCK_HEIGHT_PT,
    ExportPlan,
    GroupContent,
    GroupSlice,
    SummaryPage,
    SummaryRow,
    WatchExportInput,
    WatchPage,
    build_export_plan,
    page_dimensions_pt,
    wrap_notes,
)
from saat.ui.formatting import EM_DASH, fmt_date, fmt_number
from saat.ui.images import first_image, load_for_export
from saat.ui.minute_track import draw_minute_track
from saat.ui.spec_group import SpecRow

DPI = 300
_SCALE = DPI / 72.0  # points -> device pixels; see module docstring


def _px(value_pt: float) -> float:
    return value_pt * _SCALE


def _rect(x_pt: float, y_pt: float, w_pt: float, h_pt: float) -> QRectF:
    return QRectF(_px(x_pt), _px(y_pt), _px(w_pt), _px(h_pt))


def _point(x_pt: float, y_pt: float) -> QPointF:
    return QPointF(_px(x_pt), _px(y_pt))


class ExportError(Exception):
    """A known, already-well-messaged export failure: nothing to export,
    an unwritable path, or QPdfWriter silently producing nothing (it fails
    by returning False or leaving an empty file far more often than it
    raises). An unexpected exception from elsewhere propagates as itself
    -- either way, nothing here is ever swallowed (SPEC.md §2 rule 7)."""


def detect_page_size() -> str:
    """Letter for US/Canada, A4 everywhere else -- QLocale.system(), not
    Python's own locale module: the latter returns (None, None) unless
    something has already called setlocale(), which this app never does,
    so it can't be trusted to reflect the user's real locale on every
    machine this runs on. QLocale needs no event loop to query."""
    territory = QLocale.system().territory()
    if territory in (QLocale.Country.UnitedStates, QLocale.Country.Canada):
        return PAGE_LETTER
    return PAGE_A4


@dataclass
class _RenderGroup:
    title: str
    kind: str  # "spec" (SpecRow label/value pairs) or "lines" (one string per item)
    items: list

    @property
    def line_count(self) -> int:
        return len(self.items)


def _strap_lines(watch: Watch) -> list[str]:
    lines = []
    for strap in watch.straps:
        title_parts = [p for p in (strap.material, strap.colour) if p]
        title = " · ".join(title_parts) if title_parts else EM_DASH
        if strap.fitted:
            title += "  (fitted)"
        lines.append(title)

        detail_parts = []
        if strap.width_mm is not None:
            detail_parts.append(fmt_number(strap.width_mm, " mm"))
        if strap.clasp:
            detail_parts.append(strap.clasp)
        lines.append(" · ".join(detail_parts) if detail_parts else EM_DASH)
    return lines


def _log_lines(watch: Watch) -> list[str]:
    entries = sorted(watch.log, key=lambda e: e.date or date.min, reverse=True)
    lines = []
    for entry in entries:
        header_parts = [p for p in (fmt_date(entry.date) if entry.date else None, entry.kind) if p]
        lines.append(" · ".join(header_parts) if header_parts else EM_DASH)
        lines.extend(wrap_notes(entry.note or ""))
    return lines


def _timing_lines(watch: Watch) -> list[str]:
    entries = sorted(watch.timing, key=lambda e: e.date or date.min, reverse=True)
    lines = []
    for entry in entries:
        parts = [
            p
            for p in (
                fmt_date(entry.date) if entry.date else None,
                f"{entry.deviation_sec:+g} sec" if entry.deviation_sec is not None else None,
                entry.position,
            )
            if p
        ]
        lines.append(" · ".join(parts) if parts else EM_DASH)
    return lines


def build_render_groups(record: WatchRecord) -> list[_RenderGroup]:
    """Computed exactly once per watch. Both the pagination plan's
    GroupContent line counts (via to_group_contents) and the actual
    drawing (_draw_watch_page) come from this same list, so what
    pagination bills a page for and what gets painted are guaranteed to
    be the same lines rather than two independent derivations that could
    quietly disagree.

    Movement/Case/Dial/Acquisition/Maintenance are sourced from
    saat.ui.detail_view's own row-builders -- not saat.ui.columns'
    Column/GROUP_ORDER system, which was checked and rejected: it shows
    power reserve *and* battery life as separate always-present columns,
    where the detail view (and bullet 8's "exactly as the detail view
    does") shows whichever one the movement's kind calls for and hides
    the other. "Compatible Straps" is deliberately excluded: it isn't
    this watch's own data, it's a recommendation computed against the
    rest of a live, mutable collection, which a frozen document has no
    sensible way to represent."""
    watch = record.watch
    groups: list[_RenderGroup] = []

    def add_spec(title: str, rows: list[SpecRow]) -> None:
        if any(row.text != EM_DASH for row in rows):
            groups.append(_RenderGroup(title, "spec", rows))

    add_spec("Movement", movement_rows(watch))
    add_spec("Case", case_rows(watch))
    add_spec("Dial", dial_rows(watch))
    if watch.straps:
        groups.append(_RenderGroup("Straps", "lines", _strap_lines(watch)))
    add_spec("Acquisition", acquisition_rows_plain(watch))
    add_spec("Maintenance", maintenance_rows(watch))
    if watch.log:
        groups.append(_RenderGroup("Log", "lines", _log_lines(watch)))
    if watch.timing:
        groups.append(_RenderGroup("Timing", "lines", _timing_lines(watch)))
    notes_lines = wrap_notes(watch.notes or "")
    if notes_lines:
        groups.append(_RenderGroup("Notes", "lines", notes_lines))

    return groups


def _to_group_contents(render_groups: list[_RenderGroup]) -> list[GroupContent]:
    return [GroupContent(g.title, g.line_count) for g in render_groups]


def export_pdf(path: Path, records: list[WatchRecord], is_wishlist: bool, document_title: str) -> None:
    """Writes a PDF to path, raising ExportError (or propagating whatever
    else went wrong) rather than ever failing silently -- SPEC.md §2 rule
    7. Any failure, expected or not, unlinks whatever QPdfWriter may
    already have put on disk first, so a failed export never leaves a
    truncated file where the user expects a real document."""
    exportable = [r for r in records if r.watch is not None]
    if not exportable:
        raise ExportError("There is nothing to export.")

    page_size = detect_page_size()
    render_groups_by_slug = {r.slug: build_render_groups(r) for r in exportable}
    watch_inputs = [
        WatchExportInput(record=r, groups=_to_group_contents(render_groups_by_slug[r.slug])) for r in exportable
    ]
    plan = build_export_plan(watch_inputs, is_wishlist, page_size)

    writer = QPdfWriter(str(path))
    writer.setResolution(DPI)
    page_size_id = QPageSize.PageSizeId.Letter if page_size == PAGE_LETTER else QPageSize.PageSizeId.A4
    writer.setPageSize(QPageSize(page_size_id))
    # Zeroed explicitly: QPdfWriter's default margins would otherwise
    # shrink the paintable area below the true page_dimensions_pt this
    # module's coordinates assume, silently offsetting every draw call.
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))

    painter = QPainter(writer)
    if not painter.isActive():
        Path(path).unlink(missing_ok=True)
        raise ExportError(f"Could not write to {path}.")

    try:
        generation_date = fmt_date(date.today())
        for i, page in enumerate(plan.pages):
            if i > 0:
                writer.newPage()
            if isinstance(page, SummaryPage):
                _draw_summary_page(painter, page, i, plan, document_title, generation_date)
            else:
                _draw_watch_page(
                    painter, page, render_groups_by_slug[page.record.slug], i, plan, document_title, generation_date
                )
        painter.end()
    except BaseException:
        if painter.isActive():
            painter.end()
        del writer
        Path(path).unlink(missing_ok=True)
        raise

    # QPdfWriter can fail an I/O error by returning False / warning rather
    # than raising -- an unwritable directory discovered only mid-write
    # can leave a zero-byte file with no exception at all. This is the
    # actual "never leave a truncated PDF" guarantee; the try/except above
    # only catches what Qt chooses to raise.
    written = Path(path)
    if not written.exists() or written.stat().st_size == 0:
        written.unlink(missing_ok=True)
        raise ExportError(f"Could not write to {path}.")


# --- Fonts -----------------------------------------------------------
# Point sizes here are real typographic points -- QFont resolves them
# against the QPdfWriter's own 300dpi directly, no _px() conversion
# needed or wanted (see module docstring).

def _font(role: str, size: float, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    fonts = theme.resolve_fonts()
    font = QFont(fonts[role])
    font.setPointSizeF(size)
    font.setWeight(weight)
    return font


def _title_font() -> QFont:
    return _font("sans", 20, QFont.Weight.DemiBold)


def _heading_font() -> QFont:
    return _font("sans", 15, QFont.Weight.DemiBold)


def _label_font() -> QFont:
    return _font("sans_condensed", 7.5, QFont.Weight.DemiBold)


def _body_font() -> QFont:
    return _font("sans", 8.5)


def _mono_font() -> QFont:
    return _font("mono", 8.5)


def _footer_font() -> QFont:
    return _font("sans", 7.5)


# --- Shared page furniture -----------------------------------------------------------

def _draw_page_furniture(painter: QPainter, page_index: int, plan: ExportPlan, document_title: str, generation_date: str) -> None:
    width_pt, height_pt = page_dimensions_pt(plan.page_size)
    footer_rect = _rect(PAGE_MARGIN_PT, height_pt - PAGE_MARGIN_PT, width_pt - 2 * PAGE_MARGIN_PT, FOOTER_HEIGHT_PT)
    painter.setFont(_footer_font())
    painter.setPen(QColor(theme.PAPER.text_muted))
    text = f"{document_title}  ·  {generation_date}  ·  {page_index + 1} of {plan.page_count}"
    painter.drawText(footer_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, text)


def _content_rect_pt(plan: ExportPlan) -> tuple[float, float, float]:
    """Content left/top/width in points -- callers do their own y
    bookkeeping in points and pass coordinates through _rect()/_point()
    only at the moment of an actual painter call."""
    width_pt, _ = page_dimensions_pt(plan.page_size)
    return PAGE_MARGIN_PT, PAGE_MARGIN_PT, width_pt - 2 * PAGE_MARGIN_PT


# --- Summary page -----------------------------------------------------------

_SUMMARY_COLUMNS = ("Brand", "Model", "Reference", "Serial", "Value")
_SUMMARY_WIDTHS = (0.22, 0.28, 0.18, 0.17, 0.15)


def _summary_column_x(left: float, width: float) -> list[float]:
    xs = [left]
    for fraction in _SUMMARY_WIDTHS[:-1]:
        xs.append(xs[-1] + width * fraction)
    return xs


def _draw_summary_table_header(painter: QPainter, left: float, width: float, y: float) -> None:
    xs = _summary_column_x(left, width)
    widths = [width * f for f in _SUMMARY_WIDTHS]
    painter.setFont(_label_font())
    painter.setPen(QColor(theme.PAPER.text_muted))
    for label, x, col_width in zip(_SUMMARY_COLUMNS, xs, widths):
        align = Qt.AlignmentFlag.AlignRight if label == "Value" else Qt.AlignmentFlag.AlignLeft
        painter.drawText(_rect(x, y, col_width, SUMMARY_HEADER_HEIGHT_PT), align | Qt.AlignmentFlag.AlignVCenter, label.upper())
    rule_y = y + SUMMARY_HEADER_HEIGHT_PT - 2
    painter.setPen(QColor(theme.PAPER.rule))
    painter.drawLine(_point(left, rule_y), _point(left + width, rule_y))


def _draw_summary_row(painter: QPainter, row: SummaryRow, left: float, width: float, y: float) -> None:
    xs = _summary_column_x(left, width)
    widths = [width * f for f in _SUMMARY_WIDTHS]
    values = (row.brand, row.model, row.reference, row.serial, row.value_text)
    for i, (value, x, col_width) in enumerate(zip(values, xs, widths)):
        is_value_column = i == len(values) - 1
        painter.setFont(_mono_font() if is_value_column else _body_font())
        painter.setPen(QColor(theme.PAPER.text))
        align = Qt.AlignmentFlag.AlignRight if is_value_column else Qt.AlignmentFlag.AlignLeft
        painter.drawText(_rect(x, y, col_width, SUMMARY_ROW_HEIGHT_PT), align | Qt.AlignmentFlag.AlignVCenter, value)


def _draw_summary_page(
    painter: QPainter, page: SummaryPage, page_index: int, plan: ExportPlan, document_title: str, generation_date: str
) -> None:
    left, top, width = _content_rect_pt(plan)
    y = top
    is_first = page_index == 0

    if is_first:
        painter.setFont(_title_font())
        painter.setPen(QColor(theme.PAPER.text))
        painter.drawText(_rect(left, y, width, 28), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, document_title)
        y += 32

        painter.setFont(_body_font())
        painter.setPen(QColor(theme.PAPER.text_muted))
        painter.drawText(_rect(left, y, width, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"Generated {generation_date}")
        y += 18

        value_text = ", ".join(f"{amount:,.2f} {currency}" for currency, amount in plan.value_by_currency) or EM_DASH
        item_word = "item" if plan.item_count == 1 else "items"
        painter.drawText(
            _rect(left, y, width, 14),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"{plan.item_count} {item_word} · {value_text}",
        )
        y = top + TITLE_BLOCK_HEIGHT_PT

    _draw_summary_table_header(painter, left, width, y)
    y += SUMMARY_HEADER_HEIGHT_PT
    for row in page.rows:
        _draw_summary_row(painter, row, left, width, y)
        y += SUMMARY_ROW_HEIGHT_PT

    _draw_page_furniture(painter, page_index, plan, document_title, generation_date)


# --- Watch page -----------------------------------------------------------

def _identity_line(watch: Watch) -> str:
    return f"{watch.brand} {watch.model}"


def _draw_identity_block(painter: QPainter, left: float, width: float, y: float, watch: Watch) -> None:
    painter.setFont(_heading_font())
    painter.setPen(QColor(theme.PAPER.text))
    painter.drawText(_rect(left, y, width, 24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, _identity_line(watch))

    detail_parts = [p for p in (watch.reference, watch.nickname) if p]
    detail_line = " · ".join(detail_parts) if detail_parts else EM_DASH
    serial_line = f"Serial {watch.serial}" if watch.serial else None

    painter.setFont(_body_font())
    painter.setPen(QColor(theme.PAPER.text_muted))
    painter.drawText(_rect(left, y + 26, width, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, detail_line)
    if serial_line:
        painter.drawText(_rect(left, y + 42, width, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, serial_line)


def _draw_placeholder(painter: QPainter, left: float, top: float, width: float, height: float, watch: Watch) -> None:
    """The same informative, no-photo placeholder the grid card uses
    (saat.ui.cards._CardPlaceholder) -- a curved tick arc suggesting a
    dial's chapter ring, with the two most identifying case dimensions
    centred over it. Reimplemented rather than shared: the card's version
    is tuned for a fixed, roughly-4:3 widget size, this one is derived
    from whatever rect the PDF's photo block actually is."""
    painter.save()
    painter.setClipRect(_rect(left, top, width, height))
    # Centre sits inside the block, well above its lowest point, so the
    # visible sweep (the underside of a circle this large) crosses
    # roughly the block's middle rather than hugging its bottom edge --
    # tuned against this specific PHOTO_BLOCK_HEIGHT_PT-sized rect, not
    # copied from the grid card's own (much smaller, ~4:3) tile.
    center_pt = (left + width / 2, top + height * 0.15)
    radius_pt = height * 0.45
    span_degrees = 46
    tick_count = 26
    arc_steps = 48

    painter.setPen(QColor(theme.PAPER.rule))
    painter.setBrush(Qt.BrushStyle.NoBrush)

    def _arc_point_pt(theta: float) -> tuple[float, float]:
        return (center_pt[0] + math.sin(theta) * radius_pt, center_pt[1] + math.cos(theta) * radius_pt)

    arc_path = QPainterPath()
    for i in range(arc_steps + 1):
        theta = math.radians(-span_degrees / 2 + span_degrees * i / arc_steps)
        x_pt, y_pt = _arc_point_pt(theta)
        point = _point(x_pt, y_pt)
        if i == 0:
            arc_path.moveTo(point)
        else:
            arc_path.lineTo(point)
    painter.drawPath(arc_path)

    for i in range(tick_count + 1):
        theta = math.radians(-span_degrees / 2 + span_degrees * i / tick_count)
        direction = (math.sin(theta), math.cos(theta))
        tick_len_pt = 10 if i % 4 == 0 else 5
        outer_pt = (center_pt[0] + direction[0] * radius_pt, center_pt[1] + direction[1] * radius_pt)
        inner_pt = (
            center_pt[0] + direction[0] * (radius_pt - tick_len_pt),
            center_pt[1] + direction[1] * (radius_pt - tick_len_pt),
        )
        painter.drawLine(_point(*outer_pt), _point(*inner_pt))
    painter.restore()

    diameter = f"{watch.case.diameter_mm:g} mm" if watch.case.diameter_mm else EM_DASH
    lug = f"{watch.case.lug_width_mm} mm lugs" if watch.case.lug_width_mm else EM_DASH
    painter.setFont(_body_font())
    painter.setPen(QColor(theme.PAPER.text_muted))
    painter.drawText(_rect(left, top, width, height), Qt.AlignmentFlag.AlignCenter, f"{diameter}\n{lug}")


def _draw_photo_block(painter: QPainter, left: float, width: float, y: float, record: WatchRecord) -> None:
    image_path = first_image(record)
    pixmap = load_for_export(image_path) if image_path else None
    if pixmap is None:
        _draw_placeholder(painter, left, y, width, PHOTO_BLOCK_HEIGHT_PT, record.watch)
        return

    target_w, target_h = _px(width), _px(PHOTO_BLOCK_HEIGHT_PT)
    scaled = pixmap.scaled(
        int(target_w), int(target_h), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
    )
    x_px = _px(left) + (target_w - scaled.width()) / 2
    y_px = _px(y) + (target_h - scaled.height()) / 2
    painter.drawPixmap(QPointF(x_px, y_px), scaled)


def _draw_spec_rows(painter: QPainter, rows: list[SpecRow], left: float, width: float, y: float) -> None:
    label_width = width * 0.35
    value_width = width - label_width
    for row in rows:
        painter.setFont(_body_font())
        painter.setPen(QColor(theme.PAPER.text_muted))
        painter.drawText(_rect(left, y, label_width, LINE_HEIGHT_PT), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, row.label)

        painter.setFont(_mono_font() if row.numeric else _body_font())
        painter.setPen(QColor(theme.PAPER.text))
        painter.drawText(
            _rect(left + label_width, y, value_width, LINE_HEIGHT_PT),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            row.text,
        )
        y += LINE_HEIGHT_PT


def _draw_lines(painter: QPainter, lines: list[str], left: float, width: float, y: float) -> None:
    painter.setFont(_body_font())
    painter.setPen(QColor(theme.PAPER.text))
    for line in lines:
        painter.drawText(_rect(left, y, width, LINE_HEIGHT_PT), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, line)
        y += LINE_HEIGHT_PT


def _draw_group_slice(
    painter: QPainter, group_slice: GroupSlice, render_group: "_RenderGroup", left: float, width: float, y: float
) -> None:
    title = group_slice.title if group_slice.start_line == 0 else f"{group_slice.title} (continued)"
    painter.setFont(_label_font())
    painter.setPen(QColor(theme.PAPER.text_muted))
    painter.drawText(_rect(left, y, width, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title.upper())

    # draw_minute_track always starts its rule/ticks at x=0 in whatever
    # coordinate space it's given -- translate so "0" lands at this
    # content block's left margin rather than the physical page edge.
    # translate() is pure geometry (additive, not multiplicative like
    # scale()), so it doesn't have scale()'s font-double-sizing problem.
    painter.save()
    painter.translate(_px(left), 0)
    draw_minute_track(painter, int(_px(width)), int(_px(y + GROUP_HEADER_HEIGHT_PT - 2)), int(_px(5)), color=theme.PAPER.rule)
    painter.restore()

    body_y = y + GROUP_HEADER_HEIGHT_PT
    sliced_items = render_group.items[group_slice.start_line : group_slice.end_line]
    if render_group.kind == "spec":
        _draw_spec_rows(painter, sliced_items, left, width, body_y)
    else:
        _draw_lines(painter, sliced_items, left, width, body_y)


def _draw_watch_page(
    painter: QPainter,
    page: WatchPage,
    render_groups: list["_RenderGroup"],
    page_index: int,
    plan: ExportPlan,
    document_title: str,
    generation_date: str,
) -> None:
    left, top, width = _content_rect_pt(plan)
    y = top

    if page.is_first_page:
        _draw_photo_block(painter, left, width, y, page.record)
        y += PHOTO_BLOCK_HEIGHT_PT
        _draw_identity_block(painter, left, width, y, page.record.watch)
        y += IDENTITY_BLOCK_HEIGHT_PT

    groups_by_title = {g.title: g for g in render_groups}
    for group_slice in page.groups:
        render_group = groups_by_title[group_slice.title]
        _draw_group_slice(painter, group_slice, render_group, left, width, y)
        line_count = group_slice.end_line - group_slice.start_line
        y += GROUP_HEADER_HEIGHT_PT + line_count * LINE_HEIGHT_PT + GROUP_SPACING_PT

    _draw_page_furniture(painter, page_index, plan, document_title, generation_date)
