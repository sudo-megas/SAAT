import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtWidgets import QApplication

from saat.config import Config
from saat.models import Acquisition, Case, Movement, Watch
from saat.storage import WatchRecord, create_watch, load_collection
from saat.ui import theme
from saat.ui.collection_view import CollectionView
from saat.ui.columns import DEFAULT_COLUMN_KEYS
from saat.ui.i18n import install_language, uninstall_language
from saat.ui.table_view import TableView
from saat.ui.top_bar import VIEW_TABLE

_app = QApplication.instance() or QApplication([])


class TableViewSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-table-selection-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="A"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="B"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="C"))
        self.records = load_collection(self.watches_dir)
        self.table = TableView(on_columns_changed=lambda keys: None)
        self.table.set_columns(DEFAULT_COLUMN_KEYS)
        self.table.set_records(self.records)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_selection_initially(self) -> None:
        self.assertEqual(self.table.selected_slugs(), set())

    def test_selecting_a_row_directly_reflects_in_selected_slugs(self) -> None:
        # selectRow() replaces the selection outright, even under
        # ExtendedSelection — verified empirically; real multi-row selection
        # (ctrl/shift-click) is exercised through set_selected_slugs() below.
        self.table.selectRow(0)
        self.assertEqual(self.table.selected_slugs(), {self.records[0].slug})

    def test_set_selected_slugs_selects_the_matching_rows(self) -> None:
        target = {self.records[1].slug}
        self.table.set_selected_slugs(target)
        self.assertEqual(self.table.selected_slugs(), target)

    def test_set_selected_slugs_does_not_emit_selection_changed(self) -> None:
        received = []
        self.table.selection_changed.connect(received.append)
        self.table.set_selected_slugs({self.records[0].slug})
        self.assertEqual(received, [])

    def test_a_real_selection_change_emits_selection_changed_with_the_slug_set(self) -> None:
        received = []
        self.table.selection_changed.connect(received.append)
        self.table.selectRow(0)
        self.assertEqual(received, [{self.records[0].slug}])

    def test_set_selected_slugs_replaces_rather_than_accumulates(self) -> None:
        self.table.set_selected_slugs({self.records[0].slug})
        self.table.set_selected_slugs({self.records[1].slug})
        self.assertEqual(self.table.selected_slugs(), {self.records[1].slug})


TS_PATH = Path(__file__).resolve().parent.parent / "saat" / "resources" / "i18n" / "saat_tr.ts"


def _find_lrelease() -> str | None:
    venv_candidate = Path(sys.prefix) / "bin" / "pyside6-lrelease"
    if venv_candidate.exists():
        return str(venv_candidate)
    return shutil.which("pyside6-lrelease")


LRELEASE = _find_lrelease()

_BRANDS = ["Seiko", "Omega", "Casio", "Rolex", "Tudor", "Nomos", "Cartier", "Longines"]
_MODELS = [
    "SARB033", "Speedmaster Professional Moonwatch", "F-91W", "Submariner Date",
    "Black Bay Fifty-Eight", "Club Campus", "Tank Must", "Master Collection",
]
_STYLES = ["Diver", "Pilot", "Dress", "Sport", "Field", "Chronograph"]
_MOVEMENT_KINDS = ["Automatic", "Manual", "Automatic + Handwinding", "Quartz", "Solar"]
_WATER_RESISTANCES = [30, 50, 100, 200, 300]


def _synthetic_records(count: int) -> list[WatchRecord]:
    """Records built directly (test_retranslation.py's _make_record()
    precedent), not through create_watch()+load_collection() -- no real
    file I/O needed since this is testing table layout, not persistence,
    and the thumbnail delegate degrades to "no image" cleanly for a
    record.path that doesn't exist on disk. Varied, realistic-length
    values across every default column (including "Automatic +
    Handwinding", the longest real movement-kind value) rather than a
    table full of em-dashes, which would understate real-world width."""
    records = []
    for i in range(count):
        watch = Watch(
            brand=_BRANDS[i % len(_BRANDS)],
            model=f"{_MODELS[i % len(_MODELS)]} {i}",
            reference=f"REF-{1000 + i}",
            style=_STYLES[i % len(_STYLES)],
            movement=Movement(kind=_MOVEMENT_KINDS[i % len(_MOVEMENT_KINDS)]),
            case=Case(
                diameter_mm=float(36 + i % 9),
                lug_width_mm=18 + i % 5,
                water_resistance_m=_WATER_RESISTANCES[i % len(_WATER_RESISTANCES)],
            ),
            acquisition=Acquisition(date=date(2020, 1, 1) + timedelta(days=i * 17)),
        )
        records.append(WatchRecord(slug=f"watch-{i}", path=Path(f"/tmp/does-not-exist-{i}"), watch=watch, load_error=None))
    return records


