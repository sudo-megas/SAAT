import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QPushButton

from saat.config import Config
from saat.models import Acquisition, Movement, Watch
from saat.storage import WatchRecord, create_watch
from saat.ui.collection_view import CollectionView
from saat.ui.detail_view import DetailView
from saat.ui.i18n import install_language, uninstall_language
from saat.ui.main_window import MainWindow

_app = QApplication.instance() or QApplication([])


def _pump() -> None:
    """Delivers a pending QTimer.singleShot(0, ...) callback (motion.
    fade_transition's deferred _apply()). Deliberately NOT a real blocking
    QEventLoop().exec(): confirmed by direct repro that running one this
    late in a full `unittest discover` run segfaults -- ~900 tests across
    this suite manage Qt objects via deleteLater() and are cleaned up with
    processEvents() only (which does not drain the DeferredDelete queue),
    so a real event loop is the first thing all run to actually process
    that backlog, and something in it doesn't survive being deleted for
    real. Reproduced with a generic QEventLoop().exec() containing none of
    this file's own code, immediately after the rest of the suite and
    nothing else -- a pre-existing test-suite-wide lifecycle issue, not a
    product bug or something introduced here. Plain processEvents() calls
    reliably deliver a zero-delay singleShot on the first call in this
    environment and don't touch that queue, so a short retry loop of those
    is both sufficient and safe here."""
    for _ in range(10):
        _app.processEvents()

TS_PATH = Path(__file__).resolve().parent.parent / "saat" / "resources" / "i18n" / "saat_tr.ts"


def _find_lrelease() -> str | None:
    venv_candidate = Path(sys.prefix) / "bin" / "pyside6-lrelease"
    if venv_candidate.exists():
        return str(venv_candidate)
    return shutil.which("pyside6-lrelease")


LRELEASE = _find_lrelease()


def _make_record() -> WatchRecord:
    watch = Watch(
        brand="Seiko", model="SKX007", group="Seiko Group", style="Diver", status="Owned",
        movement=Movement(kind="Automatic"), acquisition=Acquisition(),
    )
    return WatchRecord(slug="seiko-skx007", path=Path("/tmp/does-not-matter"), watch=watch, load_error=None)


