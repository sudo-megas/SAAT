"""Pure logic only — no QPdfWriter, no QPainter, no event loop. Given a
watch collection (or wishlist) and a page size, decides which watch lands
on which page and how the summary table chunks across continuation pages
— nothing here draws a pixel. saat.ui.pdf_renderer turns this into an
actual PDF, the same split wear.py/saat.ui.compare established: unit
tested without an event loop, imported freely by files that also define
Qt widget classes. See SPEC.md §9.

The height model below (named pt constants) is deliberately the single
source of truth for both this module's page-count predictions and
saat.ui.pdf_renderer's actual drawing — the renderer advances by these same
constants rather than deriving its own from font metrics, so a predicted
page count is correct by construction, not an estimate that can drift
from what actually gets painted."""

import textwrap
from dataclasses import dataclass

from saat.storage import WatchRecord
from saat.ui.collection_summary import compute_collection_summary, compute_wishlist_summary
from saat.ui.formatting import EM_DASH, fmt_price

PAGE_A4 = "A4"
PAGE_LETTER = "Letter"

# Point (1/72in) page dimensions -- independent of whatever DPI the renderer
# actually draws at. Standard ISO 216 / ANSI sizes.
_PAGE_DIMENSIONS_PT = {
    PAGE_A4: (595.28, 841.89),
    PAGE_LETTER: (612.0, 792.0),
}

PAGE_MARGIN_PT = 48.0
FOOTER_HEIGHT_PT = 24.0  # "n of N" / generation date / document title, every page

TITLE_BLOCK_HEIGHT_PT = 100.0  # title + generation date + item count/value totals, first summary page only
SUMMARY_HEADER_HEIGHT_PT = 20.0  # compact table's column header row, every summary page
SUMMARY_ROW_HEIGHT_PT = 16.0

IDENTITY_BLOCK_HEIGHT_PT = 70.0  # brand/model/reference/nickname/serial, first page of a watch only
# Started at 260 (visually verified against a rendered PDF): a normally-
# detailed watch (Movement+Case+Dial+Acquisition, all fixed-length
# whenever shown at all per SPEC.md §4 -- 34 lines before Straps/
# Maintenance/Log/Timing/Notes even enter the picture) already asks for
# roughly 640pt against a ~670-720pt usable page height, so a 260pt photo
# block left the first page holding a single group and read as padding.
# 180pt keeps the photo genuinely prominent (2.5in on Letter) while
# leaving room for two or three groups on a watch's first page.
PHOTO_BLOCK_HEIGHT_PT = 180.0  # primary photo or its placeholder, first page of a watch only
GROUP_HEADER_HEIGHT_PT = 22.0  # a minute-track section header
GROUP_SPACING_PT = 12.0  # gap after a group, before the next
LINE_HEIGHT_PT = 15.0  # one spec row / log entry / timing entry / wrapped notes line

NOTES_CHARS_PER_LINE = 92


def page_dimensions_pt(page_size: str) -> tuple[float, float]:
    return _PAGE_DIMENSIONS_PT[page_size]


def usable_height_pt(page_size: str) -> float:
    """Content height available on any page after margins top and bottom
    and the footer's reserved strip -- the budget every page's content,
    summary or per-watch, must fit within."""
    _, height = page_dimensions_pt(page_size)
    return height - 2 * PAGE_MARGIN_PT - FOOTER_HEIGHT_PT


def wrap_notes(notes: str, chars_per_line: int = NOTES_CHARS_PER_LINE) -> list[str]:
    """Splits on existing newlines before wrapping each paragraph --
    textwrap.wrap() alone collapses blank lines, reflowing a multi-
    paragraph note into one blob. The renderer draws exactly these lines,
    one drawText() per line, rather than handing the whole string to Qt's
    own word-wrap (which wraps by measured pixel width and could
    legitimately produce a different line count) -- so the count used for
    pagination and the lines actually painted can never disagree."""
    if not notes or not notes.strip():
        return []
    lines: list[str] = []
    for paragraph in notes.split("\n"):
        if not paragraph.strip():
            lines.append("")
        else:
            lines.extend(textwrap.wrap(paragraph, chars_per_line))
    return lines


@dataclass(frozen=True)
class GroupContent:
    """What pagination needs to know about one non-empty spec group on a
    watch page: its title and how many lines it takes. Never the actual
    row text -- the renderer (saat.ui.pdf_renderer) computes real rows
    exactly once per watch and derives this count from that same
    computation, so what gets counted here and what gets drawn are
    guaranteed to be the same lines, not two independent derivations."""

    title: str
    line_count: int


@dataclass(frozen=True)
class WatchExportInput:
    record: WatchRecord
    groups: list[GroupContent]  # non-empty groups only, already in model order


@dataclass(frozen=True)
class GroupSlice:
    """One page's worth of one group: rows [start_line, end_line) of that
    group's content. The overwhelmingly common case is one slice covering
    a whole group (start_line=0, end_line=line_count) -- a slice narrower
    than the full group only appears when the group alone is taller than
    a full page (see _split_oversized_group), e.g. a long pasted Notes
    entry. start_line > 0 tells the renderer this is a continuation, not
    the group's beginning."""

    title: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class WatchPage:
    record: WatchRecord
    groups: list[GroupSlice]
    is_first_page: bool  # only the first physical page for a watch shows the photo + identity header


@dataclass(frozen=True)
class SummaryRow:
    brand: str
    model: str
    reference: str
    serial: str
    value_text: str


@dataclass(frozen=True)
class SummaryPage:
    rows: list[SummaryRow]


ExportPage = SummaryPage | WatchPage


