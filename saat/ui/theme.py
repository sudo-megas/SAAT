import gc
import tomllib
from dataclasses import dataclass, fields

from PySide6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication, QEasingCurve
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from saat.paths import resource_dir


@dataclass(frozen=True)
class Palette:
    plate: str
    plate_high: str
    rule: str
    text: str
    text_muted: str
    gilt: str
    ruby: str


@dataclass(frozen=True)
class PaletteEntry:
    id: str
    name: str
    is_dark: bool
    palette: Palette


_PALETTE_FIELD_NAMES = tuple(f.name for f in fields(Palette))

# Ten fixed presets (SPEC.md §6/§9 -- data, not a theme editor). Explicit
# display order, not alphabetical glob order: the popover lists palettes in
# exactly this sequence, and "catppuccin-frappe" would sort ahead of
# "default-light" alphabetically.
_PALETTE_ORDER = (
    "default-light",
    "default-dark",
    "noctalia",
    "catppuccin-latte",
    "catppuccin-frappe",
    "catppuccin-macchiato",
    "catppuccin-mocha",
    "rose-pine-dawn",
    "nord",
    "kanagawa-lotus",
)

# The two generic English names aren't visible to pyside6-lupdate (it only
# scans Python source, never TOML) -- marked here and translated at the call
# site via display_name(), same split columns.py's own GROUP_ORDER uses. The
# other eight are proper nouns and pass through PaletteEntry.name untranslated.
_TRANSLATABLE_NAMES = {
    "default-light": QT_TRANSLATE_NOOP("Palettes", "Default Light"),
    "default-dark": QT_TRANSLATE_NOOP("Palettes", "Default Dark"),
}

_palette_registry: dict[str, PaletteEntry] | None = None


def _load_palette_registry() -> dict[str, PaletteEntry]:
    palettes_dir = resource_dir() / "resources" / "palettes"
    registry: dict[str, PaletteEntry] = {}
    for palette_id in _PALETTE_ORDER:
        path = palettes_dir / f"{palette_id}.toml"
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        palette_colors = Palette(**{name: data[name] for name in _PALETTE_FIELD_NAMES})
        registry[palette_id] = PaletteEntry(
            id=data["id"], name=data["name"], is_dark=data["is_dark"], palette=palette_colors
        )
    return registry


def _registry() -> dict[str, PaletteEntry]:
    # Lazy, not import-time: theme.py stays free of disk I/O at import, and a
    # missing/renamed TOML file fails loudly the first time a palette is
    # actually needed rather than crashing every import of this module.
    global _palette_registry
    if _palette_registry is None:
        _palette_registry = _load_palette_registry()
    return _palette_registry


def palettes() -> tuple[PaletteEntry, ...]:
    """All ten presets, in the fixed display order (SPEC.md §6)."""
    registry = _registry()
    return tuple(registry[palette_id] for palette_id in _PALETTE_ORDER)


def palette(palette_id: str) -> PaletteEntry:
    registry = _registry()
    if palette_id not in registry:
        raise ValueError(f"unknown palette id: {palette_id!r}")
    return registry[palette_id]


def display_name(entry: PaletteEntry) -> str:
    """Default Light/Default Dark translate; the other eight are proper
    nouns (Nord, Catppuccin Mocha, ...) shown exactly as named upstream."""
    source = _TRANSLATABLE_NAMES.get(entry.id)
    if source is not None:
        return QCoreApplication.translate("Palettes", source)
    return entry.name


_current_palette_id = "default-dark"


def current_palette_id() -> str:
    return _current_palette_id


def set_palette(palette_id: str) -> None:
    global _current_palette_id
    if palette_id not in _registry():
        raise ValueError(f"unknown palette id: {palette_id!r}")
    _current_palette_id = palette_id


def active_palette() -> PaletteEntry:
    return palette(_current_palette_id)


def colors() -> Palette:
    """The active palette. Read this at paint time, not import time — a
    `from saat.ui.theme import GILT`-style import binds the string once and
    never sees a later switch. See SPEC.md §6's palette-picker requirement."""
    return active_palette().palette


# A render target, not a theme (SPEC.md §9, milestone 19) — deliberately
# outside the ten-preset registry and unreachable through set_palette()/
# colors(), so nothing can select it from the picker and PDF rendering never
# has to mutate the live window's global theme state to borrow it. Pure
# white rather than any preset's own plate, near-black text rather than a
# charcoal one, and a darker rule than default-light's — screen contrast
# tuning doesn't guarantee a hairline survives a home printer's reproduction.
# gilt/ruby are literal copies of default-light's own values (already
# contrast-checked against a pure white plate_high) rather than a live
# registry lookup, so PAPER stays a self-contained constant with no loading
# dependency of its own.
PAPER = Palette(
    plate="#FFFFFF",
    plate_high="#FFFFFF",
    rule="#B0A992",
    text="#1A1815",
    text_muted="#5C5548",
    gilt="#8A6A16",
    ruby="#A82F24",
)

