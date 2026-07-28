import sys
from pathlib import Path

import tomlkit

from saat.atomic import write_atomic
from saat.paths import config_dir


class Config:
    """Reads and writes config.toml: window geometry, last view, column choices."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else config_dir() / "config.toml"
        self.data = self._load()
        self._migrate_theme_to_palette()

    def _load(self) -> tomlkit.TOMLDocument:
        if not self.path.exists():
            return tomlkit.document()
        try:
            return tomlkit.parse(self.path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"warning: config.toml is malformed, using defaults: {exc}", file=sys.stderr)
            return tomlkit.document()

    def save(self) -> None:
        write_atomic(self.path, tomlkit.dumps(self.data))

    def _migrate_theme_to_palette(self) -> None:
        """Milestone 21b: the old two-value [theme] mode key becomes
        [palette] id, once. Guarded on "id" actually being present, not just
        the [palette] table existing, and never re-fires once it is -- a
        user who has since picked, say, Nord must never be silently reverted
        to default-dark on a later launch just because a stale [theme] table
        still lingers. A fresh config (no [theme] table at all) writes
        nothing here; palette_id()'s own fallback handles "absent means
        default-dark" at read time, the same convention every other
        accessor in this file uses."""
        if "palette" in self.data and "id" in self.data["palette"]:
            return
        theme_table = self.data.get("theme")
        old_mode = theme_table.get("mode") if theme_table else None
        if old_mode is None:
            return
        self.set_palette_id("default-light" if old_mode == "light" else "default-dark")
        self.data.pop("theme", None)
        self.save()

    def window_geometry(self) -> dict | None:
        return self.data.get("window")

    def set_window_geometry(self, geometry: dict) -> None:
        self.data["window"] = geometry

    def last_view(self) -> str | None:
        view = self.data.get("view")
        return view.get("last") if view else None

    def set_last_view(self, view: str) -> None:
        self.data.setdefault("view", tomlkit.table())["last"] = view

    def active_scope(self) -> str | None:
        scope = self.data.get("scope")
        return scope.get("active") if scope else None

    def set_active_scope(self, scope: str) -> None:
        self.data.setdefault("scope", tomlkit.table())["active"] = scope

    def column_keys(self, scope: str = "collection") -> list[str] | None:
        """Column choices are stored per scope — SPEC.md §5.12: Collection
        and Wishlist tables want different defaults, so `scope` picks a
        distinct key under [columns] rather than sharing one."""
        columns = self.data.get("columns")
        keys = columns.get(f"{scope}_keys") if columns else None
        return list(keys) if keys else None

    def set_column_keys(self, keys: list[str], scope: str = "collection") -> None:
        self.data.setdefault("columns", tomlkit.table())[f"{scope}_keys"] = list(keys)

    def picker_mode(self) -> str | None:
        """Milestone 20: Random/Weighted, remembered across launches. §9
        still bans a settings dialog -- this is the picker surface's own
        single toggle persisting itself, the same shape as palette_id()."""
        picker = self.data.get("picker")
        return picker.get("mode") if picker else None

    def set_picker_mode(self, mode: str) -> None:
        self.data.setdefault("picker", tomlkit.table())["mode"] = mode

    def palette_id(self) -> str:
        """Active palette id — absent means default-dark (SPEC.md §6: default
        on first launch stays dark), the same absence-means-default
        convention as every other accessor here rather than an Optional the
        caller has to fall back on."""
        palette = self.data.get("palette")
        return palette["id"] if palette and "id" in palette else "default-dark"

    def set_palette_id(self, palette_id: str) -> None:
        self.data.setdefault("palette", tomlkit.table())["id"] = palette_id

    def language(self) -> str | None:
        """UI language code ("tr") — absent means English, same as
        picker_mode()'s None-means-default shape. Never read from the OS
        locale: the app always starts in English on first run and the
        language is changed manually, by explicit design (SPEC.md)."""
        language = self.data.get("language")
        return language.get("code") if language else None

    def set_language(self, code: str | None) -> None:
        """code=None clears the key, restoring "absent means English" --
        the language menu's English entry must call set_language(None),
        never set_language("en"): saat_en.qm is deliberately never built
        (see saat/ui/i18n.py), so writing the literal "en" would make
        main.py try to load a translation file that doesn't exist by
        design."""
        if code is None:
            self.data.pop("language", None)
        else:
            self.data.setdefault("language", tomlkit.table())["code"] = code

    def close_to_tray(self) -> bool:
        """SPEC.md milestone 18 §8: default OFF. A user who has not opted in
        must never lose their window, so absence of the key means False,
        never a truthy default."""
        tray = self.data.get("tray")
        return bool(tray.get("close_to_tray", False)) if tray else False

    def set_close_to_tray(self, value: bool) -> None:
        self.data.setdefault("tray", tomlkit.table())["close_to_tray"] = value

    def start_minimised(self) -> bool:
        tray = self.data.get("tray")
        return bool(tray.get("start_minimised", False)) if tray else False

    def set_start_minimised(self, value: bool) -> None:
        self.data.setdefault("tray", tomlkit.table())["start_minimised"] = value

    def tray_hint_shown(self) -> bool:
        """Whether the one-time 'still running in the tray' message has
        already been shown -- SPEC.md milestone 18 §10: once, ever."""
        tray = self.data.get("tray")
        return bool(tray.get("hint_shown", False)) if tray else False

    def set_tray_hint_shown(self, value: bool) -> None:
        self.data.setdefault("tray", tomlkit.table())["hint_shown"] = value
