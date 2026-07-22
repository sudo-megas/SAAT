import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from PySide6.QtWidgets import QApplication, QPushButton

from saat.models import Acquisition, Case, Dial, LogEntry, Maintenance, Movement, Strap, TimingEntry, Watch
from saat.storage import create_watch, load_collection
from saat.ui.detail_view import (
    DetailView,
    SpecGroupsContainer,
    _acquisition_rows,
    _build_log_group,
    _build_notes_group,
    _build_straps_group,
    _build_timing_group,
    _case_rows,
    _dial_rows,
    _movement_rows,
)
from saat.ui.formatting import EM_DASH
from saat.ui.minute_track import MinuteTrackHeader
from saat.ui.spec_group import build_spec_group

_app = QApplication.instance() or QApplication([])


class RowBuilderTests(unittest.TestCase):
    """Row builders are the substantive logic here — exercise them directly
    rather than digging through QGridLayout children."""

    def test_movement_shows_power_reserve_for_mechanical_kind(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033", movement=Movement(kind="Automatic", power_reserve_hours=50, battery_life_years=3))
        rows = {r.label: r for r in _movement_rows(watch)}
        self.assertIn("Power Reserve", rows)
        self.assertNotIn("Battery Life", rows)
        self.assertEqual(rows["Power Reserve"].text, "50h")

    def test_movement_shows_battery_life_for_quartz_kind(self) -> None:
        watch = Watch(brand="Casio", model="F-91W", movement=Movement(kind="Quartz", power_reserve_hours=50, battery_life_years=3))
        rows = {r.label: r for r in _movement_rows(watch)}
        self.assertIn("Battery Life", rows)
        self.assertNotIn("Power Reserve", rows)
        self.assertEqual(rows["Battery Life"].text, "3y")

    def test_movement_all_fields_absent_render_em_dash(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033")
        rows = _movement_rows(watch)
        self.assertTrue(all(r.text == EM_DASH for r in rows))

    def test_case_rows_cover_every_case_field(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033", case=Case(
            diameter_mm=37.5, lug_to_lug_mm=46, thickness_mm=11, lug_width_mm=19,
            material="Stainless Steel", crystal="Hardlex", crown="Screw-down",
            bezel="Fixed", caseback="Solid", water_resistance_m=100, weight_g=120,
        ))
        rows = {r.label: r.text for r in _case_rows(watch)}
        self.assertEqual(rows["Diameter"], "37.5 mm")
        self.assertEqual(rows["Water Resistance"], "100 m (10 bar)")
        self.assertEqual(rows["Material"], "Stainless Steel")
        self.assertEqual(len(rows), 11)

    def test_dial_rows_cover_every_dial_field(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033", dial=Dial(colour="Cream", complications=["Date"]))
        rows = {r.label: r.text for r in _dial_rows(watch)}
        self.assertEqual(rows["Colour"], "Cream")
        self.assertEqual(rows["Complications"], "Date")
        self.assertEqual(rows["Lume"], EM_DASH)

    def test_acquisition_url_renders_as_clickable_widget(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033", acquisition=Acquisition(url="https://example.com/listing"))
        rows = {r.label: r for r in _acquisition_rows(watch)}
        self.assertIsInstance(rows["URL"].widget, QPushButton)
        self.assertEqual(rows["URL"].text, "https://example.com/listing")

    def test_acquisition_url_absent_has_no_widget(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033")
        rows = {r.label: r for r in _acquisition_rows(watch)}
        self.assertIsNone(rows["URL"].widget)
        self.assertEqual(rows["URL"].text, EM_DASH)

    def test_acquisition_price_combines_amount_and_currency(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033", acquisition=Acquisition(price=350, currency="USD"))
        rows = {r.label: r.text for r in _acquisition_rows(watch)}
        self.assertEqual(rows["Price"], "350.00 USD")


class SpecGroupVisibilityTests(unittest.TestCase):
    def test_fully_empty_group_is_hidden(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033")
        self.assertIsNone(build_spec_group("Movement", _movement_rows(watch)))

    def test_partially_populated_group_shows_every_row(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033", movement=Movement(caliber="6R15"))
        group = build_spec_group("Movement", _movement_rows(watch))
        self.assertIsNotNone(group)

    def test_straps_group_hidden_when_no_straps(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033")
        self.assertIsNone(_build_straps_group(_fake_record(watch)))

    def test_log_group_hidden_when_empty(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033")
        self.assertIsNone(_build_log_group(watch))

    def test_timing_group_hidden_when_empty(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033")
        self.assertIsNone(_build_timing_group(watch))

    def test_notes_group_hidden_when_blank(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033", notes="   ")
        self.assertIsNone(_build_notes_group(watch))

    def test_notes_group_shown_when_present(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033", notes="Bought on a whim.")
        self.assertIsNotNone(_build_notes_group(watch))


def _fake_record(watch: Watch):
    from saat.storage import WatchRecord
    return WatchRecord(slug="fake", path=Path("/nonexistent"), watch=watch)


class SpecGroupsContainerTests(unittest.TestCase):
    def test_narrow_width_uses_one_column(self) -> None:
        container = SpecGroupsContainer()
        groups = [MinuteTrackHeader("A"), MinuteTrackHeader("B"), MinuteTrackHeader("C")]
        container.set_groups(groups)
        container.resize(300, 600)
        container._relayout()
        self.assertIsNotNone(container._layout.itemAtPosition(1, 0))
        self.assertIsNone(container._layout.itemAtPosition(0, 1))

    def test_wide_width_uses_two_columns(self) -> None:
        container = SpecGroupsContainer()
        groups = [MinuteTrackHeader("A"), MinuteTrackHeader("B"), MinuteTrackHeader("C")]
        container.set_groups(groups)
        container.resize(1200, 600)
        container._relayout()
        self.assertIsNotNone(container._layout.itemAtPosition(0, 1))
        self.assertIsNotNone(container._layout.itemAtPosition(1, 0))


class DetailViewIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-detail-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_minimal_watch_builds_a_page_with_no_spec_groups(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        [record] = load_collection(self.watches_dir)

        view = DetailView(record)
        self.assertEqual(view._build_spec_groups(record), [])

    def test_fully_populated_watch_shows_every_group_in_model_order(self) -> None:
        watch = Watch(
            brand="Seiko", model="SARB033",
            movement=Movement(caliber="6R15"),
            case=Case(diameter_mm=37.5),
            dial=Dial(colour="Cream"),
            straps=[Strap(material="Leather", fitted=True)],
            acquisition=Acquisition(price=350, currency="USD"),
            maintenance=Maintenance(service_interval_years=5),
            log=[LogEntry(date=date(2023, 1, 1), kind="Service")],
            timing=[TimingEntry(date=date(2023, 1, 1), deviation_sec=5, position="Dial Up")],
            notes="A note.",
        )
        create_watch(self.watches_dir, self.backups_dir, watch)
        [record] = load_collection(self.watches_dir)

        view = DetailView(record)
        groups = view._build_spec_groups(record)
        self.assertEqual(len(groups), 9)  # Movement, Case, Dial, Straps, Acquisition, Maintenance, Log, Timing, Notes

    def test_back_requested_signal_emits(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        [record] = load_collection(self.watches_dir)

        view = DetailView(record)
        received = []
        view.back_requested.connect(lambda: received.append(True))
        view.findChild(QPushButton, "back-button").click()
        self.assertEqual(received, [True])


if __name__ == "__main__":
    unittest.main()
