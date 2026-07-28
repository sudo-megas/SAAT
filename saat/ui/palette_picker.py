"""The bottom bar's palette control (SPEC.md §6) — a swatch button showing
the active palette, opening a popover that lists all ten fixed presets in
SPEC.md §6's order. Once Milestone 21b-e retires the top-bar sun/moon
toggle, this is the app's only palette-changing affordance."""

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QWidget, QWidgetAction

from saat.ui import theme
from saat.ui.theme import PaletteEntry

_DOT_DIAMETER = 6
_DOT_GAP = 3
_SWATCH_SIZE = _DOT_DIAMETER * 3 + _DOT_GAP * 2

_BUTTON_SIZE = 24
_ROW_HEIGHT = 32


class _PaletteSwatch(QWidget):
    """Three dots -- plate, text, gilt -- for one palette. entry=None paints
    whichever palette is currently ACTIVE, read fresh at paint time so it
    self-updates through apply_theme()'s own allWidgets() sweep with no
    extra hook (the same discipline as every other custom-painted widget in
    the app). A supplied entry paints that one specific, possibly-inactive
    palette forever -- this is how the popover shows all nine non-active
    rows without ever calling theme.colors() for them (SPEC.md §6: zero
    hardcoded hex in this commit)."""

    def __init__(self, entry: PaletteEntry | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry = entry
        self.setFixedSize(_SWATCH_SIZE, _DOT_DIAMETER)

    def paintEvent(self, event: QPaintEvent) -> None:
        pal = self._entry.palette if self._entry is not None else theme.colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        radius = _DOT_DIAMETER / 2
        x = radius
        for color in (pal.plate, pal.text, pal.gilt):
            painter.setBrush(QColor(color))
            painter.drawEllipse(QPointF(x, radius), radius, radius)
            x += _DOT_DIAMETER + _DOT_GAP
        painter.end()


class _PaletteRow(QWidget):
    """One popover row: swatch + display name + a checkmark on the active
    entry. Clicking anywhere in the row selects that palette. Background is
    transparent (not the base QWidget rule's opaque @plate@) so QMenu's own
    ::item:selected hover highlight shows through underneath it."""

    clicked = Signal(str)

    def __init__(self, entry: PaletteEntry, is_active: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._palette_id = entry.id
        self.setProperty("class", "palette-row")
        self.setFixedHeight(_ROW_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 8, 4)
        layout.setSpacing(10)
        layout.addWidget(_PaletteSwatch(entry))
        label = QLabel(theme.display_name(entry))
        layout.addWidget(label, 1)
        check = QLabel("✓" if is_active else "")
        check.setFixedWidth(14)
        layout.addWidget(check)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit(self._palette_id)
        super().mouseReleaseEvent(event)


class PalettePickerButton(QWidget):
    """The bottom bar's own swatch button (SPEC.md §6 item 26). Click opens
    a QMenu popover listing all ten presets; picking one applies immediately
    and closes it."""

    palette_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(_BUTTON_SIZE, _BUTTON_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._swatch = _PaletteSwatch(entry=None, parent=self)
        self._swatch.move((_BUTTON_SIZE - _SWATCH_SIZE) // 2, (_BUTTON_SIZE - _DOT_DIAMETER) // 2)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self._show_popover()
        super().mouseReleaseEvent(event)

    def _show_popover(self) -> None:
        menu = self._build_menu()
        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def _build_menu(self) -> QMenu:
        """Split from _show_popover() so tests can build and interact with
        the real menu -- its row order, checkmarks, and click -> _apply()
        wiring -- without ever calling QMenu.exec() themselves. exec() runs
        a real nested Qt event loop, which this codebase has already hit a
        confirmed segfault from late in a full `unittest discover` run with
        its accumulated deleteLater() backlog (see test_retranslation.py's
        _pump() docstring for the original repro) -- not worth risking
        again for a test that doesn't need a shown, positioned popup to
        verify its actual logic."""
        menu = QMenu(self)
        active_id = theme.current_palette_id()
        for entry in theme.palettes():
            row = _PaletteRow(entry, is_active=(entry.id == active_id))
            action = QWidgetAction(menu)
            action.setDefaultWidget(row)
            row.clicked.connect(lambda palette_id, m=menu: self._apply(palette_id, m))
            action.triggered.connect(lambda checked=False, palette_id=entry.id, m=menu: self._apply(palette_id, m))
            menu.addAction(action)
        return menu

    def _apply(self, palette_id: str, menu: QMenu) -> None:
        menu.close()
        if palette_id == theme.current_palette_id():
            return
        self.palette_selected.emit(palette_id)
        self._swatch.update()
