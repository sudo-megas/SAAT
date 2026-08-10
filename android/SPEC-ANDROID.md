# SAAT Android — Watch Collection Manager

**Project specification. This document is authoritative for everything under
`/android`.** The desktop `SPEC.md` remains authoritative for the desktop app. Where
the two describe the same data, `docs/schema.md` at the repository root is the
contract both implementations obey, and it wins.

---

## 1. Brief

Full SAAT on a phone. The same application idea — catalogue a personal wristwatch
collection, photo-forward grid, per-attribute spec study, wear calendar, detail page,
two-up compare, add/edit form — rebuilt natively for Android because the phone is the
device that is *present when a watch goes on the wrist*. Wear logging is therefore a
first-class citizen: a home-screen widget and an app shortcut record today's watch in
two taps without opening the app.

**Ship it empty.** Same rule as the desktop, same reason.

Stack: Kotlin, Jetpack Compose, Material 3. `minSdk 26` (Android 8.0), `targetSdk`
the latest stable. Single user, offline, no accounts, no cloud of ours.

The desktop app is done and tagged; this project must never require touching it.

---

## 2. Hard rules

Non-negotiable. Do not improve past them.

1. **No seed data. No demo watches. No sample collection.** First launch shows an
   empty state. Tests build fixtures in temp directories at runtime and delete them.
   Screenshots come from the owner's real collection, taken by the owner — never
   fabricated.
   **The one sanctioned exception, for testing:** a developer action, present in
   **debug builds only**, that generates exactly **two demo watches** in code at
   tap time — one mechanical with most fields filled (straps, log, worn days,
   timing readings), one quartz with almost nothing beyond brand and model, and
   neither with photos, so the placeholder tile gets exercised too. They are
   generated, never committed to the repository, never bundled as assets, and a
   test asserts the mechanism is absent from release builds. Release APKs ship
   empty, always.
2. **Zero permissions.** The merged manifest declares no `<uses-permission>` at all.
   No INTERNET, no CAMERA, no storage permissions. Camera capture goes through the
   `ACTION_IMAGE_CAPTURE` intent, file export/import through the Storage Access
   Framework, photos in through the system Photo Picker — none of which need a
   permission. A test parses the merged manifest and fails the build if any
   permission ever appears. This is the strongest privacy claim an Android app can
   make and it is verifiable by anyone.
3. **No network.** Follows from rule 2, but stated on its own because it is the
   philosophy, not a side effect. The single exception is handing a URL to the
   system browser on explicit user tap — a hand-off, not a request.
4. **No database.** No SQLite, no Room, no ORM. The TOML files are the truth,
   parsed at launch into an in-memory index — a hobby collection fits in RAM
   hundreds of times over. Thumbnails and image caches live in `cacheDir` and are
   disposable at any moment.
5. **Dependency budget.** The approved list is §2.1. Anything beyond it needs
   written justification in the commit message. Never, under any justification:
   analytics, crash reporting, advertising, Firebase, or any SDK whose value is
   telemetry.
6. **Never silently swallow an exception.** Surface it in the UI with the message
   intact — a dialog or snackbar, not a log line.
7. **Storage is canonical English.** Enum values in `watch.toml` are data, written
   and read in English regardless of UI language. The UI language defaults to
   English and is changed only by an explicit control in Settings — the app never
   reads the system locale to choose its language. Both rules are carried over
   verbatim from desktop M21.
8. **No derived files inside `watches/`.** Original images only. Thumbnails,
   caches and indexes live outside the data tree, so the exported ZIP is always
   clean data and nothing else.

### 2.1 Approved dependencies

Kotlin stdlib and coroutines; AndroidX core, activity, lifecycle, navigation,
**appcompat**; Compose BOM with Material 3; Coil for image loading (decoding and
caching collection photos is genuinely hard to do well by hand); **one TOML
library — `tomlkt`, chosen in AM1** with the measurements recorded in that
milestone's commit message; Glance for the widget; JUnit and Robolectric for
tests. That is the whole list.

**Glance was removed in AM8, and the widget is plain RemoteViews.** This entry
was written before anyone checked what Glance depends on. Every published
version declares `androidx.work:work-runtime`, and `GlanceAppWidget`'s
*constructor* resolves `androidx.work.CoroutineWorker` — it is the class itself,
not an optional path something could exclude, which was measured rather than
assumed: with the dependency excluded the widget crashed on a real phone with
`NoClassDefFoundError` before drawing a pixel.

