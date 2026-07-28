import dataclasses
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import tomlkit

from saat.atomic import write_atomic
from saat.models import (
    Acquisition,
    Case,
    Dial,
    LogEntry,
    Maintenance,
    Movement,
    Strap,
    TimingEntry,
    Watch,
)

WATCH_FILENAME = "watch.toml"
BACKUP_KEEP = 20

_SLUG_INVALID = re.compile(r"[^a-z0-9]+")

# Windows refuses these as a whole filename component, on every drive, with
# or without an extension: they are DOS device names and predate long
# filenames. A slug is a directory name, so `con` or `lpt1` would be an
# unwritable folder — and the brand or model producing one need not be
# exotic, since the sanitiser above has already reduced whatever was typed
# to [a-z0-9-].
#
# Guarded on every platform, not only Windows, for the same reason the
# case-insensitivity rule below is: a collection has to stay loadable in
# both directions. A folder Linux happily creates and Windows cannot open
# is a collection that stops being portable the moment it is copied across.
_WINDOWS_RESERVED_NAMES = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{n}" for n in range(1, 10)}
    | {f"lpt{n}" for n in range(1, 10)}
)

# Windows' own path limit is 260 characters by default, and a slug is only
# one component of a path that also holds the data directory, `watches/`,
# `images/` and a filename. Brand and model are free text with no length
# limit of their own, so a pasted product description would otherwise
# become a directory nothing downstream could write into. Truncation can
# create a collision; unique_slug already resolves those.
_SLUG_MAX_LENGTH = 80


@dataclass
class WatchRecord:
    """A watch as loaded from disk: the parsed model plus the bookkeeping needed
    to save it back. `watch` and `document` are None when the file failed to
    load — `load_error` explains why, and the UI shows the slug with an error
    badge instead of crashing."""

    slug: str
    path: Path
    watch: Watch | None = None
    document: tomlkit.TOMLDocument | None = None
    load_error: str | None = None


def is_hidden_entry(name: str) -> bool:
    return name.startswith("_") or name.startswith(".")


def slugify(brand: str, model: str) -> str:
    """A directory name derived from brand + model, safe on every
    filesystem this app runs on.

    The character class does most of the work and always did: reducing to
    [a-z0-9-] removes all nine characters Windows forbids in a filename
    (< > : " / \\ | ? *) as a side effect of removing everything that isn't
    alphanumeric, and the trailing strip removes the trailing dots and
    spaces Windows also rejects. What it cannot see are the two rules that
    are about the name as a whole rather than its characters — reserved
    device names, and length."""
    base = f"{brand} {model}".strip().lower()
    base = _SLUG_INVALID.sub("-", base).strip("-")
    if len(base) > _SLUG_MAX_LENGTH:
        base = base[:_SLUG_MAX_LENGTH].rstrip("-")
    if not base:
        return "watch"
    if base in _WINDOWS_RESERVED_NAMES:
        # Suffixed rather than rejected: the owner typed a real brand and
        # model, and the folder name is an implementation detail they
        # should not have to work around.
        return f"{base}-watch"
    return base


def unique_slug(brand: str, model: str, existing: set[str]) -> str:
    """Disambiguate against what is already on disk, case-INSENSITIVELY.

    slugify() lowercases, so two generated slugs can never differ only by
    case — the exposure is hand-authored folders, which SPEC.md §3
    explicitly supports (copy `_template.toml` into
    `watches/<some-slug>/watch.toml`). A folder someone created as
    `Seiko-SKX007` beside a generated `seiko-skx007` is two watches on
    ext4 and one on NTFS: on Windows the second save would open the first
    watch's folder and overwrite it.

    Compared case-insensitively on every platform, so a collection stays
    loadable in both directions. On Linux this costs one extra distinct
    slug in a case that would otherwise have silently produced two folders
    a Windows user could never separate."""
    base = slugify(brand, model)
    taken = {name.casefold() for name in existing}
    if base.casefold() not in taken:
        return base
    n = 2
    while f"{base}-{n}".casefold() in taken:
        n += 1
    return f"{base}-{n}"


