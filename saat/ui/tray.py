from typing import Callable

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from saat.paths import resource_dir
from saat.storage import WatchRecord
from saat.ui.wear_stats import last_worn

MAX_WORE_TODAY_ENTRIES = 10

# Common sizes Linux tray implementations request (KDE/Plasma commonly asks
# for 22px, AppIndicator-based hosts commonly 24px) plus a few standard
# fallbacks, so whichever the host wants Qt has a matching resolution rather
# than scaling one raster -- SPEC.md milestone 18 explicitly warns not to
# assume a 256px PNG downscales cleanly to tray sizes.
_ICON_SIZES = (16, 22, 24, 32, 48, 64)


def _app_icon() -> QIcon:
    """Rendered straight from the app's own SVG at each tray size, not the
    hand-drawn, recolourable icon set in resources/icons/ -- this is brand
    identity with its own fixed colours, the same source main.py's window
    icon eventually renders from too."""
    svg_path = str(resource_dir() / "resources" / "icon" / "saat.svg")
    renderer = QSvgRenderer(svg_path)
    icon = QIcon()
    for size in _ICON_SIZES:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap)
    return icon


def _wore_today_sort_key(record: WatchRecord) -> tuple:
    """Most-recently-worn first; watches never worn sort last, by name --
    there is no date left to rank them by."""
    worn = last_worn(record.watch)
    name = (record.watch.brand.casefold(), record.watch.model.casefold())
    if worn is None:
        return (1, 0, *name)
    return (0, -worn.toordinal(), *name)


class TrayController(QObject):
    """Owns the QSystemTrayIcon and its context menu. A pure UI component --
    MainWindow supplies a window-visibility getter and current records, and
    reacts to this class's signals for every state change, the same
    signals-out/no-disk-I/O shape CollectionView and WatchForm already use.

    Only constructed when QSystemTrayIcon.isSystemTrayAvailable() -- checked
    once, at startup, by the caller -- so every code path here can assume a
    real tray exists."""

    show_hide_requested = Signal()
    wore_today_requested = Signal(object)
    close_to_tray_toggled = Signal(bool)
    start_minimised_toggled = Signal(bool)
    quit_requested = Signal()

    def __init__(self, window_visible_getter: Callable[[], bool], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._window_visible_getter = window_visible_getter
        self._records: list[WatchRecord] = []

        self._icon = QSystemTrayIcon(_app_icon(), self)
        self._icon.setToolTip("SAAT")
        self._icon.activated.connect(self._on_activated)

        self._menu = QMenu()
        self._show_hide_action = self._menu.addAction("Hide")
        self._show_hide_action.triggered.connect(self.show_hide_requested)

        self._wore_today_menu = self._menu.addMenu("Wore today")

        self._menu.addSeparator()

        self._close_to_tray_action = self._menu.addAction("Close to tray")
        self._close_to_tray_action.setCheckable(True)
        self._close_to_tray_action.toggled.connect(self.close_to_tray_toggled)

        self._start_minimised_action = self._menu.addAction("Start minimised")
        self._start_minimised_action.setCheckable(True)
        self._start_minimised_action.toggled.connect(self.start_minimised_toggled)

        self._menu.addSeparator()
        quit_action = self._menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_requested)

        self._menu.aboutToShow.connect(self._refresh_menu)
        self._icon.setContextMenu(self._menu)

    def set_records(self, records: list[WatchRecord]) -> None:
        self._records = records

    def set_close_to_tray_checked(self, value: bool) -> None:
        self._close_to_tray_action.setChecked(value)

    def set_start_minimised_checked(self, value: bool) -> None:
        self._start_minimised_action.setChecked(value)

    def show(self) -> None:
        self._icon.show()

    def hide(self) -> None:
        self._icon.hide()

    def supports_messages(self) -> bool:
        return self._icon.supportsMessages()

    def show_hint_message(self) -> None:
        self._icon.showMessage(
            "SAAT",
            "Still running in the tray. Click the icon to bring the window back.",
            QSystemTrayIcon.MessageIcon.Information,
        )

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # Right click is handled by Qt itself via setContextMenu() -- this
        # only needs to cover left click (Trigger).
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_hide_requested.emit()

    def _refresh_menu(self) -> None:
        self._show_hide_action.setText("Hide" if self._window_visible_getter() else "Show")
        self._rebuild_wore_today_menu()

    def _rebuild_wore_today_menu(self) -> None:
        self._wore_today_menu.clear()
        owned = [r for r in self._records if r.watch is not None and r.watch.status == "Owned"]
        ranked = sorted(owned, key=_wore_today_sort_key)[:MAX_WORE_TODAY_ENTRIES]

        if not ranked:
            empty_action = self._wore_today_menu.addAction("No owned watches")
            empty_action.setEnabled(False)
            return

        for record in ranked:
            label = f"{record.watch.brand} {record.watch.model}"
            action = self._wore_today_menu.addAction(label)
            action.triggered.connect(lambda checked=False, r=record: self.wore_today_requested.emit(r))