@dataclass(frozen=True)
class ExportPlan:
    pages: list[ExportPage]
    page_size: str
    item_count: int
    value_by_currency: list[tuple[str, float]]  # (currency, total), sorted -- price if collection, target_price if wishlist

    @property
    def page_count(self) -> int:
        return len(self.pages)


def _value_text(watch, is_wishlist: bool) -> str:
    amount = watch.acquisition.target_price if is_wishlist else watch.acquisition.price
    if amount is None:
        return EM_DASH
    return fmt_price((amount, watch.acquisition.currency or ""))


def build_summary_rows(records: list[WatchRecord], is_wishlist: bool) -> list[SummaryRow]:
    """A broken record (watch is None, an unparseable watch.toml) has no
    field to summarise and is skipped -- the same defensive filter
    build_export_plan applies before building per-watch pages, so a
    caller can pass a records list that hasn't itself been filtered."""
    rows = []
    for record in records:
        if record.watch is None:
            continue
        w = record.watch
        rows.append(
            SummaryRow(
                brand=w.brand,
                model=w.model,
                reference=w.reference or EM_DASH,
                serial=w.serial or EM_DASH,
                value_text=_value_text(w, is_wishlist),
            )
        )
    return rows


def paginate_summary(rows: list[SummaryRow], page_size: str) -> list[SummaryPage]:
    """The title/date/totals block only reserves space on the first
    summary page; continuation pages are table rows only, so they hold
    more rows than the first."""
    if not rows:
        return []
    usable = usable_height_pt(page_size)
    first_capacity = max(1, int((usable - TITLE_BLOCK_HEIGHT_PT - SUMMARY_HEADER_HEIGHT_PT) // SUMMARY_ROW_HEIGHT_PT))
    continuation_capacity = max(1, int((usable - SUMMARY_HEADER_HEIGHT_PT) // SUMMARY_ROW_HEIGHT_PT))

    pages = []
    remaining = rows
    capacity = first_capacity
    while remaining:
        chunk, remaining = remaining[:capacity], remaining[capacity:]
        pages.append(SummaryPage(rows=chunk))
        capacity = continuation_capacity
    return pages


def _group_height_pt(title: str, line_count: int) -> float:
    return GROUP_HEADER_HEIGHT_PT + line_count * LINE_HEIGHT_PT + GROUP_SPACING_PT


def _split_oversized_group(group: GroupContent, max_lines_per_page: int) -> list[GroupSlice]:
    slices = []
    start = 0
    while start < group.line_count:
        end = min(start + max_lines_per_page, group.line_count)
        slices.append(GroupSlice(group.title, start, end))
        start = end
    return slices


def paginate_watch(watch_input: WatchExportInput, page_size: str) -> list[WatchPage]:
    """Groups flow onto the current page until one doesn't fit, at which
    point it moves to a fresh page whole -- never split mid-group -- with
    one exception: a single group too tall for even a fresh page on its
    own (an extended Notes entry, most plausibly) is split at a line
    boundary rather than overflowing past the footer. Every watch starts
    its own fresh page; its content is never packed onto the tail end of
    the previous watch's last page. A watch with no populated groups at
    all (brand and model only) still gets exactly one, short, page."""
    usable = usable_height_pt(page_size)
    first_page_budget = usable - IDENTITY_BLOCK_HEIGHT_PT - PHOTO_BLOCK_HEIGHT_PT

    pages: list[list[GroupSlice]] = []
    current: list[GroupSlice] = []
    remaining = first_page_budget

    def start_new_page() -> None:
        nonlocal current, remaining
        pages.append(current)
        current = []
        remaining = usable

    for group in watch_input.groups:
        height = _group_height_pt(group.title, group.line_count)

        if height <= remaining:
            current.append(GroupSlice(group.title, 0, group.line_count))
            remaining -= height
        elif height <= usable:
            start_new_page()
            current.append(GroupSlice(group.title, 0, group.line_count))
            remaining -= height
        else:
            max_lines = max(1, int((usable - GROUP_HEADER_HEIGHT_PT - GROUP_SPACING_PT) // LINE_HEIGHT_PT))
            for group_slice in _split_oversized_group(group, max_lines):
                start_new_page()
                current.append(group_slice)
                remaining -= _group_height_pt(group.title, group_slice.end_line - group_slice.start_line)

    pages.append(current)  # the last page accumulated -- [] for a watch with no populated groups

    return [
        WatchPage(record=watch_input.record, groups=slices, is_first_page=(i == 0))
        for i, slices in enumerate(pages)
    ]


def build_export_plan(watch_inputs: list[WatchExportInput], is_wishlist: bool, page_size: str) -> ExportPlan:
    """watch_inputs drives both the summary table (one row per watch) and
    the one-page-per-watch section that follows it, in the same order --
    a single list in, so the two can never fall out of sync with each
    other. Line counts inside each WatchExportInput come from the
    Qt-aware row-builders in saat.ui.detail_view and saat.ui.pdf_renderer,
    which this module never imports. item_count/value_by_currency reuse
    saat.ui.collection_summary's existing, already-Qt-free aggregation
    (the same figures the on-screen sidebar footer shows) rather than a
    second computation of the same totals."""
    records = [wi.record for wi in watch_inputs]
    summary_rows = build_summary_rows(records, is_wishlist)
    pages: list[ExportPage] = list(paginate_summary(summary_rows, page_size))
    for watch_input in watch_inputs:
        pages.extend(paginate_watch(watch_input, page_size))

    if is_wishlist:
        aggregate = compute_wishlist_summary(records)
        value_by_currency = aggregate.target_value_by_currency
    else:
        aggregate = compute_collection_summary(records)
        value_by_currency = aggregate.value_by_currency

    return ExportPlan(
        pages=pages,
        page_size=page_size,
        item_count=aggregate.total,
        value_by_currency=value_by_currency,
    )