def load_collection(watches_dir: Path) -> list[WatchRecord]:
    if not watches_dir.exists():
        return []
    records = []
    for entry in sorted(watches_dir.iterdir()):
        if not entry.is_dir() or is_hidden_entry(entry.name):
            continue
        records.append(_load_watch(entry))
    return records


def _load_watch(folder: Path) -> WatchRecord:
    slug = folder.name
    toml_path = folder / WATCH_FILENAME
    if not toml_path.exists():
        return WatchRecord(slug=slug, path=folder, load_error=f"{WATCH_FILENAME} not found")

    try:
        text = toml_path.read_text(encoding="utf-8")
    except OSError as exc:
        return WatchRecord(slug=slug, path=folder, load_error=str(exc))

    try:
        document = tomlkit.parse(text)
    except Exception as exc:
        return WatchRecord(slug=slug, path=folder, load_error=str(exc))

    try:
        watch = _watch_from_document(document)
    except Exception as exc:
        return WatchRecord(slug=slug, path=folder, document=document, load_error=str(exc))

    return WatchRecord(slug=slug, path=folder, watch=watch, document=document)


def _dataclass_from_table(cls, table) -> object:
    kwargs = {}
    for f in dataclasses.fields(cls):
        if f.name not in table:
            continue
        value = table[f.name]
        if isinstance(value, list):
            value = list(value)
        kwargs[f.name] = value
    return cls(**kwargs)


def _watch_from_document(doc: tomlkit.TOMLDocument) -> Watch:
    brand = doc.get("brand")
    model = doc.get("model")
    if not isinstance(brand, str) or not brand.strip():
        raise ValueError("missing required field: brand")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("missing required field: model")

    return Watch(
        brand=brand,
        model=model,
        reference=doc.get("reference"),
        nickname=doc.get("nickname"),
        serial=doc.get("serial"),
        group=doc.get("group"),
        style=doc.get("style"),
        status=doc.get("status", "Owned"),
        storage=doc.get("storage"),
        rating=doc.get("rating"),
        tags=list(doc.get("tags", [])),
        movement=_dataclass_from_table(Movement, doc.get("movement", {})),
        case=_dataclass_from_table(Case, doc.get("case", {})),
        dial=_dataclass_from_table(Dial, doc.get("dial", {})),
        straps=[_dataclass_from_table(Strap, s) for s in doc.get("straps", [])],
        acquisition=_dataclass_from_table(Acquisition, doc.get("acquisition", {})),
        maintenance=_dataclass_from_table(Maintenance, doc.get("maintenance", {})),
        log=[_dataclass_from_table(LogEntry, entry) for entry in doc.get("log", [])],
        worn=list(doc.get("worn", [])),
        timing=[_dataclass_from_table(TimingEntry, entry) for entry in doc.get("timing", [])],
        notes=doc.get("notes"),
        images=list(doc.get("images", [])),
    )


def _set_or_create_table(doc, name: str):
    if name not in doc or not isinstance(doc.get(name), dict):
        doc[name] = tomlkit.table()
    return doc[name]


def _sync_scalar(table, key: str, value) -> None:
    if value is None:
        if key in table:
            del table[key]
        return
    table[key] = value


def _sync_table(table, obj) -> None:
    for f in dataclasses.fields(obj):
        value = getattr(obj, f.name)
        if isinstance(value, list):
            table[f.name] = list(value)
        else:
            _sync_scalar(table, f.name, value)


def _build_aot(entries):
    aot = tomlkit.aot()
    for entry in entries:
        item = tomlkit.table()
        _sync_table(item, entry)
        aot.append(item)
    return aot


