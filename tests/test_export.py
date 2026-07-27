import unittest
from pathlib import Path

from saat.models import Acquisition, Watch
from saat.storage import WatchRecord
from saat.ui.export import (
    FOOTER_HEIGHT_PT,
    GROUP_HEADER_HEIGHT_PT,
    GROUP_SPACING_PT,
    IDENTITY_BLOCK_HEIGHT_PT,
    LINE_HEIGHT_PT,
    PAGE_A4,
    PAGE_LETTER,
    PHOTO_BLOCK_HEIGHT_PT,
    SUMMARY_HEADER_HEIGHT_PT,
    TITLE_BLOCK_HEIGHT_PT,
    ExportPlan,
    GroupContent,
    SummaryPage,
    WatchExportInput,
    WatchPage,
    build_export_plan,
    build_summary_rows,
    paginate_summary,
    paginate_watch,
    usable_height_pt,
    wrap_notes,
)
from saat.ui.formatting import EM_DASH

# saat.ui.export never imports PySide6, so importing it (module scope,
# above) never touches Qt -- there is nothing here to set QT_QPA_PLATFORM
# for, unlike every other test module in this project.


def _record(brand="Seiko", model="SARB033", **acquisition_kwargs) -> WatchRecord:
    watch = Watch(brand=brand, model=model, acquisition=Acquisition(**acquisition_kwargs))
    return WatchRecord(slug=f"{brand}-{model}".lower(), path=Path("/nonexistent"), watch=watch)


class WrapNotesTests(unittest.TestCase):
    def test_empty_string_wraps_to_no_lines(self) -> None:
        self.assertEqual(wrap_notes(""), [])

    def test_whitespace_only_wraps_to_no_lines(self) -> None:
        self.assertEqual(wrap_notes("   \n  \n"), [])

    def test_short_line_is_one_line(self) -> None:
        self.assertEqual(wrap_notes("Bought at a boutique in Tokyo."), ["Bought at a boutique in Tokyo."])

    def test_long_paragraph_wraps_to_multiple_lines_at_the_chosen_width(self) -> None:
        paragraph = "word " * 40  # far longer than any reasonable chars_per_line
        lines = wrap_notes(paragraph, chars_per_line=20)
        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertLessEqual(len(line), 20)

    def test_blank_line_between_paragraphs_is_preserved_not_collapsed(self) -> None:
        """textwrap.wrap() alone collapses "\\n\\n" into one reflowed blob
        -- the whole reason wrap_notes splits on newlines first."""
        lines = wrap_notes("First paragraph.\n\nSecond paragraph.")
        self.assertEqual(lines, ["First paragraph.", "", "Second paragraph."])

    def test_renderer_draws_exactly_these_lines_no_hidden_pixel_based_rewrap(self) -> None:
        """The count returned here is what pagination bills the page for;
        the renderer must draw this exact list, not re-wrap independently
        with Qt's TextWordWrap (which measures by pixel width and could
        legitimately disagree on where a line breaks)."""
        lines = wrap_notes("A watch bought secondhand, serviced once since.", chars_per_line=15)
        recombined = " ".join(line for line in lines if line)
        self.assertEqual(recombined, "A watch bought secondhand, serviced once since.")


class BuildSummaryRowsTests(unittest.TestCase):
    def test_owned_watch_uses_price_not_target_price(self) -> None:
        record = _record(price=350, currency="USD", target_price=999, target_date=None)
        rows = build_summary_rows([record], is_wishlist=False)
        self.assertIn("350.00 USD", rows[0].value_text)

    def test_wishlist_watch_uses_target_price_not_price(self) -> None:
        record = _record(price=350, currency="USD", target_price=999)
        rows = build_summary_rows([record], is_wishlist=True)
        self.assertIn("999.00 USD", rows[0].value_text)

    def test_missing_relevant_price_renders_em_dash(self) -> None:
        record = _record()
        rows = build_summary_rows([record], is_wishlist=False)
        self.assertEqual(rows[0].value_text, EM_DASH)

    def test_missing_reference_and_serial_render_em_dash(self) -> None:
        record = _record()
        rows = build_summary_rows([record], is_wishlist=False)
        self.assertEqual(rows[0].reference, EM_DASH)
        self.assertEqual(rows[0].serial, EM_DASH)

    def test_broken_record_with_no_watch_is_skipped(self) -> None:
        broken = WatchRecord(slug="broken", path=Path("/nonexistent"), watch=None)
        good = _record()
        rows = build_summary_rows([broken, good], is_wishlist=False)
        self.assertEqual(len(rows), 1)