@unittest.skipUnless(LRELEASE, "pyside6-lrelease not found -- install PySide6 to run this test")
class LiveRetranslationTests(unittest.TestCase):
    """End-to-end: installs the REAL compiled Turkish translator at runtime
    and confirms Qt's LanguageChange propagation actually reaches Sidebar/
    TopBar/TableView through CollectionView's own changeEvent -- not a
    unit-level check of each widget's _retranslate() in isolation, which
    could pass even if the changeEvent wiring connecting them were wrong.
    Advisor's suggested order for this milestone's biggest architectural
    risk: get these three right and proven end-to-end before fanning the
    same pattern out to the rest of saat/ui/."""

    def setUp(self) -> None:
        self.qm_path = TS_PATH.parent / "saat_tr.qm"
        if not self.qm_path.exists():
            subprocess.run([LRELEASE, str(TS_PATH), "-qm", str(self.qm_path)], check=True, capture_output=True)
            self.addCleanup(self.qm_path.unlink, missing_ok=True)
        self.addCleanup(uninstall_language, _app)
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-retranslation-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.config = Config(self.tmp / "config.toml")
        self.view = CollectionView([_make_record()], self.config)

    def test_switching_to_turkish_retranslates_top_bar_labels(self) -> None:
        top_bar = self.view._top_bar
        self.assertEqual(top_bar._collection_button.text(), "Collection")
        self.assertEqual(top_bar._wishlist_button.text(), "Wishlist")
        self.assertEqual(top_bar._grid_button.text(), "Grid")

        self.assertTrue(install_language(_app, "tr"))
        _app.processEvents()

        self.assertEqual(top_bar._collection_button.text(), "Koleksiyon")
        self.assertEqual(top_bar._wishlist_button.text(), "İstek Listesi")
        self.assertEqual(top_bar._grid_button.text(), "Izgara")

    def test_switching_to_turkish_retranslates_sidebar_labels(self) -> None:
        sidebar = self.view._sidebar
        self.assertEqual(sidebar._toggle_button.text(), "Hide filters")

        self.assertTrue(install_language(_app, "tr"))
        _app.processEvents()

        self.assertEqual(sidebar._toggle_button.text(), "Filtreleri gizle")

    def test_switching_to_turkish_retranslates_table_header(self) -> None:
        # Uppercased via QLocale().toUpper() (table_view.py's _render()),
        # not plain str.upper() -- "Mekanizma" has an ASCII lowercase i,
        # which Turkish casing rules turn into dotted İ (MEKANİZMA), not
        # plain ASCII I. A wrong casing call here would silently render the
        # OS-default-locale form instead and this test wouldn't catch it,
        # so the expected strings are QLocale(Turkish)-correct, not typed
        # by hand.
        table = self.view._table_view
        table.set_columns(["group", "movement_kind"])
        header_text = lambda: [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
        self.assertEqual(header_text(), ["GROUP", "MOVEMENT"])

        self.assertTrue(install_language(_app, "tr"))
        _app.processEvents()

        self.assertEqual(header_text(), ["GRUP", "MEKANİZMA"])

    def test_switching_back_to_english_reverts_all_three(self) -> None:
        top_bar = self.view._top_bar
        sidebar = self.view._sidebar
        install_language(_app, "tr")
        _app.processEvents()
        self.assertEqual(top_bar._collection_button.text(), "Koleksiyon")

        uninstall_language(_app)
        _app.processEvents()

        self.assertEqual(top_bar._collection_button.text(), "Collection")
        self.assertEqual(sidebar._toggle_button.text(), "Hide filters")


@unittest.skipUnless(LRELEASE, "pyside6-lrelease not found -- install PySide6 to run this test")
class MainWindowRetranslationTests(unittest.TestCase):
    """Routes through the REAL production call path (MainWindow.
    _on_language_selected), not a raw install_language() call -- two things
    only this path can prove:

    1. The DetailView re-show machinery (changeEvent -> singleShot(0) ->
       _apply_pending_retranslate -> _show_detail) that was designed and
       built but never exercised by LiveRetranslationTests above, which
       only ever built a bare CollectionView.
    2. Facet-heading Turkish casing depends on config.language() already
       being "tr" by the time LanguageChange fires -- true in production
       because _on_language_selected() writes config before installing
       the translator, but LiveRetranslationTests' raw install_language()
       calls never touch config at all, so they couldn't have caught a
       regression in that ordering."""

    def setUp(self) -> None:
        self.qm_path = TS_PATH.parent / "saat_tr.qm"
        if not self.qm_path.exists():
            subprocess.run([LRELEASE, str(TS_PATH), "-qm", str(self.qm_path)], check=True, capture_output=True)
            self.addCleanup(self.qm_path.unlink, missing_ok=True)
        self.addCleanup(uninstall_language, _app)
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-retranslation-mw-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.watches_dir = self.tmp / "watches"
        self.backups_dir = self.tmp / "backups"
        self.watches_dir.mkdir()
        watch = Watch(brand="Seiko", model="SKX007", style="Diver", status="Owned")
        self.record = create_watch(self.watches_dir, self.backups_dir, watch)
        self.config = Config(self.tmp / "config.toml")
        self.window = MainWindow(self.watches_dir, self.backups_dir, self.config)

    def test_detail_view_stays_current_and_retranslates_after_a_language_switch(self) -> None:
        self.window._show_detail(self.record)
        _pump()  # motion.fade_transition's own deferred _apply()
        detail_view = self.window._stack.currentWidget()
        self.assertIsInstance(detail_view, DetailView)

        self.window._on_language_selected("tr")
        _pump()

        current = self.window._stack.currentWidget()
        self.assertIsInstance(current, DetailView)
        self.assertIsNot(current, detail_view)  # rebuilt, not mutated in place
        self.assertEqual(current.record.slug, self.record.slug)
        new_back_button = current.findChild(QPushButton, "back-button")
        self.assertEqual(new_back_button.text(), "Geri")

    def test_bottom_bar_summary_retranslates_after_a_language_switch(self) -> None:
        """Milestone 21b-e: BottomBar.set_summary() (bottom_bar.py) stores
        the raw CollectionSummary/WishlistSummary dataclass and reformats
        it on every changeEvent(LanguageChange), rather than being handed
        pre-formatted text -- otherwise the bottom bar would keep showing
        English until the next filter change re-triggered CollectionView.
        _recompute()'s own summary_changed emit. One real watch (setUp) is
        already primed into English "1 watch" by MainWindow's own initial
        wiring (_load_and_show_collection's post-connect current_summary
        priming) before this test ever touches language."""
        summary_label = self.window._bottom_bar._summary_label
        self.assertEqual(summary_label.text(), "1 watch")

        self.window._on_language_selected("tr")
        _pump()

        self.assertEqual(summary_label.text(), "1 saat")

    def test_language_change_while_on_the_collection_view_does_not_touch_detail_state(self) -> None:
        """MainWindow's changeEvent guards on currentWidget() is the detail/
        compare view -- while the collection view is showing, a language
        switch must not call _show_detail at all (nothing to re-show, and
        _last_detail_record may be stale from an earlier visit)."""
        self.window._show_detail(self.record)
        _pump()
        self.window._show_collection()
        _pump()

        self.window._on_language_selected("tr")
        _pump()

        self.assertIs(self.window._stack.currentWidget(), self.window._collection_view)

    def test_facet_heading_gets_correct_turkish_casing_through_the_real_selection_path(self) -> None:
        """QLocale(Turkish).toUpper("Stil") -> "STİL" (dotted capital İ);
        plain Python .upper() or an English-resolved QLocale both give the
        wrong "STIL" (dotless). Only fails if config.language() and the
        installed translator can drift out of sync."""
        sidebar = self.window._collection_view._sidebar
        style_heading = next(label for facet, label in sidebar._facet_headings if facet.key == "style")
        self.assertEqual(style_heading.text(), "STYLE")

        self.window._on_language_selected("tr")
        _pump()

        self.assertEqual(style_heading.text(), "STİL")

    def test_rapid_reselection_does_not_crash_or_duplicate_the_detail_view(self) -> None:
        """Defense-in-depth coverage for the _retranslate_pending coalescing
        flag: even though a single switch was measured to fire exactly one
        LanguageChange event during development, nothing guarantees that
        stays true across Qt versions/platforms, and clicking a second
        language before the first's fade transition finishes is a real way
        to trigger more than one _show_detail() re-invocation in the same
        event-loop turn regardless. Without the flag, motion.fade_transition's
        deferred _apply() would removeWidget()/deleteLater() the same
        DetailView twice."""
        self.window._show_detail(self.record)
        _pump()

        self.window._on_language_selected("tr")
        self.window._on_language_selected(None)
        self.window._on_language_selected("tr")
        _pump()

        current = self.window._stack.currentWidget()
        self.assertIsInstance(current, DetailView)
        self.assertEqual(current.record.slug, self.record.slug)
