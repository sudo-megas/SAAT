from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from saat.paths import resource_dir
from saat.ui import theme

ICON_SIZE = 18

_pixmap_cache: dict[tuple[str, str, int], QPixmap] = {}


def _icon_path(name: str) -> str:
    return str(resource_dir() / "resources" / "icons" / f"{name}.svg")


def pixmap(name: str, color: str, size: int = ICON_SIZE) -> QPixmap:
    """`name` rendered at `size`x`size` and recoloured to `color`. SPEC.md §6:
    one SVG per icon, no shipped colour variants — recolouring happens here,
    at render time, against whichever hex the caller passes in. Cached per
    (name, color, size), which self-invalidates across a theme toggle since
    the color string itself changes."""
    key = (name, color, size)
    cached = _pixmap_cache.get(key)
    if cached is not None:
        return cached

    renderer = QSvgRenderer(_icon_path(name))
    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)

    painter = QPainter(result)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(result.rect(), QColor(color))
    painter.end()

    _pixmap_cache[key] = result
    return result


def icon(name: str, color: str, size: int = ICON_SIZE) -> QIcon:
    return QIcon(pixmap(name, color, size))


def set_icon(widget, name: str, color_role: str = "text_muted", size: int = ICON_SIZE) -> None:
    """Attach a themed icon to any widget with .setIcon() (QPushButton,
    QAction, ...). Qt has no theme-changed signal in this app — apply_theme()
    instead sweeps every live widget and calls back into a `_refresh_icon`
    hook if one exists, the same duck-typed pattern that sweep already uses
    for repainting hand-drawn widgets. `color_role` names a Palette field
    (theme.py) read fresh on every refresh, never cached as a color."""
    def _refresh() -> None:
        color = getattr(theme.colors(), color_role)
        widget.setIcon(icon(name, color, size))
    widget._refresh_icon = _refresh
    _refresh()


def set_checkable_icon(
    widget, name: str, checked_color_role: str = "gilt", unchecked_color_role: str = "text_muted",
    size: int = ICON_SIZE,
) -> None:
    """Like set_icon, but for a checkable button whose icon should track its
    own checked state as well as the theme — SPEC.md §6: gilt appears only on
    things that are interactive or currently active, and these buttons
    already turn their *text* gilt when checked (theme.qss). Refreshed on
    toggle (covers both a user click and a programmatic setChecked()) in
    addition to the usual theme-apply sweep."""
    def _refresh() -> None:
        role = checked_color_role if widget.isChecked() else unchecked_color_role
        color = getattr(theme.colors(), role)
        widget.setIcon(icon(name, color, size))
    widget._refresh_icon = _refresh
    widget.toggled.connect(_refresh)
    _refresh()