def _apply_watch_to_document(watch: Watch, doc: tomlkit.TOMLDocument) -> None:
    _sync_scalar(doc, "brand", watch.brand)
    _sync_scalar(doc, "model", watch.model)
    _sync_scalar(doc, "reference", watch.reference)
    _sync_scalar(doc, "nickname", watch.nickname)
    _sync_scalar(doc, "serial", watch.serial)
    _sync_scalar(doc, "group", watch.group)
    _sync_scalar(doc, "style", watch.style)
    _sync_scalar(doc, "status", watch.status)
    _sync_scalar(doc, "storage", watch.storage)
    _sync_scalar(doc, "rating", watch.rating)
    doc["tags"] = list(watch.tags)

    _sync_table(_set_or_create_table(doc, "movement"), watch.movement)
    _sync_table(_set_or_create_table(doc, "case"), watch.case)
    _sync_table(_set_or_create_table(doc, "dial"), watch.dial)
    doc["straps"] = _build_aot(watch.straps)
    _sync_table(_set_or_create_table(doc, "acquisition"), watch.acquisition)
    _sync_table(_set_or_create_table(doc, "maintenance"), watch.maintenance)
    doc["log"] = _build_aot(watch.log)
    doc["worn"] = list(watch.worn)
    doc["timing"] = _build_aot(watch.timing)

    _sync_scalar(doc, "notes", watch.notes)
    doc["images"] = list(watch.images)


def create_watch(watches_dir: Path, backups_dir: Path, watch: Watch) -> WatchRecord:
    existing = {p.name for p in watches_dir.iterdir() if p.is_dir()} if watches_dir.exists() else set()
    slug = unique_slug(watch.brand, watch.model, existing)
    record = WatchRecord(slug=slug, path=watches_dir / slug, watch=watch)
    return save_watch(backups_dir, record)


def save_watch(backups_dir: Path, record: WatchRecord, backup: bool = True) -> WatchRecord:
    """`backup=False` skips the pre-write snapshot — for saves that aren't a
    "destructive operation" in SPEC.md §3's sense, e.g. a wear-date toggle
    from the calendar. That path can touch many watches in one gesture, and
    backups/ is pruned to a shared 20 slots; every caller that edits
    hand-typed fields must keep the default so evictable wear-toggle
    snapshots never crowd out a real one."""
    assert record.watch is not None
    folder = record.path
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "images").mkdir(exist_ok=True)

    toml_path = folder / WATCH_FILENAME
    if backup and toml_path.exists():
        backup_watch_toml(backups_dir, record.slug, toml_path)

    document = record.document if record.document is not None else tomlkit.document()
    _apply_watch_to_document(record.watch, document)
    write_atomic(toml_path, tomlkit.dumps(document))

    return dataclasses.replace(record, document=document, load_error=None)


def delete_watch(backups_dir: Path, record: WatchRecord) -> None:
    toml_path = record.path / WATCH_FILENAME
    backup_watch_toml(backups_dir, record.slug, toml_path)

    deleted_dir = backups_dir / "deleted"
    deleted_dir.mkdir(parents=True, exist_ok=True)
    destination = deleted_dir / record.slug
    if destination.exists():
        destination = deleted_dir / f"{record.slug}-{_timestamp()}"
    shutil.move(str(record.path), str(destination))


def backup_watch_toml(backups_dir: Path, slug: str, toml_path: Path) -> None:
    if not toml_path.exists():
        return
    backups_dir.mkdir(parents=True, exist_ok=True)

    base_name = f"{slug}-{_timestamp()}"
    dest = backups_dir / f"{base_name}.toml"
    n = 2
    while dest.exists():
        dest = backups_dir / f"{base_name}-{n}.toml"
        n += 1

    shutil.copy2(toml_path, dest)
    _prune_backups(backups_dir)


def _prune_backups(backups_dir: Path, keep: int = BACKUP_KEEP) -> None:
    files = [p for p in backups_dir.iterdir() if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime)
    excess = len(files) - keep
    if excess <= 0:
        return
    for path in files[:excess]:
        path.unlink()


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%dT%H%M%S")