class PaginateSummaryTests(unittest.TestCase):
    def test_empty_rows_produce_no_pages(self) -> None:
        self.assertEqual(paginate_summary([], PAGE_A4), [])

    def test_a_handful_of_rows_fit_on_one_page(self) -> None:
        rows = build_summary_rows([_record() for _ in range(5)], is_wishlist=False)
        pages = paginate_summary(rows, PAGE_A4)
        self.assertEqual(len(pages), 1)
        self.assertEqual(len(pages[0].rows), 5)

    def test_enough_rows_force_a_continuation_page(self) -> None:
        rows = build_summary_rows([_record(brand=f"Brand{i}") for i in range(200)], is_wishlist=False)
        pages = paginate_summary(rows, PAGE_A4)
        self.assertGreater(len(pages), 1)

    def test_first_page_holds_fewer_rows_than_a_continuation_page(self) -> None:
        """The title/date/totals block only reserves space on page one."""
        rows = build_summary_rows([_record(brand=f"Brand{i}") for i in range(200)], is_wishlist=False)
        pages = paginate_summary(rows, PAGE_A4)
        self.assertLess(len(pages[0].rows), len(pages[1].rows))

    def test_every_row_is_preserved_across_pages_in_order(self) -> None:
        records = [_record(brand=f"Brand{i}") for i in range(150)]
        rows = build_summary_rows(records, is_wishlist=False)
        pages = paginate_summary(rows, PAGE_A4)
        recombined = [row for page in pages for row in page.rows]
        self.assertEqual(recombined, rows)


