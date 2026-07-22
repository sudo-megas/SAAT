from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from saat.paths import resource_dir

# Palette — a movement plate, not a generic dark-mode app. See SPEC.md §6.
PLATE = "#1C1B19"
PLATE_HIGH = "#262421"
RULE = "#38352F"
TEXT = "#E8E4DC"
TEXT_MUTED = "#8E877C"
GILT = "#C9A227"
RUBY = "#9E2B25"

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

FONT_SANS = "IBM Plex Sans"
FONT_SANS_CONDENSED = "IBM Plex Sans Condensed"
FONT_MONO = "IBM Plex Mono"

FALLBACK_SANS = "Sans Serif"
FALLBACK_MONO = "Monospace"


def resolve_fonts() -> dict[str, str]:
    """Detect IBM Plex; fall back cleanly so the app never breaks without it."""
    families = set(QFontDatabase.families())
    return {
        "sans": FONT_SANS if FONT_SANS in families else FALLBACK_SANS,
        "sans_condensed": FONT_SANS_CONDENSED if FONT_SANS_CONDENSED in families else FALLBACK_SANS,
        "mono": FONT_MONO if FONT_MONO in families else FALLBACK_MONO,
    }


def _load_stylesheet(fonts: dict[str, str]) -> str:
    qss_path = resource_dir() / "ui" / "theme.qss"
    text = qss_path.read_text(encoding="utf-8")
    tokens = {
        "@plate@": PLATE,
        "@plate-high@": PLATE_HIGH,
        "@rule@": RULE,
        "@text@": TEXT,
        "@text-muted@": TEXT_MUTED,
        "@gilt@": GILT,
        "@ruby@": RUBY,
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


def apply_theme(app: QApplication) -> None:
    fonts = resolve_fonts()
    app.setFont(QFont(fonts["sans"], SIZE_SM))
    app.setStyleSheet(_load_stylesheet(fonts))
