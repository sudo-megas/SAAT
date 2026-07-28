import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QApplication, QMenu

from saat.ui.i18n import build_language_menu, install_language, uninstall_language

TS_PATH = Path(__file__).resolve().parent.parent / "saat" / "resources" / "i18n" / "saat_tr.ts"


def _find_lrelease() -> str | None:
    """Prefers the interpreter's own venv (matches how this repo's other
    tooling is invoked -- see docs/DEVELOPMENT.md) over whatever's on PATH."""
    venv_candidate = Path(sys.prefix) / "bin" / "pyside6-lrelease"
    if venv_candidate.exists():
        return str(venv_candidate)
    return shutil.which("pyside6-lrelease")


LRELEASE = _find_lrelease()


@unittest.skipUnless(LRELEASE, "pyside6-lrelease not found -- install PySide6 to run this test")
class CompiledTranslationTests(unittest.TestCase):
    """Compiles the real, checked-in saat_tr.ts (not a fixture) into a
    throwaway .qm -- catches a stale or malformed .ts the same way the real
    build pipeline would, without depending on whichever .qm a developer
    happens to already have sitting in the gitignored resources/i18n/
    build-output location."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saat-i18n-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.qm_path = self.tmp / "saat_tr.qm"
        result = subprocess.run(
            [LRELEASE, str(TS_PATH), "-qm", str(self.qm_path)],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        match = re.search(r"(\d+) unfinished", result.stdout)
        self.assertIsNotNone(match, result.stdout)
        self.assertEqual(match.group(1), "0", result.stdout)

    def test_compiles_with_zero_unfinished_entries(self) -> None:
        self.assertTrue(self.qm_path.exists())

    def test_a_representative_set_of_strings_translate(self) -> None:
        app = QApplication.instance() or QApplication([])
        translator = QTranslator(app)
        self.assertTrue(translator.load("saat_tr", str(self.tmp)))
        app.installTranslator(translator)
        try:
            self.assertEqual(QCoreApplication.translate("EnumChoices", "Diver"), "Dalgıç")
            self.assertEqual(QCoreApplication.translate("EnumChoices", "Automatic"), "Otomatik")
            self.assertEqual(QCoreApplication.translate("WatchForm", "Add watch"), "Saat ekle")
            self.assertEqual(QCoreApplication.translate("Columns", "Water Resistance"), "Su Direnci")
        finally:
            app.removeTranslator(translator)


class InstallLanguageTests(unittest.TestCase):
    """QApplication.instance() is a process-wide singleton shared with every
    other test module in the same unittest discover run -- install_language()
    installs its translators directly onto it (that's the whole point), so
    every test here must remove them again, or a later-alphabetical test
    module (anything after test_i18n.py) silently starts seeing translated
    strings instead of the English it expects. Confirmed the hard way: this
    exact omission broke test_watch_picker.py during development."""

    def setUp(self) -> None:
        self.app = QApplication.instance() or QApplication([])
        self.addCleanup(uninstall_language, self.app)
        # uninstall_language() (registered above) resets QLocale's default
        # too, so this covers both -- but that only runs AFTER this test's
        # own assertions, and QLocale.setDefault() is process-global state
        # exactly like the translator pollution risk documented on this
        # class already: without resetting it, a test here that switches to
        # Turkish would leave every later-alphabetical test module seeing
        # Turkish casing/date rules instead of the English they expect.

    def test_unsupported_code_returns_false_and_does_not_raise(self) -> None:
        self.assertFalse(install_language(self.app, "xx"))

    @unittest.skipUnless(LRELEASE, "pyside6-lrelease not found -- install PySide6 to run this test")
    def test_turkish_loads_from_the_real_resource_directory(self) -> None:
        """Requires resources/i18n/saat_tr.qm to already be compiled in
        place (docs/DEVELOPMENT.md's build step) -- unlike
        CompiledTranslationTests above, install_language() reads a fixed
        resource_dir() path, not an injectable directory, so this is the
        one test that depends on the real build artifact rather than a
        throwaway compile."""
        qm_path = TS_PATH.parent / "saat_tr.qm"
        if not qm_path.exists():
            subprocess.run([LRELEASE, str(TS_PATH), "-qm", str(qm_path)], check=True, capture_output=True)
            self.addCleanup(qm_path.unlink, missing_ok=True)
        self.assertTrue(install_language(self.app, "tr"))

    def test_qtbase_translations_ship_in_this_pyside6_install(self) -> None:
        """Not SAAT's own artifact -- confirms the environment assumption
        Commit B's plan note relies on (PyInstaller's PySide6 hook bundles
        qtbase_*.qm automatically because QtCore always pulls it in), so a
        PySide6 upgrade that drops Turkish qtbase coverage fails loudly
        here instead of silently at frozen-build time."""
        qtbase_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        self.assertTrue((Path(qtbase_dir) / "qtbase_tr.qm").exists())

    @unittest.skipUnless(LRELEASE, "pyside6-lrelease not found -- install PySide6 to run this test")
    def test_uninstall_removes_both_translators_install_added(self) -> None:
        qm_path = TS_PATH.parent / "saat_tr.qm"
        if not qm_path.exists():
            subprocess.run([LRELEASE, str(TS_PATH), "-qm", str(qm_path)], check=True, capture_output=True)
            self.addCleanup(qm_path.unlink, missing_ok=True)
        self.assertTrue(install_language(self.app, "tr"))
        self.assertGreater(len(self.app.findChildren(QTranslator)), 0)
        uninstall_language(self.app)
        self.assertEqual(self.app.findChildren(QTranslator), [])
        # Reverting to English must actually take effect, not just empty
        # the translator list -- a stale cached lookup would pass the
        # count check above while still returning Turkish text.
        self.assertEqual(QCoreApplication.translate("EnumChoices", "Diver"), "Diver")

    def test_uninstall_is_a_harmless_noop_when_nothing_is_installed(self) -> None:
        uninstall_language(self.app)  # must not raise

    @unittest.skipUnless(LRELEASE, "pyside6-lrelease not found -- install PySide6 to run this test")
    def test_successful_install_sets_qlocale_default_to_the_target_language(self) -> None:
        qm_path = TS_PATH.parent / "saat_tr.qm"
        if not qm_path.exists():
            subprocess.run([LRELEASE, str(TS_PATH), "-qm", str(qm_path)], check=True, capture_output=True)
            self.addCleanup(qm_path.unlink, missing_ok=True)
        self.assertTrue(install_language(self.app, "tr"))
        self.assertEqual(QLocale().language(), QLocale.Language.Turkish)
        # QLocale.toUpper() only applies locale-specific casing when Qt is
        # built with ICU -- without it, it silently falls back to
        # ASCII-style casing and "i" -> "I", not "İ", the exact bug this
        # whole mechanism exists to fix, passing silently. Asserts the
        # actual primitive rather than trusting Qt's docs, the same
        # discipline the bundled-font glyph-coverage check (fc-query vs
        # QRawFont) already established for this milestone.
        self.assertEqual(QLocale().toUpper("indices"), "İNDİCES")

    def test_failed_install_leaves_qlocale_default_at_english(self) -> None:
        """An unrecognised code fails to load SAAT's own catalog -- the UI
        text stays English (see main.py's caller, which warns and
        continues), so the casing/date locale must stay English too:
        Turkish casing applied to English text would be a second, separate
        bug layered on top of the first."""
        self.assertFalse(install_language(self.app, "xx"))
        self.assertEqual(QLocale().language(), QLocale.Language.English)

    def test_uninstall_resets_qlocale_default_to_english(self) -> None:
        QLocale.setDefault(QLocale(QLocale.Language.Turkish))
        uninstall_language(self.app)
        self.assertEqual(QLocale().language(), QLocale.Language.English)


class BuildLanguageMenuTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = QApplication.instance() or QApplication([])

    def test_lists_english_plus_every_supported_language(self) -> None:
        menu = build_language_menu(current_code=None, on_select=lambda code: None)
        labels = [action.text() for action in menu.actions()]
        self.assertEqual(labels, ["English", "Türkçe"])

    def test_current_code_is_the_only_one_checked(self) -> None:
        menu = build_language_menu(current_code="tr", on_select=lambda code: None)
        checked = {action.text(): action.isChecked() for action in menu.actions()}
        self.assertEqual(checked, {"English": False, "Türkçe": True})

    def test_none_current_code_checks_english(self) -> None:
        menu = build_language_menu(current_code=None, on_select=lambda code: None)
        checked = {action.text(): action.isChecked() for action in menu.actions()}
        self.assertEqual(checked, {"English": True, "Türkçe": False})

    def test_selecting_an_entry_calls_on_select_with_its_code(self) -> None:
        selected = []
        menu = build_language_menu(current_code=None, on_select=selected.append)
        turkish_action = next(a for a in menu.actions() if a.text() == "Türkçe")
        turkish_action.trigger()
        self.assertEqual(selected, ["tr"])

    def test_selecting_english_calls_on_select_with_none(self) -> None:
        selected = []
        menu = build_language_menu(current_code="tr", on_select=selected.append)
        english_action = next(a for a in menu.actions() if a.text() == "English")
        english_action.trigger()
        self.assertEqual(selected, [None])

    def test_reusing_a_menu_clears_stale_actions_instead_of_appending(self) -> None:
        menu = QMenu()
        build_language_menu(current_code=None, on_select=lambda code: None, menu=menu)
        build_language_menu(current_code="tr", on_select=lambda code: None, menu=menu)
        labels = [action.text() for action in menu.actions()]
        self.assertEqual(labels, ["English", "Türkçe"])