Keeping WorkManager breaks two hard rules at once. It injects WAKE_LOCK,
ACCESS_NETWORK_STATE, RECEIVE_BOOT_COMPLETED and FOREGROUND_SERVICE into the
merged manifest — hard rule 2, and `verifyReleaseManifestPolicy` failed on all
four the moment Glance went in — and it brings `androidx.sqlite`, which hard
rule 4 forbids by name. The hard rules are non-negotiable; this list is a
budget. So the widget uses `RemoteViews`, which needs no dependency at all, and
Glance is off the approved list.

Three entries changed after this section was first written, and the reasons
belong here rather than only in a commit message:

- **`androidx.appcompat` was added.** Hard rule 7 below says the app never reads
  the system locale and defaults to English. On Android that is not a default you
  inherit — resource resolution follows the system locale the moment `values-tr/`
  exists — so the English default must be actively asserted at every process
  start. The only supported mechanism across the whole `minSdk 26` range is
  `AppCompatDelegate.setApplicationLocales`, which requires this library, an
  `AppCompatActivity`, and a `Theme.AppCompat`-descended XML theme hosting the
  Compose theme. The framework's own `LocaleManager` is API 33+ and would leave
  26–32 unserved. Taken in AM1 rather than AM11 because the Activity base class
  and theme parent are expensive to change once every screen exists.
  `kotlinx-serialization-core` arrives transitively with the TOML library and the
  Navigation type-safe routes; it is a serialization runtime, not an SDK.

- **The TOML library moved from AM2 to AM1.** Choosing it while the only consumer
  is `config.toml` means that if it turns out to be wrong, switching costs one
  file rather than the whole storage layer — and AM2 then inherits a library
  already proven against a watch-shaped fixture.

---

## 3. Storage

App-private internal storage (`filesDir`):

```
files/
├── watches/                   THE RECORDS — ships empty
│   └── <slug>/
│       └── watch.toml
├── media/                     THE PHOTOGRAPHS — ships empty
│   └── <slug>/
│       └── <filenames as listed in that watch's `images` key>
├── config.toml                theme, language, last view, sort choices
└── backups/                   timestamped copies, pruned to the newest 20
    └── deleted/               a removed watch's folders move here first
```

**Why photographs are not inside `watches/<slug>/images/`, unlike the desktop.**
Android's Auto Backup rules match `path` as a literal prefix and support no
wildcards whatsoever. With photographs nested inside each watch's folder, §3.1's
rule — back up the records, never the photographs — cannot be written down:
`<exclude path="watches/*/images"/>` is not valid syntax, and enumerating one
exclude per slug is impossible because slugs are created at runtime. Separating
the two trees is what makes the rule expressible, as two static `<include>`
lines that cannot rot as the schema changes.

This changes only the phone's internal layout. **The ZIP contract in §3.2 is
unchanged**: export re-roots `media/<slug>/*` back into `watches/<slug>/images/*`
so the archive is exactly the desktop's shape, and import splits them apart
again. Desktop compatibility lives in the archive, not in `filesDir`.

Two consequences to carry forward: deleting a watch moves **both**
`watches/<slug>/` and `media/<slug>/` into `backups/deleted/`, and this works
only because a watch's `images` key holds bare filenames rather than paths —
so it must continue to.

`cacheDir` holds thumbnails and Coil's cache — disposable, never backed up, never
exported.

Rules for the storage layer, identical to desktop where they overlap:

- `<slug>` derives from brand + model, lowercased, ASCII-safe, non-alphanumerics to
  hyphens. The Turkish dotless-i casing trap is handled (desktop M21 rule).
  Collisions are detected **case-insensitively** and resolved with `-2`, `-3`
  (desktop M24 rule — adopted here from day one so a collection moves in both
  directions between platforms without surprises).
- Any file or directory whose name starts with `_` or `.` is skipped by the loader.
- Writes are atomic: temp file, then rename.
- A malformed `watch.toml` is skipped with a visible notice naming the file and the
  parse error. Never a crash, never silent.
- **Byte preservation.** An imported `watch.toml` keeps its original bytes; the app
  rewrites a file only when the user edits that watch. A hand-written file's
  comments therefore survive until its first edit on the phone — state this limit
  honestly in the docs rather than pretending Kotlin TOML writers preserve
  comments the way tomlkit does.

### 3.1 Cloud backup

Android Auto Backup is **allowed** — pragmatism won, by the owner's decision.
Records are backed up; photographs never are. The quota is roughly 25 MB, the
records must always fit, and photographs would exhaust it — so they are excluded
by rule rather than truncated by luck. Records are irreplaceable; photographs are
re-takeable, and the ZIP export is their safety net.