class PaginateWatchTests(unittest.TestCase):
    def test_watch_with_only_brand_and_model_gets_one_short_page(self) -> None:
        """A sparse watch (no populated spec groups at all) still gets
        exactly one page -- short, not empty. Whether this watch has a
        photo or needs the grid-card-style placeholder doesn't change
        this: SPEC.md's placeholder reserves the exact same
        PHOTO_BLOCK_HEIGHT_PT a real photo would, so pagination has
        nothing to branch on either way -- only saat.ui.pdf_export's
        drawing step (which image to paint, if any) differs."""
        watch_input = WatchExportInput(record=_record(), groups=[])
        pages = paginate_watch(watch_input, PAGE_A4)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].groups, [])
        self.assertTrue(pages[0].is_first_page)

    def test_a_single_watch_with_a_few_small_groups_fits_one_page(self) -> None:
        # A lightly-documented watch: only Movement and Dial have any data
        # at all (Case, Acquisition etc. are entirely empty and so already
        # excluded from watch_input.groups by the caller, same as
        # build_spec_group's own all-em-dash hide rule). Movement and Dial
        # are fixed-length whenever shown at all (every known field gets a
        # row, blank or not, per SPEC.md §4) -- 9 and 5 lines respectively,
        # comfortably inside the first page's budget alongside the photo
        # and identity header.
        groups = [GroupContent("Movement", 9), GroupContent("Dial", 5)]
        watch_input = WatchExportInput(record=_record(), groups=groups)
        pages = paginate_watch(watch_input, PAGE_A4)
        self.assertEqual(len(pages), 1)
        self.assertEqual([g.title for g in pages[0].groups], ["Movement", "Dial"])

    def test_enough_groups_force_a_continuation_page_with_no_group_split_mid_page(self) -> None:
        # Nine groups, each individually small but collectively too tall
        # for one page's budget alongside the photo + identity header.
        groups = [GroupContent(f"Group{i}", 12) for i in range(9)]
        watch_input = WatchExportInput(record=_record(), groups=groups)
        pages = paginate_watch(watch_input, PAGE_A4)
        self.assertGreater(len(pages), 1)
        self.assertTrue(pages[0].is_first_page)
        self.assertTrue(all(not p.is_first_page for p in pages[1:]))
        # Every group appears exactly once, as a single whole slice --
        # never split across the page boundary this test forces.
        seen_titles = [gs.title for page in pages for gs in page.groups]
        self.assertEqual(sorted(seen_titles), sorted(g.title for g in groups))
        for page in pages:
            for group_slice in page.groups:
                original = next(g for g in groups if g.title == group_slice.title)
                self.assertEqual((group_slice.start_line, group_slice.end_line), (0, original.line_count))

    def test_oversized_single_group_splits_at_a_line_boundary_across_pages(self) -> None:
        """A group taller than a full page on its own (e.g. a long pasted
        Notes entry) must not overflow past the footer -- it splits, but
        only at a line boundary, never mid-line."""
        huge = GroupContent("Notes", line_count=500)
        watch_input = WatchExportInput(record=_record(), groups=[huge])
        pages = paginate_watch(watch_input, PAGE_A4)
        self.assertGreater(len(pages), 1)

        slices = [gs for page in pages for gs in page.groups]
        # Contiguous, non-overlapping, and covers the whole group exactly once.
        self.assertEqual(slices[0].start_line, 0)
        self.assertEqual(slices[-1].end_line, 500)
        for a, b in zip(slices, slices[1:]):
            self.assertEqual(a.end_line, b.start_line)

        usable = usable_height_pt(PAGE_A4)
        for group_slice in slices:
            line_count = group_slice.end_line - group_slice.start_line
            height = GROUP_HEADER_HEIGHT_PT + line_count * LINE_HEIGHT_PT + GROUP_SPACING_PT
            self.assertLessEqual(height, usable)

    def test_letter_page_produces_a_valid_plan_too(self) -> None:
        groups = [GroupContent("Movement", 9)]
        watch_input = WatchExportInput(record=_record(), groups=groups)
        pages = paginate_watch(watch_input, PAGE_LETTER)
        self.assertEqual(len(pages), 1)


class BuildExportPlanTests(unittest.TestCase):
    def test_empty_collection_produces_an_empty_plan(self) -> None:
        plan = build_export_plan([], is_wishlist=False, page_size=PAGE_A4)
        self.assertEqual(plan.page_count, 0)
        self.assertEqual(plan.pages, [])

    def test_single_watch_produces_a_summary_page_and_one_watch_page(self) -> None:
        watch_input = WatchExportInput(record=_record(), groups=[GroupContent("Movement", 3)])
        plan = build_export_plan([watch_input], is_wishlist=False, page_size=PAGE_A4)
        self.assertEqual(plan.page_count, 2)
        self.assertIsInstance(plan.pages[0], SummaryPage)
        self.assertIsInstance(plan.pages[1], WatchPage)

    def test_summary_pages_precede_every_watch_page_in_input_order(self) -> None:
        inputs = [
            WatchExportInput(record=_record(brand="A"), groups=[]),
            WatchExportInput(record=_record(brand="B"), groups=[]),
        ]
        plan = build_export_plan(inputs, is_wishlist=False, page_size=PAGE_A4)
        watch_pages = [p for p in plan.pages if isinstance(p, WatchPage)]
        self.assertEqual([p.record.watch.brand for p in watch_pages], ["A", "B"])
        first_watch_index = next(i for i, p in enumerate(plan.pages) if isinstance(p, WatchPage))
        self.assertTrue(all(isinstance(p, SummaryPage) for p in plan.pages[:first_watch_index]))

    def test_page_count_matches_len_pages(self) -> None:
        inputs = [WatchExportInput(record=_record(brand=f"B{i}"), groups=[]) for i in range(3)]
        plan = build_export_plan(inputs, is_wishlist=False, page_size=PAGE_A4)
        self.assertEqual(plan.page_count, len(plan.pages))


if __name__ == "__main__":
    unittest.main()
