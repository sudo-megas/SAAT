from dataclasses import dataclass

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from saat.paths import resource_dir

MODE_DARK = "dark"
MODE_LIGHT = "light"


@dataclass(frozen=True)
class Palette:
    plate: str
    plate_high: str
    rule: str
    text: str
    text_muted: str
    gilt: str
    ruby: str


# Two movement plates, not a generic dark-mode app. See SPEC.md §6. Light is
# the same plate under daylight, not an inverted dark mode — same hue
# relationships, lightness re-tuned, gilt/ruby deepened for AA contrast.
_DARK = Palette(
    plate="#1C1B19",
    plate_high="#262421",
    rule="#38352F",
    text="#E8E4DC",
    text_muted="#938C81",  # nudged from spec's #8E877C: measured 4.35:1 on plate-high, below the 4.5:1 bar
    gilt="#C9A227",
    ruby="#CF3931",  # nudged from spec's #9E2B25: measured 2.08:1 on plate-high, below the 3:1 bar
)
_LIGHT = Palette(
    plate="#F1EEE6",
    plate_high="#FFFFFF",
    rule="#DAD4C5",
    text="#2B2822",
    text_muted="#70695E",  # nudged from spec's #7C7568: measured 3.94:1 on plate, below the 4.5:1 bar
    gilt="#8A6A16",
    ruby="#A82F24",
)
_PALETTES = {MODE_DARK: _DARK, MODE_LIGHT: _LIGHT}

_current_mode = MODE_DARK


def current_mode() -> str:
    return _current_mode


def set_mode(mode: str) -> None:
    global _current_mode
    if mode not in _PALETTES:
        raise ValueError(f"unknown theme mode: {mode!r}")
    _current_mode = mode


def colors() -> Palette:
    """The active palette. Read this at paint time, not import time — a
    `from saat.ui.theme import GILT`-style import binds the string once and
    never sees a later toggle. See SPEC.md §6's toggle requirement."""
    return _PALETTES[_current_mode]

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
    palette = colors()
    tokens = {
        "@plate@": palette.plate,
        "@plate-high@": palette.plate_high,
        "@rule@": palette.rule,
        "@text@": palette.text,
        "@text-muted@": palette.text_muted,
        "@gilt@": palette.gilt,
        "@ruby@": palette.ruby,
        "@font-sans@": fonts["sans"],
        "@font-sans-condensed@": fonts["sans_condensed"],
        "@font-mono@": fonts["mono"],
        "@size-xs@": str(SIZE_XS),
        "@size-sm@": str(SIZE_SM),
        "@size-md@": str(SIZE_MD),
        "@size-lg@": str(SIZE_LG),
        "@size-xl@": str(SIZE_XL),
    }
    for token, value in tokens.items():
        text = text.replace(token, value)
    return text


def apply_theme(app: QApplication, mode: str | None = None) -> None:
    if mode is not None:
        set_mode(mode)
    fonts = resolve_fonts()
    app.setFont(QFont(fonts["sans"], SIZE_SM))
    app.setStyleSheet(_load_stylesheet(fonts))
    # QSS reapplication alone doesn't invalidate a custom paintEvent's pixel
    # content — Qt has no way to know it depends on theme.colors(). Force
    # every widget to redraw so the hand-painted ones pick up the new palette.
    for widget in QApplication.allWidgets():
        widget.update()
