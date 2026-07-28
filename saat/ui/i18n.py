"""Installs SAAT's own translation plus Qt's built-in string catalog (dialog
button labels, file-picker chrome) for a given UI language. See SPEC.md's
localisation section. Called only for an explicit non-English choice --
English needs no translator installed at all, the same "absent means
English" shape as saat.config.Config.language() itself."""

from typing import Callable

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import QApplication, QMenu

from saat.paths import resource_dir

# Endonyms, not English names -- Commit C's language menu lists these.
# Scoped to "codes with an installable saat_<code>.qm", not "all UI
# language choices" -- English is deliberately excluded (see
# build_language_menu() below, which adds its own English entry).
SUPPORTED_LANGUAGES = {"tr": "Türkçe"}

# A parallel map, not derived from SUPPORTED_LANGUAGES: the values are a
# different kind of thing (a QLocale.Language enum member for casing/date
# rules, not a display endonym) and would need their own dict either way.
_QLOCALE_LANGUAGES = {"tr": QLocale.Language.Turkish}


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
    the way a missing app-authored .qm would be.

    Also sets QLocale.setDefault() -- the one and only place SAAT sets it,
    so every other file needing locale-aware casing (.toUpper()/.toLower())
    or month/weekday names just calls bare QLocale() and gets the right
    answer, with no language code threaded in from anywhere. Only on
    success: if the .qm fails to load, the UI text is staying English (see
    main.py's caller), so the casing/date locale must too -- Turkish
    casing applied to English text would be its own, different bug."""
    app_translator = QTranslator(app)
    app_loaded = app_translator.load(f"saat_{code}", str(resource_dir() / "resources" / "i18n"))
    if app_loaded:
        app.installTranslator(app_translator)
        QLocale.setDefault(QLocale(_QLOCALE_LANGUAGES.get(code, QLocale.Language.English)))

    qtbase_translator = QTranslator(app)
    qtbase_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if qtbase_translator.load(f"qtbase_{code}", qtbase_dir):
        app.installTranslator(qtbase_translator)

    return app_loaded


def uninstall_language(app: QApplication) -> None:
    """Reverts to English -- removes every translator install_language()
    may have installed, and resets QLocale.setDefault() to English
    alongside them. Safe to call unconditionally, including from an
    already-English session (a no-op then): sweeps whatever's currently
    installed on `app` rather than tracking specific instances, since SAAT
    only ever installs a QTranslator via install_language() -- nothing
    else's state is at risk of being swept up here. Called before every
    switch (including switching between two non-English languages), never
    just before installing English, so translators never accumulate: two
    installed at once would have the most-recently-installed one shadow
    the other only for keys they share, silently falling through to the
    older one -- and therefore a stale language -- for any key it doesn't."""
    for translator in app.findChildren(QTranslator):
        app.removeTranslator(translator)
        translator.setParent(None)
        translator.deleteLater()
    QLocale.setDefault(QLocale(QLocale.Language.English))


def build_language_menu(
    current_code: str | None,
    on_select: Callable[[str | None], None],
    menu: QMenu | None = None,
) -> QMenu:
    """Populates `menu` (clearing it first) with one checkable, mutually
    exclusive action per supported language plus English, and returns it
    -- constructs a fresh QMenu if none is given. Shared by both language-
    control hosts (TrayController's submenu, Sidebar's fallback popup) so
    they can't drift out of sync -- e.g. one showing a stale checkmark
    after the other's selection changed config.language(). Meant to be
    rebuilt fresh on every open rather than holding live state of its own
    -- the same "reflects reality read fresh every time the menu opens"
    idiom TrayController's own _rebuild_wore_today_menu already uses for
    its checkable items.

    Labels are endonyms (see SUPPORTED_LANGUAGES), never translated: a
    language picker names each language in itself, the same way such a
    picker would show "Español" regardless of the UI's current language.
    English isn't part of SUPPORTED_LANGUAGES and gets its own entry here
    with its own clear-the-key semantics: on_select(None), never
    on_select("en") -- see config.py's set_language() docstring for why
    writing the literal "en" is wrong."""
    if menu is None:
        menu = QMenu()
    else:
        menu.clear()
    group = QActionGroup(menu)
    group.setExclusive(True)

    def _add(label: str, code: str | None) -> None:
        action = menu.addAction(label)
        action.setCheckable(True)
        action.setChecked(current_code == code)
        action.triggered.connect(lambda: on_select(code))
        group.addAction(action)

    _add("English", None)
    for code, endonym in SUPPORTED_LANGUAGES.items():
        _add(endonym, code)

    return menu
