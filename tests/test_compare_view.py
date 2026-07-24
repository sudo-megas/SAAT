import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from saat.models import Case, Watch
from saat.storage import create_watch, load_collection
from saat.ui.case_silhouette import _TopDownSilhouette
from saat.ui.compare_view import CompareView, _ColorSwatchBar
from saat.ui.dimension_bars import _DimensionBarCell
from saat.ui.minute_track import MinuteTrackHeader
from saat.ui.year_view import slug_color

_app = QApplication.instance() or QApplication([])


class CompareViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-compare-view-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_shows_one_header_per_watch(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Casio", model="F-91W"))
        records = load_collection(self.watches_dir)

        view = CompareView(records)
        titles = [label.text() for label in view.findChildren(QLabel) if label.property("class") == "detail-title"]
        self.assertEqual(sorted(titles), ["F-91W", "SARB033"])

    def test_back_requested_signal_emits(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Casio", model="F-91W"))
        records = load_collection(self.watches_dir)

        view = CompareView(records)
        received = []
        view.back_requested.connect(lambda: received.append(True))
        view.findChild(QPushButton, "back-button").click()
        self.assertEqual(received, [True])

    def test_agreeing_row_is_muted_and_differing_row_is_not(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="A", case=Case(diameter_mm=38)))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="B", case=Case(diameter_mm=42)))
        records = load_collection(self.watches_dir)

        view = CompareView(records)
        labels = view.findChildren(QLabel)
        brand_values = [l for l in labels if l.text() == "Seiko" and l.property("class") == "spec-row-value"]
        self.assertTrue(all(l.property("muted") for l in brand_values))

        diameter_values = [l for l in labels if l.property("class") == "spec-row-value-mono" and "mm" in l.text()]
        self.assertTrue(any(not l.property("muted") for l in diameter_values))

    def test_group_headers_render_for_non_empty_groups(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="A", case=Case(diameter_mm=38)))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Casio", model="B", case=Case(diameter_mm=40)))
        records = load_collection(self.watches_dir)

        view = CompareView(records)
        titles = {h._title for h in view.findChildren(MinuteTrackHeader)}
        self.assertIn("IDENTITY", titles)
        self.assertIn("CASE", titles)

    def test_works_with_four_watches(self) -> None:
        for i in range(4):
            create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model=f"M{i}"))
        records = load_collection(self.watches_dir)
        view = CompareView(records)  # must not raise
        titles = [label.text() for label in view.findChildren(QLabel) if label.property("class") == "detail-title"]
        self.assertEqual(len(titles), 4)

    def test_each_column_header_carries_a_swatch_in_its_own_slug_colour(self) -> None:
        """SPEC.md M15 groundwork: links the table's headers to the visuals
        above it (case silhouette, accuracy ranges, dimension bars), all of
        which use the same per-watch slug_color()."""
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="A"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Casio", model="B"))
        records = load_collection(self.watches_dir)

        view = CompareView(records)
        swatches = view.findChildren(_ColorSwatchBar)
        self.assertEqual(len(swatches), 2)
        self.assertEqual({s._slug for s in swatches}, {r.slug for r in records})
        for swatch in swatches:
            swatch.resize(40, 4)
            swatch.show()
        QApplication.processEvents()
        for swatch in swatches:
            image = swatch.grab().toImage()
            self.assertEqual(image.pixelColor(5, 2).name(), slug_color(swatch._slug).name())

    def test_case_silhouette_section_appears_when_two_watches_have_diameter(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="A", case=Case(diameter_mm=38)))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Casio", model="B", case=Case(diameter_mm=42)))
        records = load_collection(self.watches_dir)

        view = CompareView(records)
        self.assertEqual(len(view.findChildren(_TopDownSilhouette)), 1)

    def test_case_silhouette_section_absent_when_no_watch_has_case_data(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="A"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Casio", model="B"))
        records = load_collection(self.watches_dir)

        view = CompareView(records)
        self.assertEqual(view.findChildren(_TopDownSilhouette), [])

    def test_dimension_bars_section_appears_when_two_watches_share_a_bar_eligible_attribute(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="A", case=Case(weight_g=120)))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Casio", model="B", case=Case(weight_g=90)))
        records = load_collection(self.watches_dir)

        view = CompareView(records)
        self.assertEqual(len(view.findChildren(_DimensionBarCell)), 2)

    def test_dimension_bars_section_absent_when_nothing_qualifies(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="A"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Casio", model="B"))
        records = load_collection(self.watches_dir)

        view = CompareView(records)
        self.assertEqual(view.findChildren(_DimensionBarCell), [])


if __name__ == "__main__":
    unittest.main()
