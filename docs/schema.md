# watch.toml schema

Each watch is one folder under `watches/<slug>/`, holding `watch.toml` and an
`images/` folder. This documents how the data model (SPEC.md §4) maps onto the
TOML file — SPEC.md is authoritative on fields and their meaning; this is the
concrete shape.

## Layout

Identity fields sit at the top level. Everything else groups into a table
matching its section in SPEC.md §4, except `worn`, which is a flat array —
see `watches/_template.toml` for a fully-commented example.

```toml
brand = "Seiko"
model = "SARB033"
reference = "SARB033"
nickname = ""
serial = ""
group = "Seiko Group"
style = "Dress"
status = "Owned"
storage = ""
rating = 4
tags = ["daily", "grail"]
worn = [2024-01-01, 2024-01-02]   # flat array of dates, nothing else

[movement]
caliber = "6R15"
...

[case]
...

[dial]
...

[[straps]]        # one block per strap
material = "Leather"
fitted = true

[acquisition]
...

[maintenance]
...

[[log]]            # one block per service/battery/regulation/note entry
date = 2024-01-01
kind = "Service"
note = "Full service"

[[timing]]          # one block per timing reading
date = 2024-01-01
deviation_sec = 3
position = "Dial Up"

notes = "A daily beater."
```

## Why identity is flat but everything else is a table

`log`, `timing` and `straps` carry multiple fields per entry, so each is an
array of tables (`[[log]]`). `worn` is nothing but dates (SPEC.md §4), so it's
a plain TOML array — an array of tables for a single scalar would be noise.

## Where `worn` goes in the file, and why it matters

`worn` is a top-level key, so it must appear **before the first table header**,
alongside `tags` and `notes`. This is a TOML rule, not a preference: after
`[[log]]`, a bare key belongs to that log entry, so a `worn` written at the
bottom of the file silently becomes `log[N].worn` and the wear history is gone
with no error from either app.

Both apps write it in the right place — each hoists top-level keys above the
tables — so this only bites a file typed by hand. An earlier version of the
example below showed `worn` beneath `[[log]]` and would have produced exactly
that loss if copied literally; it was moved up when the Android storage layer
was built. `watches/_template.toml` still shows it in the low position, but
commented out, so it is safe until uncommented in place.

## Round-tripping

`saat/storage.py` loads `watch.toml` with `tomlkit.parse()` and keeps the
parsed `TOMLDocument` attached to the in-memory record. Saving mutates that
same document in place — setting or deleting individual keys — rather than
regenerating the file from the dataclass. That's what lets a hand-written
comment on one field survive an edit to a different field. Array-of-table
sections (`straps`, `log`, `timing`) and `worn` are rebuilt fresh on every
save, since diffing per-entry comments inside a reordering list isn't worth
the complexity — SPEC.md's round-trip example is a comment on a scalar field.

## Slugs

`<slug>` is generated once, at creation, from `brand` + `model` (SPEC.md §3).
Editing brand/model later does not rename the folder — the slug is an
identifier, not a live mirror of those fields.

## What's intentionally not here yet

Image ordering and "which photo is primary" aren't in SPEC.md §4's field
tables. That storage decision is deferred to the milestone that builds the
Images tab (SPEC.md §5.7), so it can be shaped by what the UI actually needs
instead of guessed at now.