class TableViewNoHorizontalScrollAt1100Tests(unittest.TestCase):
    """SPEC.md §5 (milestone 21b): no horizontal scrollbar in the table at
    the documented 1100x700 minimum, in any shipped language -- the known
    bug this commit closes, worse in Turkish (longer translated labels).
    Built against a real CollectionView, not a bare TableView: the 260px
    sidebar (SIDEBAR_WIDTH, expanded by default) is what actually eats
    into the table's real available width at that floor, so a bare
    TableView sized to 1100 would get the full 1100px and pass vacuously.
    >=30 records force a real vertical scrollbar, so viewport().width()
    reflects what a real, longer collection actually gets rather than the
    few extra pixels a short list would leave it.

    Checked against both default palettes even though column widths don't
    read from palette colours at all (only from theme.py's palette-
    independent SIZE_*/CARD_PADDING-style constants) -- an explicit
    regression guard against that independence claim, the same exhaustive-
    combination style test_theme_contrast.py already uses throughout,
    rather than trusting the reasoning unverified."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-table-width-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.addCleanup(theme.set_palette, "default-dark")
        self.records = _synthetic_records(30)

    def _config(self) -> Config:
        return Config(self.tmp / "config.toml")

    def _assert_no_horizontal_scroll(self) -> None:
        view = CollectionView(self.records, self._config())
        self.addCleanup(view.deleteLater)
        view._top_bar.set_view(VIEW_TABLE)
        view.resize(1100, 700)
        view.show()
        _app.processEvents()

        table = view._table_view
        self.assertFalse(
            table.horizontalScrollBar().isVisible(),
            f"horizontal scrollbar visible: header length={table.horizontalHeader().length()}, "
            f"viewport width={table.viewport().width()}",
        )
        # Belt and suspenders (item 31's own point): ScrollBarAlwaysOff
        # would also make isVisible() false while silently clipping
        # content instead of fitting it -- this second assertion is what
        # actually distinguishes "fits" from "clips."
        self.assertLessEqual(table.horizontalHeader().length(), table.viewport().width())
        view.hide()

    def test_default_columns_fit_at_1100_english_dark(self) -> None:
        theme.set_palette("default-dark")
        self._assert_no_horizontal_scroll()

    def test_default_columns_fit_at_1100_english_light(self) -> None:
        theme.set_palette("default-light")
        self._assert_no_horizontal_scroll()

    @unittest.skipUnless(LRELEASE, "pyside6-lrelease not found -- install PySide6 to run this test")
    def test_default_columns_fit_at_1100_turkish_dark(self) -> None:
        qm_path = TS_PATH.parent / "saat_tr.qm"
        if not qm_path.exists():
            subprocess.run([LRELEASE, str(TS_PATH), "-qm", str(qm_path)], check=True, capture_output=True)
            self.addCleanup(qm_path.unlink, missing_ok=True)
        self.assertTrue(install_language(_app, "tr"))
        self.addCleanup(uninstall_language, _app)

        theme.set_palette("default-dark")
        self._assert_no_horizontal_scroll()

    @unittest.skipUnless(LRELEASE, "pyside6-lrelease not found -- install PySide6 to run this test")
    def test_default_columns_fit_at_1100_turkish_light(self) -> None:
        qm_path = TS_PATH.parent / "saat_tr.qm"
        if not qm_path.exists():
            subprocess.run([LRELEASE, str(TS_PATH), "-qm", str(qm_path)], check=True, capture_output=True)
            self.addCleanup(qm_path.unlink, missing_ok=True)
        self.assertTrue(install_language(_app, "tr"))
        self.addCleanup(uninstall_language, _app)

        theme.set_palette("default-light")
        self._assert_no_horizontal_scroll()


if __name__ == "__main__":
    unittest.main()
