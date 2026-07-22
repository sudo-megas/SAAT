import sys

import tomlkit

from saat.atomic import write_atomic
from saat.paths import app_dir


class Config:
    """Reads and writes config.toml: window geometry, last view, column choices."""

    def __init__(self) -> None:
        self.path = app_dir() / "config.toml"
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
