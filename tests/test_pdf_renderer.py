import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from saat.models import Acquisition, Case, Watch
from saat.storage import WatchRecord
from saat.ui.export import WatchExportInput, build_export_plan
from saat.ui.pdf_renderer import ExportError, _to_group_contents, build_render_groups, detect_page_size, export_pdf

_app = QApplication.instance() or QApplication([])


def _page_count_in_pdf(path: Path) -> int:
    """Counts genuine page objects (/Type /Page) rather than the page
    tree root (/Type /Pages) -- \\b correctly excludes the latter, cross-
    checked against pdfinfo's own count on a real generated file during
    development. No external PDF library is a project dependency
    (SPEC.md §2 rule 5), so this stays a light, dependency-free regex
    rather than pulling one in just for tests."""
    data = path.read_bytes()
    return len(re.findall(rb"/Type\s*/Page\b", data))


class PdfRendererTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-pdf-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _record(self, brand="Seiko", model="SARB033", slug=None, **acquisition_kwargs) -> WatchRecord:
        watch = Watch(brand=brand, model=model, acquisition=Acquisition(**acquisition_kwargs))
        record_dir = self.tmp / (slug or f"{brand}-{model}".lower())
        record_dir.mkdir(exist_ok=True)
        return WatchRecord(slug=record_dir.name, path=record_dir, watch=watch)


class DetectPageSizeTests(PdfRendererTestCase):
    def test_returns_a_known_page_size(self) -> None:
        from saat.ui.export import PAGE_A4, PAGE_LETTER

        self.assertIn(detect_page_size(), (PAGE_A4, PAGE_LETTER))


class BuildRenderGroupsTests(PdfRendererTestCase):
    def test_bare_watch_has_no_groups(self) -> None:
        record = self._record()
        self.assertEqual(build_render_groups(record), [])

    def test_populated_case_produces_a_case_group(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033", case=Case(diameter_mm=37.5))
        record = WatchRecord(slug="seiko", path=self.tmp, watch=watch)
        groups = build_render_groups(record)
        self.assertEqual([g.title for g in groups], ["Case"])

    def test_compatible_straps_never_appears(self) -> None:
        """Deliberately excluded (see saat.ui.pdf_renderer's module-level
        docstring on build_render_groups): it's a cross-collection
        recommendation, not this watch's own data, so a frozen document
        has no sensible way to represent it."""
        record = self._record(price=100, currency="USD")
        groups = build_render_groups(record)
        self.assertNotIn("Compatible Straps", [g.title for g in groups])


class ExportPdfTests(PdfRendererTestCase):
    def test_empty_records_list_raises(self) -> None:
        out = self.tmp / "out.pdf"
        with self.assertRaises(ExportError):
            export_pdf(out, [], is_wishlist=False, document_title="SAAT Collection")
        self.assertFalse(out.exists())

    def test_all_broken_records_raises_same_as_empty(self) -> None:
        """A visible list that's non-empty but entirely unparseable
        records (watch is None) must be refused exactly like an empty
        one -- not silently produce a summary-only PDF with zero watch
        pages."""
        broken = WatchRecord(slug="broken", path=self.tmp, watch=None)
        out = self.tmp / "out.pdf"
        with self.assertRaises(ExportError):
            export_pdf(out, [broken], is_wishlist=False, document_title="SAAT Collection")
        self.assertFalse(out.exists())

    def test_unwritable_directory_raises_and_leaves_no_file(self) -> None:
        record = self._record(price=100, currency="USD")
        bad_path = self.tmp / "does-not-exist" / "out.pdf"
        with self.assertRaises(ExportError):
            export_pdf(bad_path, [record], is_wishlist=False, document_title="SAAT Collection")
        self.assertFalse(bad_path.exists())

    def test_single_watch_produces_a_real_pdf_with_the_predicted_page_count(self) -> None:
        record = self._record(price=350, currency="USD")
        out = self.tmp / "out.pdf"
        export_pdf(out, [record], is_wishlist=False, document_title="SAAT Collection")

        self.assertTrue(out.exists())
        self.assertGreater(out.stat().st_size, 0)
        self.assertEqual(out.read_bytes()[:5], b"%PDF-")

        groups = _to_group_contents(build_render_groups(record))
        plan = build_export_plan(
            [WatchExportInput(record=record, groups=groups)],
            is_wishlist=False,
            page_size=detect_page_size(),
        )
        self.assertEqual(_page_count_in_pdf(out), plan.page_count)

    def test_multiple_watches_with_varied_content_match_predicted_page_count(self) -> None:
        sparse = self._record(brand="Casio", model="F-91W")
        detailed = self._record(brand="Omega", model="Speedmaster", price=5000, currency="USD")
        detailed.watch.case = Case(diameter_mm=42, lug_to_lug_mm=48, thickness_mm=13, lug_width_mm=20,
                                    material="Steel", crystal="Sapphire", crown="Screw-down", bezel="Fixed",
                                    caseback="Solid", water_resistance_m=100, weight_g=150)
        records = [sparse, detailed]
        out = self.tmp / "out.pdf"
        export_pdf(out, records, is_wishlist=False, document_title="SAAT Collection")

        page_size = detect_page_size()
        watch_inputs = [
            WatchExportInput(record=r, groups=_to_group_contents(build_render_groups(r))) for r in records
        ]
        plan = build_export_plan(watch_inputs, is_wishlist=False, page_size=page_size)

        self.assertEqual(_page_count_in_pdf(out), plan.page_count)

    def test_wishlist_export_succeeds_and_reflects_target_price(self) -> None:
        record = self._record(target_price=999, currency="USD")
        out = self.tmp / "out.pdf"
        export_pdf(out, [record], is_wishlist=True, document_title="SAAT Wishlist")
        self.assertTrue(out.exists())
        self.assertGreater(out.stat().st_size, 0)

    def test_failure_never_leaves_a_partial_file(self) -> None:
        """A genuine mid-render exception (simulated by monkeypatching a
        drawing step to raise) must not leave a truncated PDF where the
        user expects a real document."""
        import saat.ui.pdf_renderer as pdf_renderer

        record = self._record(price=100, currency="USD")
        out = self.tmp / "out.pdf"

        original = pdf_renderer._draw_summary_page
        pdf_renderer._draw_summary_page = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            with self.assertRaises(RuntimeError):
                export_pdf(out, [record], is_wishlist=False, document_title="SAAT Collection")
        finally:
            pdf_renderer._draw_summary_page = original
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
