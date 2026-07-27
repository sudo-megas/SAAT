import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QTranslator
from PySide6.QtWidgets import QApplication

from saat.ui.i18n import install_language

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
        self.addCleanup(self._remove_installed_translators)

    def _remove_installed_translators(self) -> None:
        for translator in self.app.findChildren(QTranslator):
            self.app.removeTranslator(translator)
            translator.setParent(None)
            translator.deleteLater()

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