The rule is **include-only**, which is what makes it safe:

```xml
<include domain="file" path="watches"/>
<include domain="file" path="config.toml"/>
```

Presence of any `<include>` makes everything unlisted excluded, so `media/`,
`backups/` and `cacheDir` are left out by omission rather than by a rule someone
must remember to update. There are no wildcards to get wrong and nothing to keep
in sync with the schema.

> An earlier draft of this section specified "include `watches/**/watch.toml`,
> exclude every `images/` directory". That is not expressible — the backup rules
> format has no wildcard support at all. §3's separate `media/` tree exists to
> make this rule writable; see the note there.

On Android 12+ the equivalent `data_extraction_rules.xml` splits backup from
device transfer, and the two are deliberately **not** the same. `<cloud-backup>`
carries records only, as above. `<device-transfer>` — phone to phone, during
setup — has no quota and never leaves the two devices, so it carries the
photographs too. Moving to a new phone brings the whole collection; a cloud
restore brings the records and leaves the photographs to the ZIP.

### 3.2 The ZIP contract

The ZIP is not a backup format. It is the bridge to the desktop app.

- **Export:** the exact `watches/` tree, zipped from the `watches/` root
  (`watches/<slug>/watch.toml`, `watches/<slug>/images/...`), written wherever the
  user picks via `ACTION_CREATE_DOCUMENT`. Filename `saat-export-YYYY-MM-DD.zip`.
  Unzipping it into the desktop app's folder *is* the import on that side.
- **Import:** `ACTION_OPEN_DOCUMENT`. Accept an archive rooted at `watches/` or
  directly at slug level — desktop users will zip it both ways, detect which.
  A slug that already exists on the phone is **skipped**; only new watches are
  added. Finish with a summary: n added, n skipped, named.
- **Round-trip acceptance test (AM10):** a fixture tree in desktop format imports,
  exports, and semantically equals the original — every field, every list, every
  image byte-identical; untouched `watch.toml` files byte-identical.

---

## 4. Data model

`docs/schema.md` at the repository root is the contract. The Android
implementation reads and writes exactly what the desktop reads and writes. Parity
points restated because they are easy to drop in a rewrite:

- Dates: ISO in storage, `DD.MM.YYYY` in the UI. `worn` entries are plain local
  calendar dates — no times, no time zones.
- `water_resistance_m` stored in metres, always; the form accepts bar/atm and
  converts (1 bar ≈ 10 m); display metres with the bar equivalent in parentheses.
- Currency defaults to TRY.
- Fields marked `enum*` are suggestions, not constraints: an editable dropdown
  offering the listed values plus every value already used in the collection, and
  accepting free text.
- An absent field renders as a muted em-dash within a shown group; a wholly empty
  group is hidden, not rendered as dashes.
- At most one strap per watch is `fitted` — enforced.
- Derived, never stored: last worn, days since worn, times worn this year, longest
  streak, next service due (latest Service log entry + `service_interval_years`),
  frequency in Hz (bph ÷ 7200).

---

## 5. Interface

### 5.1 Navigation

Bottom navigation bar, four destinations: **Grid, Specs, Calendar, Settings.**
A top app bar on Grid and Specs carries search and the sort menu. "Add watch" is a
FAB on the Grid — the one primary-weight control in the app, same rule as desktop.
Detail, form and compare are full screens pushed above the tabs; the system back
gesture always means back, never exit-with-lost-state.

### 5.2 Grid

Image-forward cards, two columns portrait, three landscape. Primary photo at the
desktop's 4:5 portrait crop, brand as overline, model as title, style and movement
kind as small metadata. A watch with no photo gets the neutral placeholder tile
with diameter and lug width set in the middle. A watch due (or overdue) for
service carries a small accent dot. Long-press enters selection mode, which feeds
Compare. There is no hover on touch, so "Wore this today" lives on the detail
page, the widget and the app shortcut — not on the card.

### 5.3 Specs (the table view, rethought)

The desktop's dense table cannot survive a 6-inch portrait screen, so it becomes a
**single-column spec list with a preset switcher**: a chip row — Identity,
Movement, Case, Dial, Straps, Acquisition — and beneath it one row per watch:
thumbnail, brand + model, then that family's key fields in tabular figures. Tap a
row for the detail page. The point survives even though the columns did not:
studying the whole collection against one family of attributes at a time.

### 5.4 Compare

