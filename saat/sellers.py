import sys
from dataclasses import dataclass
from pathlib import Path

import tomlkit

from saat.atomic import write_atomic
from saat.storage import backup_watch_toml

SELLERS_FILENAME = "sellers.toml"


@dataclass
class Seller:
    name: str
    url: str | None = None
    city: str | None = None
    notes: str | None = None


def sellers_path(data_dir: Path) -> Path:
    """SPEC.md §3: lives in data_dir() beside watches/, not config_dir() —
    user-authored content that travels with the collection, not UI state."""
    return data_dir / SELLERS_FILENAME


def load_sellers(path: Path) -> list[Seller]:
    """Ships absent — a missing file is an empty seller directory, not an
    error. A malformed file warns (same tolerance as config.py's own
    malformed-file handling) rather than crashing the app over what is,
    unlike a watch.toml, optional convenience data."""
    if not path.exists():
        return []
    try:
        doc = tomlkit.parse(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"warning: sellers.toml is malformed, ignoring it: {exc}", file=sys.stderr)
        return []
    return [
        Seller(name=str(entry["name"]), url=entry.get("url"), city=entry.get("city"), notes=entry.get("notes"))
        for entry in doc.get("seller", [])
        if entry.get("name")
    ]


def save_sellers(backups_dir: Path, path: Path, sellers: list[Seller]) -> None:
    """Rebuilt fresh via tomlkit on every save, the same treatment
    docs/schema.md already documents for watch.toml's own array-of-table
    sections (straps/log/timing) — no per-entry comment preservation, kept
    deliberately simple. Backed up through the same pruned-to-20 rotation
    as everything else in backups/ (SPEC.md §3: sellers.toml "falls under
    the backup scheme"), reusing storage.backup_watch_toml verbatim."""
    if path.exists():
        backup_watch_toml(backups_dir, "sellers", path)

    doc = tomlkit.document()
    aot = tomlkit.aot()
    for seller in sellers:
        entry = tomlkit.table()
        entry["name"] = seller.name
        if seller.url:
            entry["url"] = seller.url
        if seller.city:
            entry["city"] = seller.city
        if seller.notes:
            entry["notes"] = seller.notes
        aot.append(entry)
    doc["seller"] = aot
    write_atomic(path, tomlkit.dumps(doc))


def find_seller(sellers: list[Seller], name: str) -> Seller | None:
    """Exact, case-sensitive match — SPEC.md §3's loose coupling: a watch's
    acquisition.seller is a plain string, matched against sellers.toml by
    name alone, never a stored reference."""
    return next((s for s in sellers if s.name == name), None)
