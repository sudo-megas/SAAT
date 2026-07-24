import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

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
    _TimingSparkline,
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

    def test_target_price_is_distinct_from_price(self) -> None:
        """SPEC.md §4: target_price (what it costs) vs. price (what was
        paid) — both render, never overloading one field for both."""
        watch = Watch(
            brand="Seiko", model="SARB033",
            acquisition=Acquisition(price=350, target_price=500, currency="USD"),
        )
        rows = {r.label: r.text for r in _acquisition_rows(watch)}
        self.assertEqual(rows["Price"], "350.00 USD")
        self.assertEqual(rows["Target Price"], "500.00 USD")

    def test_target_price_and_target_date_absent_render_em_dash(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033")
        rows = {r.label: r.text for r in _acquisition_rows(watch)}
        self.assertEqual(rows["Target Price"], EM_DASH)
        self.assertEqual(rows["Target Date"], EM_DASH)


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


class TimingSparklineTests(unittest.TestCase):
    """SPEC.md §4: sparkline only once there are 3+ readings; the plain
    chronological list (already covered elsewhere) always renders regardless."""

    def _entry(self, day: int, deviation: float) -> TimingEntry:
        return TimingEntry(date=date(2023, 1, day), deviation_sec=deviation, position="Dial Up")

    def test_group_has_no_sparkline_with_only_two_readings(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033", timing=[self._entry(1, 5), self._entry(2, 6)])
        group = _build_timing_group(watch)
        self.assertIsNone(group.findChild(_TimingSparkline))

    def test_group_has_a_sparkline_with_three_readings(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033", timing=[self._entry(1, 5), self._entry(2, 6), self._entry(3, 4)])
        group = _build_timing_group(watch)
        self.assertIsNotNone(group.findChild(_TimingSparkline))

    def test_entries_missing_date_or_deviation_are_excluded_from_the_readings_count(self) -> None:
        watch = Watch(brand="Seiko", model="SARB033", timing=[
            self._entry(1, 5), self._entry(2, 6), self._entry(3, 4),
            TimingEntry(date=None, deviation_sec=10, position="Crown Up"),
            TimingEntry(date=date(2023, 1, 4), deviation_sec=None, position="Crown Up"),
        ])
        group = _build_timing_group(watch)
        sparkline = group.findChild(_TimingSparkline)
        self.assertIsNotNone(sparkline)
        self.assertEqual(len(sparkline._values), 3)

    def test_sparkline_values_are_sorted_chronologically_regardless_of_input_order(self) -> None:
        sparkline = _TimingSparkline([self._entry(3, 30), self._entry(1, 10), self._entry(2, 20)])
        self.assertEqual(sparkline._values, [10, 20, 30])

    def test_fewer_than_two_values_paints_without_error(self) -> None:
        sparkline = _TimingSparkline([self._entry(1, 5)])
        sparkline.resize(160, 48)
        sparkline.repaint()  # must not raise even though there's nothing to draw a line between


class StrapCompatibilityTests(unittest.TestCase):
    """SPEC.md §5.9. DetailView's default all_records=None (used by every
    other test in this file, which only ever passes a single record) always
    yields [] here — this class is what actually exercises the wiring."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-detail-strap-compat-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_all_records_argument_means_no_compatible_straps_section(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", case=Case(lug_width_mm=20)))
        [record] = load_collection(self.watches_dir)
        view = DetailView(record)
        self.assertNotIn("Compatible Straps", [g.findChild(MinuteTrackHeader)._title for g in view._build_spec_groups(record) if g.findChild(MinuteTrackHeader)])

    def test_a_matching_strap_on_another_watch_shows_the_section(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", case=Case(lug_width_mm=20)))
        create_watch(self.watches_dir, self.backups_dir, Watch(
            brand="Casio", model="F-91W", case=Case(lug_width_mm=22),
            straps=[Strap(material="NATO", width_mm=20)],
        ))
        records = load_collection(self.watches_dir)
        target = next(r for r in records if r.watch.brand == "Seiko")

        view = DetailView(target, records)
        titles = [g.findChild(MinuteTrackHeader)._title for g in view._build_spec_groups(target) if g.findChild(MinuteTrackHeader)]
        self.assertIn("COMPATIBLE STRAPS", titles)

    def test_no_matches_means_no_section_even_with_the_full_collection(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", case=Case(lug_width_mm=20)))
        create_watch(self.watches_dir, self.backups_dir, Watch(
            brand="Casio", model="F-91W", case=Case(lug_width_mm=22),
            straps=[Strap(material="NATO", width_mm=22)],
        ))
        records = load_collection(self.watches_dir)
        target = next(r for r in records if r.watch.brand == "Seiko")

        view = DetailView(target, records)
        titles = [g.findChild(MinuteTrackHeader)._title for g in view._build_spec_groups(target) if g.findChild(MinuteTrackHeader)]
        self.assertNotIn("COMPATIBLE STRAPS", titles)


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

    def _button_labeled(self, view: DetailView, text: str) -> QPushButton | None:
        return next((b for b in view.findChildren(QPushButton) if b.text() == text), None)

    def test_mark_as_owned_button_present_only_for_a_wishlist_watch(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", status="Wishlist"))
        [wishlist_record] = load_collection(self.watches_dir)
        self.assertIsNotNone(self._button_labeled(DetailView(wishlist_record), "Mark as Owned"))

        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Casio", model="F-91W", status="Owned"))
        records = load_collection(self.watches_dir)
        owned_record = next(r for r in records if r.watch.brand == "Casio")
        self.assertIsNone(self._button_labeled(DetailView(owned_record), "Mark as Owned"))

    def test_clicking_mark_as_owned_emits_the_request_with_the_record(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033", status="Wishlist"))
        [record] = load_collection(self.watches_dir)

        view = DetailView(record)
        received = []
        view.move_to_owned_requested.connect(lambda r: received.append(r))
        self._button_labeled(view, "Mark as Owned").click()
        self.assertEqual([r.slug for r in received], [record.slug])


class MaintenanceDueLineTests(unittest.TestCase):
    """SPEC.md §4: 'a line at the top of its detail page' — silent when
    nothing is due, silent entirely when the interval is blank."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-detail-maintenance-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_interval_shows_no_line(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        [record] = load_collection(self.watches_dir)
        view = DetailView(record)
        self.assertIsNone(view.findChild(QLabel, "maintenance-due-line"))

    def test_overdue_service_shows_the_line(self) -> None:
        watch = Watch(
            brand="Seiko", model="SARB033",
            maintenance=Maintenance(service_interval_years=1),
            log=[LogEntry(date=date(2020, 1, 1), kind="Service")],
        )
        create_watch(self.watches_dir, self.backups_dir, watch)
        [record] = load_collection(self.watches_dir)
        view = DetailView(record)
        line = view.findChild(QLabel, "maintenance-due-line")
        self.assertIsNotNone(line)
        self.assertIn("overdue", line.text().lower())

    def test_interval_far_from_due_shows_no_line(self) -> None:
        watch = Watch(
            brand="Seiko", model="SARB033",
            maintenance=Maintenance(service_interval_years=5),
            log=[LogEntry(date=date.today(), kind="Service")],
        )
        create_watch(self.watches_dir, self.backups_dir, watch)
        [record] = load_collection(self.watches_dir)
        view = DetailView(record)
        self.assertIsNone(view.findChild(QLabel, "maintenance-due-line"))


if __name__ == "__main__":
    unittest.main()
