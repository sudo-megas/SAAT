#!/usr/bin/env python3
"""Cross-implementation parity between the Android storage layer and the desktop app.

AM2's acceptance criterion is not "does it work" but "does it read and write what
the desktop reads and writes". This script is that criterion, executable: it runs
the DESKTOP'S OWN CODE -- `saat/storage.py`, `saat/models.py` -- against files the
Android tests wrote, and against a file it writes for them to read.

That is possible cheaply because the desktop's storage layer has no GUI
dependency at all: `saat.storage` imports `tomlkit` and the standard library and
nothing else, so one `pip install tomlkit` buys the real loader rather than a
reimplementation of it that could drift.

Two subcommands, run either side of the Gradle build:

    emit <dir>      writes desktop-full.toml, exactly as saat.storage.save_watch
                    produces it, for the Kotlin tests to read back
    verify <dir>    loads the TOML the Kotlin tests wrote using
                    saat.storage.load_collection and asserts every field
                    survived, then diffs the field maps
    enums [root]    diffs the enum* suggestion lists the two forms offer,
                    parsed from both sources -- see the note above `enums`
    zip <dir>       opens the ZIP the Kotlin tests exported with
                    saat.storage.load_collection -- AM10's release gate,
                    answered by the desktop rather than by the phone

The fixture below is the twin of `fullyPopulatedWatch()` in the Kotlin test
sources. The duplication is the point: two independent constructions of the same
watch, each written and read by its own implementation. If they ever stop
agreeing the build goes red here, rather than in AM10 when the ZIP bridge is
being built on top of the assumption that they agree.

Nothing here is committed as data. The fixture is code, on both sides -- hard
rule 1 applies to test assets exactly as it applies to shipped code.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import json
import pathlib
import zipfile
import re
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from saat.models import (  # noqa: E402
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
from saat.storage import WatchRecord, load_collection, save_watch  # noqa: E402

# The five fields of Watch that are a nested table in the file...
GROUPS = ("movement", "case", "dial", "acquisition", "maintenance")
# ...and the three that are an array of tables.
LISTS_OF_TABLES = ("straps", "log", "timing")

GROUP_TYPES = {
    "movement": Movement,
    "case": Case,
    "dial": Dial,
    "acquisition": Acquisition,
    "maintenance": Maintenance,
    "straps": Strap,
    "log": LogEntry,
    "timing": TimingEntry,
}


def fully_populated_watch() -> Watch:
    """The twin of fullyPopulatedWatch() in TestWatches.kt. Every field set, and
    every value distinctive -- a field left at its default would round-trip
    successfully whether or not the other side knows it exists."""
    return Watch(
        brand="Grand Seiko",
        model="SBGA211",
        reference="SBGA211",
        nickname="Snowflake",
        serial="D1234567",
        group="Seiko Group",
        style="Dress",
        status="Owned",
        storage="Winder slot 2",
        rating=5,
        tags=["grail", "daily", "İzmir"],
        movement=Movement(
            caliber="9R65",
            kind="Spring Drive",
            power_reserve_hours=72.0,
            battery_life_years=2.5,
            accuracy_min=-1.0,
            accuracy_max=1.0,
            accuracy_unit="sec/day",
            jewels=30,
            bph=28800,
            hacking=True,
            handwinding=False,
            origin="Japan",
        ),
        case=Case(
            diameter_mm=41.0,
            lug_to_lug_mm=49.0,
            thickness_mm=12.5,
            lug_width_mm=19,
            material="Titanium",
            crystal="Sapphire",
            crown="Push-pull",
            bezel="Fixed",
            caseback="Exhibition",
            water_resistance_m=100,
            weight_g=100.5,
        ),
        dial=Dial(
            colour="White",
            material="Snowflake pattern",
            indices="Applied",
            lume="LumiBrite",
            complications=["Power Reserve", "Date"],
        ),
        straps=[
            Strap(
                material="Titanium Bracelet",
                colour="Silver",
                width_mm=19,
                clasp="Butterfly",
                fitted=True,
                image="bracelet.jpg",
            ),
            Strap(material="Leather", colour="Brown", clasp="Pin Buckle", fitted=False),
        ],
        acquisition=Acquisition(
            date=datetime.date(2024, 3, 11),
            price=4200.5,
            currency="TRY",
            seller="Saat Dünyası",
            url="https://example.com/sbga211",
            condition="New",
            box_and_papers=True,
            warranty_until=datetime.date(2027, 3, 11),
            target_price=3900.0,
            target_date=datetime.date(2024, 1, 1),
        ),
        maintenance=Maintenance(
            service_interval_years=5.5,
            battery_due=datetime.date(2027, 1, 1),
        ),
        log=[
            LogEntry(date=datetime.date(2024, 3, 11), kind="Note", note="Bought in İzmir"),
            LogEntry(date=datetime.date(2025, 1, 2), kind="Service", note="Full service"),
        ],
        worn=[
            datetime.date(2024, 3, 12),
            datetime.date(2024, 3, 13),
            datetime.date(2025, 1, 1),
        ],
        timing=[
            TimingEntry(date=datetime.date(2024, 4, 1), deviation_sec=0.5, position="Dial Up"),
            TimingEntry(date=datetime.date(2024, 5, 1), deviation_sec=-1.25, position="Crown Down"),
        ],
        notes="A daily wearer.\nSecond line of notes.",
        images=["front.jpg", "clasp.jpg"],
    )


def minimal_watch() -> Watch:
    return Watch(brand="Casio", model="F-91W")


def desktop_field_map() -> dict:
    """The schema as the desktop's dataclasses actually define it -- read by
    reflection, so it cannot be a stale hand-copy of docs/schema.md."""
    top = [
        f.name
        for f in dataclasses.fields(Watch)
        if f.name not in GROUPS and f.name not in LISTS_OF_TABLES
    ]
    return {
        "top": top,
        "groups": {g: [f.name for f in dataclasses.fields(GROUP_TYPES[g])] for g in GROUPS},
        "lists_of_tables": {
            g: [f.name for f in dataclasses.fields(GROUP_TYPES[g])] for g in LISTS_OF_TABLES
        },
    }


# ---------------------------------------------------------------------------


def emit(out_dir: pathlib.Path) -> int:
    """Write the fixture with the desktop's own writer, for Kotlin to read."""
    out_dir.mkdir(parents=True, exist_ok=True)

    staging = pathlib.Path(tempfile.mkdtemp())
    slug = "grand-seiko-sbga211"
    save_watch(
        staging / "backups",
        WatchRecord(slug=slug, path=staging / "watches" / slug, watch=fully_populated_watch()),
    )
    written = (staging / "watches" / slug / "watch.toml").read_text(encoding="utf-8")
    (out_dir / "desktop-full.toml").write_text(written, encoding="utf-8")

    (out_dir / "desktop-fields.json").write_text(
        json.dumps(desktop_field_map(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # AM10: the same record, zipped in the desktop's own layout, for the Android
    # import path to accept. Written from the tree save_watch just produced --
    # not assembled entry by entry here -- so it is the desktop's real output
    # being handed over rather than this script's idea of it.
    (staging / "watches" / slug / "images").mkdir(parents=True, exist_ok=True)
    (staging / "watches" / slug / "images" / "front.jpg").write_bytes(bytes(range(256)) * 4)

    archive = out_dir / "desktop-export.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted((staging / "watches").rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(staging).as_posix())

    print(f"wrote {out_dir / 'desktop-full.toml'} ({len(written)} bytes) with saat.storage.save_watch")
    print(f"wrote {archive} in the desktop's watches/ layout")
    return 0


def verify(reports: pathlib.Path) -> int:
    failures: list[str] = []

    # --- 1. Android's output, through the desktop's real loader --------------
    for name, expected in (("android-full.toml", fully_populated_watch()),
                           ("android-minimal.toml", minimal_watch())):
        source = reports / name
        if not source.exists():
            failures.append(f"{name} was not produced by the Kotlin tests")
            continue

        staging = pathlib.Path(tempfile.mkdtemp()) / "watches" / "under-test"
        staging.mkdir(parents=True)
        (staging / "watch.toml").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

        records = load_collection(staging.parent)
        record = records[0]

        if record.load_error:
            failures.append(f"{name}: the desktop could not load it -- {record.load_error}")
            continue

        differences = list(compare(expected, record.watch))
        for field, mine, theirs in differences:
            failures.append(f"{name}: {field} -- desktop read {theirs!r}, expected {mine!r}")
        if not differences:
            print(f"  {name}: loaded by saat.storage with every field intact")

    # --- 2. the field maps ---------------------------------------------------
    kotlin_map_file = reports / "kotlin-fields.json"
    if not kotlin_map_file.exists():
        failures.append("kotlin-fields.json was not produced by the Kotlin tests")
    else:
        kotlin_map = json.loads(kotlin_map_file.read_text(encoding="utf-8"))
        failures.extend(diff_field_maps(desktop_field_map(), kotlin_map))

    # --- report --------------------------------------------------------------
    print()
    if failures:
        print("PARITY FAILED")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("PARITY OK -- every schema field maps, and both implementations read each other's files")
    return 0


def compare(expected: Watch, actual: Watch):
    """Field-by-field difference between two watches, named by their TOML path."""
    for f in dataclasses.fields(Watch):
        mine, theirs = getattr(expected, f.name), getattr(actual, f.name)

        if f.name in GROUPS:
            for sub in dataclasses.fields(GROUP_TYPES[f.name]):
                a, b = getattr(mine, sub.name), getattr(theirs, sub.name)
                if not equal(a, b):
                    yield f"{f.name}.{sub.name}", a, b
        elif f.name in LISTS_OF_TABLES:
            if len(mine) != len(theirs):
                yield f"{f.name} (length)", len(mine), len(theirs)
                continue
            for i, (a_entry, b_entry) in enumerate(zip(mine, theirs)):
                for sub in dataclasses.fields(GROUP_TYPES[f.name]):
                    a, b = getattr(a_entry, sub.name), getattr(b_entry, sub.name)
                    if not equal(a, b):
                        yield f"{f.name}[{i}].{sub.name}", a, b
        elif not equal(mine, theirs):
            yield f.name, mine, theirs


def equal(a, b) -> bool:
    """tomlkit hands back Integer/Float/String/Date subclasses rather than the
    builtins, and they compare equal to them -- but a date that came back as a
    STRING would also compare unequal, which is exactly the failure worth
    catching, so the type is checked as well as the value."""
    if a is None or b is None:
        return a is b
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, datetime.date) and not isinstance(b, datetime.date):
        return False
    if isinstance(a, str) and not isinstance(b, str):
        return False
    if isinstance(a, (int, float)) and not isinstance(b, (int, float)):
        return False
    return a == b


def diff_field_maps(desktop: dict, kotlin: dict) -> list[str]:
    problems: list[str] = []

    def compare_names(where: str, theirs: list, ours: list) -> None:
        missing = [n for n in theirs if n not in ours]
        extra = [n for n in ours if n not in theirs]
        if missing:
            problems.append(f"{where}: Android never writes {missing} -- present in saat/models.py")
        if extra:
            problems.append(f"{where}: Android writes {extra} -- absent from saat/models.py")

    compare_names("top level", desktop["top"], kotlin.get("top", []))

    for section in ("groups", "lists_of_tables"):
        for name, fields in desktop[section].items():
            if name not in kotlin.get(section, {}):
                problems.append(f"{name}: Android writes no such section at all")
                continue
            compare_names(name, fields, kotlin[section][name])

        for name in kotlin.get(section, {}):
            if name not in desktop[section]:
                problems.append(f"{name}: Android writes a section the desktop has no field for")

    if not problems:
        total = (
            len(desktop["top"])
            + sum(len(v) for v in desktop["groups"].values())
            + sum(len(v) for v in desktop["lists_of_tables"].values())
        )
        print(f"  field map: all {total} schema fields present, none renamed")

    return problems



# --- enum* suggestion lists (AM5) -------------------------------------------
#
# The third thing that can drift, and the one that is invisible in English.
#
# The Android form offers ninety-nine suggested values across seventeen enum*
# lists, and every one of them is DATA: the canonical English string is what
# lands in watch.toml and what the desktop reads back. A value renamed on one
# side -- "Stainless Steel" becoming "Stainless steel" -- does not fail any
# test, does not fail the field-map check (the field is still there), and does
# not fail a round trip (the string survives). It simply means the two apps
# offer different vocabularies for the same field, and a collection edited on
# both grows two spellings of everything.
#
# So the lists are compared directly, desktop source against Android source.
# Parsed with `ast` rather than imported, because watch_form.py imports PySide6
# and CI has no Qt -- and because a parse cannot execute anything.

# desktop identifier -> Android identifier in EnumChoices.kt
ENUM_LISTS = {
    "GROUP_SUGGESTIONS": "GROUPS",
    "STYLE_SUGGESTIONS": "STYLES",
    "STATUS_OPTIONS": "STATUSES",
    "MOVEMENT_KIND_SUGGESTIONS": "MOVEMENT_KINDS",
    "ACCURACY_UNIT_OPTIONS": "ACCURACY_UNITS",
    "CASE_MATERIAL_SUGGESTIONS": "CASE_MATERIALS",
    "CRYSTAL_SUGGESTIONS": "CRYSTALS",
    "CROWN_SUGGESTIONS": "CROWNS",
    "BEZEL_SUGGESTIONS": "BEZELS",
    "CASEBACK_SUGGESTIONS": "CASEBACKS",
    "INDICES_SUGGESTIONS": "INDICES",
    "COMPLICATIONS_SUGGESTIONS": "COMPLICATIONS",
    "STRAP_MATERIAL_SUGGESTIONS": "STRAP_MATERIALS",
    "STRAP_CLASP_SUGGESTIONS": "CLASPS",
    "CONDITION_OPTIONS": "CONDITIONS",
    "LOG_KIND_OPTIONS": "LOG_KINDS",
    "TIMING_POSITION_OPTIONS": "TIMING_POSITIONS",
}

DESKTOP_ENUM_SOURCES = ("saat/ui/watch_form.py", "saat/ui/list_editors.py")
ANDROID_ENUM_SOURCE = "android/app/src/main/kotlin/io/github/sudomegas/saat/ui/form/EnumChoices.kt"


def _literal(node) -> str | None:
    """The string a list element carries, through QT_TRANSLATE_NOOP or bare."""
    import ast as _ast

    if isinstance(node, _ast.Constant) and isinstance(node.value, str):
        return node.value
    # QT_TRANSLATE_NOOP("EnumChoices", "Stainless Steel") -- a runtime
    # pass-through whose second argument is the canonical value.
    if isinstance(node, _ast.Call) and node.args:
        last = node.args[-1]
        if isinstance(last, _ast.Constant) and isinstance(last.value, str):
            return last.value
    return None


def desktop_enums(root: pathlib.Path) -> dict[str, list[str]]:
    import ast as _ast

    found: dict[str, list[str]] = {}
    for relative in DESKTOP_ENUM_SOURCES:
        tree = _ast.parse((root / relative).read_text(encoding="utf-8"))
        for node in _ast.walk(tree):
            if not isinstance(node, _ast.Assign):
                continue
            names = [t.id for t in node.targets if isinstance(t, _ast.Name)]
            if not names or names[0] not in ENUM_LISTS:
                continue
            if not isinstance(node.value, (_ast.List, _ast.Tuple)):
                continue
            values = [_literal(element) for element in node.value.elts]
            if all(v is not None for v in values):
                found[names[0]] = values
    return found


def android_enums(root: pathlib.Path) -> dict[str, list[str]]:
    text = (root / ANDROID_ENUM_SOURCE).read_text(encoding="utf-8")
    found: dict[str, list[str]] = {}
    # val NAME: List<EnumChoice> = listOf( choice("Value", R.string.key), ... )
    for match in re.finditer(r"val (\w+): List<EnumChoice> = listOf\((.*?)\n\)", text, re.S):
        name, body = match.group(1), match.group(2)
        found[name] = re.findall(r'choice\("((?:[^"\\]|\\.)*)"', body)
    return found


def enums(root: pathlib.Path) -> int:
    desktop = desktop_enums(root)
    android = android_enums(root)

    problems: list[str] = []
    for desktop_name, android_name in ENUM_LISTS.items():
        expected = desktop.get(desktop_name)
        actual = android.get(android_name)
        if expected is None:
            problems.append(f"{desktop_name}: not found in the desktop sources")
            continue
        if actual is None:
            problems.append(f"{android_name}: not found in {ANDROID_ENUM_SOURCE}")
            continue
        if expected != actual:
            problems.append(
                f"{desktop_name} -> {android_name} differ\n"
                f"    desktop: {expected}\n"
                f"    android: {actual}"
            )

    if problems:
        print("ENUM PARITY FAILED", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(
            "\nThese strings are DATA: they are written into watch.toml and read by\n"
            "both apps. A value spelled differently on the two sides means a\n"
            "collection edited on both grows two spellings of the same thing.",
            file=sys.stderr,
        )
        return 1

    total = sum(len(v) for v in desktop.values())
    print(f"ENUM PARITY OK -- {total} values across {len(ENUM_LISTS)} lists match the desktop")
    return 0


def zip_bridge(reports: pathlib.Path) -> int:
    """AM10's release gate, answered by the desktop.

    The Android tests export a real collection to saat-export.zip. This unzips
    it into a scratch directory and loads it with the DESKTOP'S OWN
    load_collection -- which is the actual claim SPEC-ANDROID 3.2 makes about
    the archive: "unzipping it into the desktop app's folder IS the import on
    that side". A layout the desktop cannot read fails here, and nothing the
    Android tests can assert about themselves would have caught it.
    """
    archive = reports / "saat-export.zip"
    if not archive.exists():
        print(f"ZIP BRIDGE FAILED\n  {archive} was not produced by the Kotlin tests", file=sys.stderr)
        return 1

    scratch = pathlib.Path(tempfile.mkdtemp())
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        zf.extractall(scratch)

    watches_dir = scratch / "watches"
    if not watches_dir.is_dir():
        print(
            "ZIP BRIDGE FAILED\n"
            f"  the archive has no watches/ root -- entries were: {names[:5]}",
            file=sys.stderr,
        )
        return 1

    failures: list[str] = []
    records = load_collection(watches_dir)
    if not records:
        failures.append("the desktop loader found no watches in the exported archive")

    for record in records:
        if record.load_error:
            failures.append(f"{record.slug}: the desktop could not load it -- {record.load_error}")
            continue

        # The photographs must land where the desktop expects them, which is the
        # whole reason the export re-roots media/ back into images/.
        images = record.path / "images"
        if not images.is_dir() or not any(images.iterdir()):
            failures.append(f"{record.slug}: no images/ folder in the archive")

        for field, mine, theirs in compare(fully_populated_watch(), record.watch):
            failures.append(f"{record.slug}: {field} -- desktop read {theirs!r}, expected {mine!r}")

    print()
    if failures:
        print("ZIP BRIDGE FAILED", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        print(
            "\nSPEC-ANDROID 3.2: unzipping the export into the desktop app's folder IS\n"
            "the import on that side. If this fails, that promise is broken and v1.0\n"
            "is not shippable -- AM10 is the release gate.",
            file=sys.stderr,
        )
        return 1

    print(
        f"ZIP BRIDGE OK -- {len(records)} watch(es) exported by Android, "
        "loaded by saat.storage.load_collection with every field intact"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_emit = sub.add_parser("emit", help="write a desktop-authored fixture for the Kotlin tests")
    p_emit.add_argument("dir", type=pathlib.Path)

    p_verify = sub.add_parser("verify", help="check what the Kotlin tests wrote")
    p_verify.add_argument("dir", type=pathlib.Path)

    p_enums = sub.add_parser("enums", help="diff the enum* suggestion lists against the desktop")
    p_enums.add_argument("root", type=pathlib.Path, nargs="?", default=pathlib.Path("."))

    p_zip = sub.add_parser("zip", help="open the Android export with the desktop's loader")
    p_zip.add_argument("dir", type=pathlib.Path)

    args = parser.parse_args()
    if args.command == "emit":
        return emit(args.dir)
    if args.command == "enums":
        return enums(args.root)
    if args.command == "zip":
        return zip_bridge(args.dir)
    return verify(args.dir)


if __name__ == "__main__":
    sys.exit(main())
