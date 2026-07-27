"""Installs SAAT's own translation plus Qt's built-in string catalog (dialog
button labels, file-picker chrome) for a given UI language. See SPEC.md's
localisation section. Called only for an explicit non-English choice --
English needs no translator installed at all, the same "absent means
English" shape as saat.config.Config.language() itself."""

from PySide6.QtCore import QLibraryInfo, QTranslator
from PySide6.QtWidgets import QApplication

from saat.paths import resource_dir

# Endonyms, not English names -- Commit C's language menu lists these.
SUPPORTED_LANGUAGES = {"tr": "Türkçe"}


def install_language(app: QApplication, code: str) -> bool:
    """Returns whether SAAT's own .qm loaded. Qt's qtbase_<code>.qm covers
    stock widget chrome (QMessageBox/QFileDialog/QDialogButtonBox button
    labels) that never passes through saat's own .ts files no matter how
    thorough the string sweep is -- PyInstaller's PySide6 hook bundles every
    qtbase_*.qm automatically (QtCore is always a transitive dependency), so
    this resolves the same way frozen or not. A missing qtbase file is not
    surfaced as a failure the way a missing saat_<code>.qm is: Qt ships
    qtbase translations for far fewer languages than SAAT will ever target,
    so its absence for some future language is expected, not a build defect
    the way a missing app-authored .qm would be."""
    app_translator = QTranslator(app)
    app_loaded = app_translator.load(f"saat_{code}", str(resource_dir() / "resources" / "i18n"))
    if app_loaded:
        app.installTranslator(app_translator)

    qtbase_translator = QTranslator(app)
    qtbase_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if qtbase_translator.load(f"qtbase_{code}", qtbase_dir):
        app.installTranslator(qtbase_translator)

    return app_loaded
