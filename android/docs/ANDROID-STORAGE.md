# The Android storage layer

How SAAT for Android reads and writes a collection, what it guarantees, and — the
part worth reading — what it does **not** guarantee.

`docs/schema.md` at the repository root is the contract both apps obey and wins
over anything here. This document covers the Android implementation of it.

## Layout

```
files/
├── watches/<slug>/watch.toml   THE RECORDS — ships empty
├── media/<slug>/<filename>     THE PHOTOGRAPHS — ships empty
├── config.toml                 theme, language
└── backups/
    ├── <slug>-<timestamp>.toml the newest 20, shared across the collection
    └── deleted/<slug>/         a removed watch, whole
```

The photographs are not inside each watch's folder, unlike on the desktop.
Android's Auto Backup rules match `path` as a literal prefix and support no
wildcards at all, so SPEC-ANDROID §3.1's rule — back up the records, never the
photographs — is only expressible if the two are separate top-level trees. The
ZIP contract is unchanged: export re-roots the photographs back into
`watches/<slug>/images/`, so the archive is exactly the desktop's shape.

That works only because a watch's `images` key holds **bare filenames rather than
paths**, so it must continue to.

## Byte preservation, and its limit

**The guarantee.** A watch loaded from disk and never edited is never rewritten.
Loading the collection writes nothing at all. Saving a record whose model still
equals what came off disk is a no-op — the check lives in `WatchStore.save`, not
only in the repository, so no caller can bypass it by holding a record and
saving in a loop.

**The limit, stated plainly.** The first time you edit a watch on the phone, its
`watch.toml` is **regenerated**, and anything that was in the file but not in the
data model is lost: comments, blank lines, key order, the choice between `41` and
`41.0`.

This is a real difference from the desktop app, which keeps the parsed document
attached to each record and mutates it key by key, so a hand-written comment on
one field survives an edit to a different field. No Kotlin TOML library offers an
equivalent, and pretending otherwise would be worse than saying so: a comment you
believe is safe and is not is more expensive than one you know is temporary.

So: hand-written comments survive on the phone until that watch's first edit
there. Files you never edit on the phone keep their bytes forever.

## Reading files the app did not write

`watch.toml` is a file you are invited to hand-edit, so the loader is built to
survive one. Only **two** things are fatal, because only two mean "this is not a
watch":

- TOML that will not parse at all
- a missing or blank `brand` or `model`

Either produces a record carrying a `loadError`. It stays in the collection and
appears in the UI with its error, rather than vanishing — never a crash, never a
silent skip.

Everything else loads, and one bad field costs exactly one field:

| the file says | the app does |
|---|---|
| `rating = "4"` | reads `4` |
| `diameter_mm = 41` | reads `41.0` |
| `rating = 4.0` | reads `4` |
| `hacking = 1` | reads `true` |
| `tags = "diver"` | reads `["diver"]` |
| `[straps]` where `[[straps]]` was meant | reads one strap |
| `worn = [2024-03-12T09:30:00]` | reads the day, drops the time |
| `rating = "high"` | leaves it absent, **and warns** |
| two straps marked `fitted` | loads both as-is, **and warns** |

The rule behind the table: coerce in silence when the intent is unambiguous and
nothing is lost; warn and leave the field absent when the value cannot become the
field's type without inventing something. A warning names the field and quotes
what was there, and travels out with the record for the UI to surface — never a
log line (SPEC-ANDROID hard rule 6).

Nothing is ever corrected on your behalf. Two fitted straps is a statement you
made in a file; the app reports it and lets the edit form fix it when you next
tick one.

## Slugs

Ported clause by clause from the desktop's `saat/storage.py`, not redesigned — a
slug generated differently on the two platforms is a watch that duplicates itself
the first time a collection crosses between them.

Brand + model, lowercased, everything outside `[a-z0-9]` collapsed to hyphens,
capped at 80 characters, Windows device names (`con`, `nul`, `lpt1`…) suffixed
with `-watch`, collisions resolved case-insensitively with `-2`, `-3`.

Two results that look wrong and are correct, because they are what the desktop
produces:

- `Züblin` → `z-blin`. Accented letters are dropped, not folded to ASCII.
- `İzmir` → `i-zmir`. `İ` lowercases to `i` plus a combining dot, and the
  combining mark becomes a separator.

**The Turkish dotless-i trap** is handled by using Kotlin's locale-independent
`lowercase()`. A locale-sensitive lowercase maps `I` to `ı` on a Turkish phone;
`ı` is outside `[a-z0-9]`, so `Seiko` would slug as `seko` on that phone and
nowhere else. `SlugTest` proves the independence by flipping the default locale
rather than by asserting a comment.

## Backups and deletion

Before an edit rewrites a `watch.toml`, the previous version is copied to
`backups/<slug>-<timestamp>.toml`, and the directory is pruned to the newest 20.
A wear-date toggle skips the snapshot: one calendar gesture can touch many
watches, and 20 slots shared across the collection would otherwise fill with
evictable toggles and evict a real one.

Deleting moves a watch rather than erasing it. Both of its trees go, and they
**rejoin** into one folder shaped like a desktop watch:

```
backups/deleted/<slug>/watch.toml
backups/deleted/<slug>/images/…
```

so a deleted watch is self-contained, reads as a watch to anyone browsing the
files, and can be zipped without transforming. `backups/deleted/` is a directory,
so it never competes with the 20-file budget.

## Parity with the desktop, checked rather than asserted

`android/tools/parity_check.py` runs the **desktop's own code** — `saat/storage.py`
and `saat/models.py` — on both sides of the Gradle build. It is affordable
because the desktop's storage layer has no GUI dependency: it imports `tomlkit`
and the standard library and nothing else.

```sh
pip install tomlkit==0.15.1

# 1. the desktop writes a fully-populated watch for the Android tests to read
python3 android/tools/parity_check.py emit android/app/build/parity-in

# 2. the Android tests read it, and write their own for the desktop to read
cd android && ./gradlew check

# 3. the desktop reads what Android wrote, and diffs the field maps
cd .. && python3 android/tools/parity_check.py verify \
    android/app/build/reports/parity
```

Step 3 reports the parity checklist AM2 asks for, generated from the encoder's
real output rather than hand-copied from `docs/schema.md`:

```
  android-full.toml: loaded by saat.storage with every field intact
  android-minimal.toml: loaded by saat.storage with every field intact
  field map: all 66 schema fields present, none renamed
```

A schema field that is missing, renamed or misspelled on the Android side fails
the Android build. So does a date emitted as a quoted string, which is the
failure that would otherwise wait until AM10's ZIP bridge to be discovered.

The fixture watch is constructed **in code, twice** — once in Kotlin, once in
Python — and that duplication is the test. Nothing is committed as fixture data
on either side; hard rule 1 applies to test assets exactly as it applies to
shipped code.

## Deferred, deliberately

- **Image filename sanitisation.** The desktop's `safe_image_filename` has no
  caller until the images editor exists, so it lands with AM5 rather than sitting
  here untested in anger.
- **The wear index and one-watch-per-day.** Derived per watch here; the
  collection-wide date→watch index belongs to the calendar in AM7.
- **`withSingleFitted` is written but never called.** The at-most-one-fitted-strap
  rule is about the moment the owner ticks a strap, which is AM5's form.
