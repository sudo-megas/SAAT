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

    def theme_mode(self) -> str | None:
        theme = self.data.get("theme")
        return theme.get("mode") if theme else None

    def set_theme_mode(self, mode: str) -> None:
        self.data.setdefault("theme", tomlkit.table())["mode"] = mode