# Type scale. Weights 400 and 600 only.
SIZE_XS = 11
SIZE_SM = 13
SIZE_MD = 15
SIZE_LG = 20
SIZE_XL = 28

# Spacing — 8px base unit.
SPACING_UNIT = 8
CARD_PADDING = 16
GROUP_SPACING = 32
PAGE_MARGIN = 24
TABLE_ROW_PADDING = 12

# SPEC.md §5.1 — left sidebar, ~260px, collapsible.
SIDEBAR_WIDTH = 260
SIDEBAR_COLLAPSED_WIDTH = 130

# SPEC.md §6 — one duration, one easing curve, single-sourced so no view
# scatters its own magic number. Only state CHANGES animate, never first
# paint, and nothing here runs longer than ANIM_DURATION_MS.
ANIM_DURATION_MS = 160
ANIM_EASING = QEasingCurve.Type.InOutCubic

FONT_SANS = "Ubuntu Sans"
FONT_SANS_CONDENSED = "Ubuntu Sans Condensed"
FONT_MONO = "Ubuntu Mono"

FALLBACK_SANS = "Sans Serif"
FALLBACK_MONO = "Monospace"


def load_bundled_fonts() -> list[str]:
    """Register the vendored Ubuntu statics from resource_dir() — never
    data_dir()/config_dir(), these are read-only bundled assets, not user
    data. Returns the family names actually registered so resolve_fonts()
    (and tests) can tell a real load from a fallback. addApplicationFont()
    returns -1 on failure rather than raising, so a missing/corrupt file
    just fails to register — resolve_fonts()'s existing fallback-to-system-
    font chain already handles that, no try/except needed here."""
    fonts_dir = resource_dir() / "resources" / "fonts"
    families: list[str] = []
    for path in sorted(fonts_dir.glob("*.ttf")):
        font_id = QFontDatabase.addApplicationFont(str(path))
        families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return families


def resolve_fonts() -> dict[str, str]:
    """Detect the bundled Ubuntu fonts; fall back cleanly so the app never
    breaks without them (e.g. a build where load_bundled_fonts() found
    nothing to load)."""
    families = set(QFontDatabase.families())
    return {
        "sans": FONT_SANS if FONT_SANS in families else FALLBACK_SANS,
        "sans_condensed": FONT_SANS_CONDENSED if FONT_SANS_CONDENSED in families else FALLBACK_SANS,
        "mono": FONT_MONO if FONT_MONO in families else FALLBACK_MONO,
    }


def _load_stylesheet(fonts: dict[str, str]) -> str:
    qss_path = resource_dir() / "ui" / "theme.qss"
    text = qss_path.read_text(encoding="utf-8")
    active = colors()
    tokens = {f"@{name.replace('_', '-')}@": getattr(active, name) for name in _PALETTE_FIELD_NAMES}
    tokens.update(
        {
            "@font-sans@": fonts["sans"],
            "@font-sans-condensed@": fonts["sans_condensed"],
            "@font-mono@": fonts["mono"],
            "@size-xs@": str(SIZE_XS),
            "@size-sm@": str(SIZE_SM),
            "@size-md@": str(SIZE_MD),
            "@size-lg@": str(SIZE_LG),
            "@size-xl@": str(SIZE_XL),
        }
    )
    for token, value in tokens.items():
        text = text.replace(token, value)
    return text


def apply_theme(app: QApplication, palette_id: str | None = None) -> None:
    if palette_id is not None:
        set_palette(palette_id)
    fonts = resolve_fonts()
    app.setFont(QFont(fonts["sans"], SIZE_SM))
    app.setStyleSheet(_load_stylesheet(fonts))
    # QSS reapplication alone doesn't invalidate a custom paintEvent's pixel
    # content — Qt has no way to know it depends on theme.colors(). Force
    # every widget to redraw so the hand-painted ones pick up the new palette.
    # A themed QIcon (saat.ui.icons.set_icon) is a cached pixmap, not a live
    # paintEvent — the same sweep also calls its _refresh_icon hook if set.
    #
    # allWidgets() materialises a snapshot of raw C++ widget pointers, and
    # both building that snapshot and walking it run Python that allocates.
    # Any allocation can trip CPython's cyclic collector, and a widget the
    # collector frees mid-sweep takes its children down with it — leaving
    # pointers already sitting in the snapshot dangling. Dereferencing one
    # is a segfault, not an exception, so it cannot be caught and retried:
    # hold the collector off for the duration instead, so nothing can be
    # destroyed while the snapshot is in use. Restores the previous state
    # rather than unconditionally enabling, so a caller that deliberately
    # disabled the collector still finds it disabled afterwards.
    collecting = gc.isenabled()
    gc.disable()
    try:
        for widget in QApplication.allWidgets():
            widget.update()
            refresh_icon = getattr(widget, "_refresh_icon", None)
            if refresh_icon is not None:
                refresh_icon()
    finally:
        if collecting:
            gc.enable()
