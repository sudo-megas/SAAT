import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from saat import __version__
from saat.config import Config
from saat.models import Acquisition, Case, Movement, Watch
from saat.storage import create_watch, load_collection
from saat.ui.collection_view import CollectionView
from saat.ui.columns import COLUMN_PRESETS, DEFAULT_COLUMN_KEYS
from saat.ui.detail_view import DetailView
from saat.ui.empty_state import EmptyStateView
from saat.ui.main_window import MainWindow
from saat.ui.table_view import TableView

_app = QApplication.instance() or QApplication([])


class UITestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-ui-test-"))
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _config(self) -> Config:
        return Config(self.tmp / "config.toml")


class MainWindowEntryPointTests(UITestCase):
    """Routed through MainWindow itself, not the leaf widgets — this is what
    actually catches import errors and signal-wiring mistakes in the new
    grid/table/collection code, since the real watches/ dir ships empty and
    never exercises the populated branch on its own."""

    def test_empty_collection_shows_empty_state(self) -> None:
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        self.assertIsInstance(window.centralWidget().currentWidget(), EmptyStateView)

    def test_window_title_shows_the_single_source_of_truth_version(self) -> None:
        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        self.assertIn(__version__, window.windowTitle())

    def test_populated_collection_shows_collection_view(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Casio", model="F-91W"))

        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        view = window.centralWidget().currentWidget()

        self.assertIsInstance(view, CollectionView)
        self.assertEqual(len(view._grid_view._cards), 2)
        self.assertEqual(view._table_view.rowCount(), 2)

    def test_malformed_watch_alongside_good_ones_still_renders(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        broken = self.watches_dir / "broken"
        broken.mkdir()
        (broken / "watch.toml").write_text("brand = ][not valid toml", encoding="utf-8")

        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        view = window.centralWidget().currentWidget()

        self.assertIsInstance(view, CollectionView)
        self.assertEqual(len(view._grid_view._cards), 2)
        self.assertEqual(view._table_view.rowCount(), 2)

    def test_activating_a_record_opens_detail_and_back_returns_same_collection_view(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))

        window = MainWindow(self.watches_dir, self.backups_dir, self._config())
        collection_view = window.centralWidget().currentWidget()
        [record] = collection_view._records

        collection_view.record_activated.emit(record)
        self.assertIsInstance(window.centralWidget().currentWidget(), DetailView)

        window._detail_view.back_requested.emit()
        self.assertIs(window.centralWidget().currentWidget(), collection_view)


class CollectionViewBehaviorTests(UITestCase):
    def setUp(self) -> None:
        super().setUp()
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Seiko", model="SARB033"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Casio", model="F-91W"))
        create_watch(self.watches_dir, self.backups_dir, Watch(brand="Omega", model="Speedmaster"))
        self.records = load_collection(self.watches_dir)

    def test_default_view_and_columns_match_config_defaults(self) -> None:
        view = CollectionView(self.records, self._config())
        self.assertEqual(view._table_view.columnCount(), len(DEFAULT_COLUMN_KEYS))

    def test_default_sort_is_by_brand(self) -> None:
        view = CollectionView(self.records, self._config())
        brands = [view._table_view.item(r, 0).text() for r in range(view._table_view.rowCount())]
        self.assertEqual(brands, sorted(brands))
        self.assertEqual(brands, ["Casio", "Omega", "Seiko"])

    def test_sort_change_reorders_table(self) -> None:
        view = CollectionView(self.records, self._config())
        view._on_sort_changed("model")
        models = [view._table_view.item(r, 1).text() for r in range(view._table_view.rowCount())]
        self.assertEqual(models, sorted(models))

    def test_double_click_after_header_sort_activates_the_correct_record(self) -> None:
        """A header-sort reorders the table's visual rows without touching
        self._records, so the record behind a double-clicked row must come
        from data attached to the item (UserRole), never self._records[row]."""
        view = CollectionView(self.records, self._config())
        received = []
        view.record_activated.connect(received.append)

        view._table_view.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        view._table_view._on_cell_double_clicked(0, 0)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].watch.brand, "Seiko")  # last alphabetically, so row 0 descending

    def test_column_preset_switches_visible_columns_and_persists(self) -> None:
        config = self._config()
        view = CollectionView(self.records, config)
        view._on_preset_changed("Movement")

        self.assertEqual(view._table_view.columnCount(), len(COLUMN_PRESETS["Movement"]))
        self.assertEqual(config.column_keys(), COLUMN_PRESETS["Movement"])

    def test_view_toggle_persists_to_config(self) -> None:
        config = self._config()
        view = CollectionView(self.records, config)
        view._on_view_changed("table")
        self.assertEqual(config.last_view(), "table")


def _formatter_exercise_watch() -> Watch:
    """Populates exactly the fields a bare brand/model fixture leaves at None —
    water resistance, bph/frequency, signed accuracy range, price, a date — so
    a broken column formatter fails a test instead of silently landing as an
    em-dash."""
    return Watch(
        brand="Seiko",
        model="SARB033",
        movement=Movement(bph=21600, accuracy_min=-20, accuracy_max=40, accuracy_unit="sec/day"),
        case=Case(water_resistance_m=200),
        acquisition=Acquisition(price=350, currency="USD", date=date(2023, 6, 15)),
    )


class TableFormatterTests(UITestCase):
    """Column.text() formatters are the substantive logic of the table view —
    exercise them through the real render path, not just brand/model."""

    def test_formatted_cell_values(self) -> None:
        create_watch(self.watches_dir, self.backups_dir, _formatter_exercise_watch())
        [record] = load_collection(self.watches_dir)

        keys = ["water_resistance_m", "bph", "accuracy", "price", "acquired_date"]
        table = TableView(on_columns_changed=lambda keys: None)
        table.set_columns(keys)
        table.set_records([record])

        def cell(key: str) -> str:
            return table.item(0, keys.index(key)).text()

        self.assertEqual(cell("water_resistance_m"), "200 m (20 bar)")
        self.assertEqual(cell("bph"), "21600 bph (3 Hz)")
        self.assertEqual(cell("accuracy"), "-20/+40 sec/day")
        self.assertEqual(cell("price"), "350.00 USD")
        self.assertEqual(cell("acquired_date"), "15.06.2023")


class TopBarStyledBackgroundTests(unittest.TestCase):
    """A plain QWidget subclass silently ignores QSS `border-*` (though not
    `background`) unless WA_StyledBackground is set — TopBar's border-bottom
    was invisible for all of milestone 3 without anyone noticing, since only
    a pixel-level check (not a widget-tree check) catches a border that never
    painted. See also SidebarStyledBackgroundTests in test_sidebar.py."""

    def test_top_bar_has_styled_background_enabled(self) -> None:
        from saat.ui.top_bar import TopBar

        top_bar = TopBar()
        self.assertTrue(top_bar.testAttribute(Qt.WidgetAttribute.WA_StyledBackground))


if __name__ == "__main__":
    unittest.main()