Exactly **two watches, side by side, portrait**. Entered from grid selection mode.
Watches as columns, attributes as rows in the model's order; rows where both share
a value are dimmed, rows that differ sit at full contrast, rows where neither has
a value are hidden. Same reading logic as desktop, sized for a hand.

### 5.5 Calendar

Month grid, seven columns, weeks starting Monday. A day with a watch shows its
primary photo square-cropped filling the cell, day number over a subtle scrim; an
empty day shows its number muted; today carries an accent hairline border.

Touch grammar, replacing the desktop's mouse grammar:

- Tap an empty day → picker bottom sheet: search field plus the collection as
  thumbnails. Pick one, the day fills.
- Tap a filled day → the picker opens with the current watch marked; picking
  another replaces it; Clear empties it.
- **Long-press a day → range mode:** extend the selection to a span, pick one
  watch, the whole span fills. This is how a year of backlog gets entered.
- Every day is editable, past or future. Future days are how you plan.

Rules unchanged from desktop: **one watch per day across the whole collection** —
assigning an owned day moves it silently; wear history stored per watch in its own
`worn` list, never centralised; the date→watch index is built in memory at load;
no concept of a rest day.

Footer strip: days recorded, distinct watches worn, and the watches *not* worn
this month. **Year view** toggled in the header: twelve compact month grids,
cells as colour chips, one hue per watch derived deterministically from its slug.

**"Pick for me"** — ported from the desktop's `saat/ui/today_picker.py`, single
day only; the desktop's week planner (`pick_week`) is out of scope. A button
below the footer, always visible, always today regardless of which month is on
screen. Opens a sheet drawing only from Owned watches: **Random** (uniform) or
**Weighted** (favours whatever was worn least recently, via a gentle
collection-relative curve that never truly excludes a recently-worn watch),
persisted in `config.toml`'s `[picker]` table and switchable in the sheet
itself. Choosing re-rolls immediately; **Re-roll** rolls again; nothing is
written until **"Wore this today"** is tapped, which commits through the same
`WatchRepository.assignWorn` every other wear entry point uses. Special-cased
for zero owned watches (a message, nothing to pick) and exactly one (a name
and a single confirm button — no toggle, no re-roll, nothing to roll between).
No tumble or settle animation on the reveal — §6's "no celebratory animation"
rules that out; the chosen watch is shown plainly the instant the sheet opens.

### 5.6 Detail

A full screen with a back affordance. Large primary image, thumbnail strip
beneath. Wear stats line: last worn, days since, times worn this year, longest
streak, plus the compact twelve-month strip of this watch's days — hidden when it
has never been worn. A single **"Wore this today"** button: one tap, no dialog,
idempotent within a local calendar date.

Spec groups in the model's order, single column: Movement, Case, Dial, Straps,
Acquisition, Maintenance, Log, Timing, Notes. Empty groups hidden. Straps render
as small cards with their own photo, the fitted one marked. Strap compatibility:
straps belonging to *other* watches whose `width_mm` matches this watch's
`case.lug_width_mm`, hidden when there are no matches. A maintenance line appears
at the top only when service is due within 90 days or overdue — silent otherwise,
silent entirely when the interval is blank. The timing sparkline renders at three
or more readings. Edit and Delete at the bottom; Delete requires typing the model
name.

### 5.7 Add / edit form

One full-screen **scrolling page with collapsible group headers** in spec order —
not tabs. Tabs on a phone hide what is unfilled; a scroll shows the whole shape of
the record. Numeric fields get numeric keyboards and unit suffixes inside the
field. The Movement group swaps `power_reserve_hours` for `battery_life_years`
and changes the accuracy unit when `kind` is Quartz or Solar. The Images group
offers the system Photo Picker and the camera intent, copies files into the
watch's `images/`, allows reordering and setting the primary. **Saving with only
brand and model filled must succeed.** Validation blocks nothing else. Backing
out with unsaved changes prompts.

### 5.8 Empty states

Same discipline as desktop. Collection empty: centred and quiet — a line stating
the collection is empty, a sentence that watches are plain TOML files the owner
can export at any time, one primary button to add the first watch. No
illustration, no mascot, no exclamation marks. Calendar empty: an empty month
plus one muted line explaining that tapping a day records what was worn.

### 5.9 Widget and shortcuts

A Glance home-screen widget showing **today**: the assigned watch's photo and
name, or "Nothing recorded today". Tapping an empty widget opens the picker for
today; tapping a filled one opens that watch's detail page. It updates at
midnight and whenever today's assignment changes. Static app shortcuts on the
launcher icon: **Wore this today** (straight to the picker) and **Add watch**
(straight to the form).

