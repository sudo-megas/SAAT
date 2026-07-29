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

    print(f"wrote {out_dir / 'desktop-full.toml'} ({len(written)} bytes) with saat.storage.save_watch")
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_emit = sub.add_parser("emit", help="write a desktop-authored fixture for the Kotlin tests")
    p_emit.add_argument("dir", type=pathlib.Path)

    p_verify = sub.add_parser("verify", help="check what the Kotlin tests wrote")
    p_verify.add_argument("dir", type=pathlib.Path)

    args = parser.parse_args()
    if args.command == "emit":
        return emit(args.dir)
    return verify(args.dir)


if __name__ == "__main__":
    sys.exit(main())