### 5.10 Settings

Theme: System / Light / Dark. Dynamic colour toggle on Android 12+. Language:
English / Turkish, explicit control, no locale sniffing. Export ZIP. Import ZIP.
About: version, GPL-3.0, source link (opens the browser — the one permitted
hand-off).

### 5.11 Collection summary

Footer of the filter sheet: watch count, split by movement kind, total
acquisition value by currency. Plain figures. No charts, no gauges, no progress
rings.

### 5.12 Search and filters

Fuzzy search across brand, model, reference, caliber and tags, from the top bar
on Grid and Specs. Filters live in a bottom sheet: Status, Style, Group, Movement
kind, Case material, Lug width, Tags, `Not worn in 90 days` — each multi-select
with live counts, facets with no values hidden. The desktop sidebar, folded into
a sheet.

---

## 6. Design language

**Material 3 with dynamic colour** — the owner chose system feel over porting the
desktop identity. On Android 12+ the palette derives from the user's wallpaper;
below 12, a static fallback palette modelled on the desktop's Default Light and
Default Dark. The desktop's gilt and ruby roles map to Material accent roles, so
the maintenance dot and today's border stay meaningful in any palette.

The restraint carries over even though the palette engine does not: hairline
dividers, no decoration beyond Material defaults, no empty-state art, no
celebratory animation. Light and dark are both first-class and both get a
contrast pass.

---

## 7. Milestones

| # | versionName | What |
|---|---|---|
| AM1 | 0.1 | Scaffold: Gradle, Compose, 4-tab shell, theme, zero-permission manifest, CI |
| AM2 | 0.2 | Storage layer: model, TOML I/O, slugs, atomic writes, backups, tests |
| AM3 | 0.3 | Grid + empty state + sort + search |
| AM4 | 0.4 | Detail view + wear stats + "Wore this today" |
| AM5 | 0.5 | Add/edit form + images + delete |
| AM6 | 0.6 | Specs list + filter sheet + collection summary |
| AM7 | 0.7 | Calendar + wear tracking + year view |
| AM8 | 0.8 | Widget + app shortcuts |
| AM9 | 0.9 | Compare + timing + maintenance + strap compatibility |
| AM10 | 0.10 | ZIP export/import + round-trip test + backup rules |
| AM11 | 1.0 | Turkish, signing, release workflow, README — **the public release** |
| AM12 | — | Distribution: IzzyOnDroid, F-Droid metadata |

v1.0 ships after AM11 and never before AM10 — releasing an app that cannot export
its data would betray everything SAAT stands for. Debug builds are sideloaded on
the owner's phone from AM3 onward.

---

## 8. Build and release

Gradle Kotlin DSL with a version catalog. `applicationId` is
`io.github.sudomegas.saat` — permanent once distributed, so it is confirmed with
the owner in AM1's plan before a single install happens. `versionName` follows
the milestone table; `versionCode` is a monotonic integer bumped on every tagged
release.

Two workflows, both path-filtered to `/android` so the desktop pipeline is never
touched:

- **android-ci.yml** — on push: unit tests, manifest permission assertion,
  `assembleDebug`, debug APK as an Actions artifact for sideloading.
- **android-release.yml** — on `android-v*` tags: tests, signed release APK,
  attached to a GitHub Release.

Signing: the owner generates the keystore once, locally, and it is never
committed. It reaches CI as GitHub secrets (base64 keystore, store and key
passwords). **Losing the keystore means losing the ability to update the app for
every existing user** — the docs say this in exactly those words, with where the
owner should keep copies.

Versioning is independent of the desktop app: `android-vX.Y` tags, its own
`CHANGELOG-ANDROID.md`, its own release notes. Desktop tags and workflows are
frozen history.

---

## 9. Distribution

In order, deliberately:

1. **GitHub Releases** — the signed APK, from AM11. The primary channel, same as
   the desktop's tarball, .deb and installer.
2. **IzzyOnDroid** — takes the release APK directly from GitHub Releases; fast to
   enter, updates follow tags within a day.
3. **F-Droid** — builds from source; GPL-3.0 and a zero-proprietary dependency
   tree already satisfy inclusion. Fastlane metadata structure prepared in AM12;
   their review takes as long as it takes.

**Google Play is deliberately out of scope.** Recorded decision: the fee, the
12-tester/14-day gate for new personal accounts, and the audience mismatch make it
not worth it for v1. Revisit only on the owner's word.
