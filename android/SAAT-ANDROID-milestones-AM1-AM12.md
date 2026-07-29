# SAAT Android — Milestones AM1 to AM12

The complete roadmap for the Android app, written before the first line of code.
`SPEC-ANDROID.md` is authoritative; read it before every milestone. Run these one
at a time; do not start one before the previous is committed, since two sessions
on the same repository produce conflicts that cost more than they save.

Everything lives in the existing repository under `/android`. The desktop app is
done and tagged — **no milestone here may modify anything outside `/android`,
`docs/schema.md`, the repository README's install section, and the two new
workflow files.** Both workflows are path-filtered so desktop CI never runs for
Android changes and vice versa.

No releases are tagged until AM11. Milestones AM1–AM10 end with a version bump, a
`CHANGELOG-ANDROID.md` entry, commits and a push; the debug APK from CI is the
sideload artifact for the owner's phone throughout.

| # | versionName | What | Status |
|---|---|---|---|
| AM1 | 0.1 | Scaffold, theme, 4-tab shell, zero-permission manifest, CI | pending |
| AM2 | 0.2 | Storage layer: model, TOML I/O, slugs, backups, tests | pending |
| AM3 | 0.3 | Grid, empty state, sort, search | pending |
| AM4 | 0.4 | Detail view, wear stats, "Wore this today" | pending |
| AM5 | 0.5 | Add/edit form, images, delete | pending |
| AM6 | 0.6 | Specs list, filter sheet, collection summary | pending |
| AM7 | 0.7 | Calendar, wear tracking, year view | pending |
| AM8 | 0.8 | Widget, app shortcuts | pending |
| AM9 | 0.9 | Compare, timing, maintenance, strap compatibility | pending |
| AM10 | 0.10 | ZIP export/import, round-trip test, backup rules | pending |
| AM11 | 1.0 | Turkish, signing, release workflow, README — public release | pending |
| AM12 | — | IzzyOnDroid + F-Droid metadata | pending |

**The two gates:** v1.0 is tagged only after AM11, and AM11 is not started before
AM10 is green — an app that cannot export its data does not get released,
period. The widget (AM8) is scheduled before compare (AM9) because daily wear
logging is the phone's reason to exist and it should start earning its keep as
early as possible.

---

## Milestone AM1 — Scaffold (0.1)

Nothing visible gets built here beyond an empty shell, and that is the point: the
zero-permission rule, the path filters that protect the desktop pipeline, and the
applicationId that can never change are all decisions that hurt to revisit. They
get made first, alone, while the diff is small enough to read.

```
Milestone AM1 - Scaffold (target: versionName 0.1).

Read SPEC-ANDROID.md first, in full. No AI or tooling attribution anywhere -
no commit trailers.

This is the first Android milestone in a repository whose desktop app is
done and tagged. The prime directive: nothing outside /android, the shared
docs, and the new workflow file may change. Desktop CI must not trigger on
Android pushes - verify the path filters actually achieve this.

Commit as THREE commits.

=== COMMIT A: PROJECT AND SHELL ===

1. Gradle project under /android: Kotlin DSL, version catalog, Compose BOM,
   Material 3. minSdk 26, targetSdk latest stable. applicationId
   io.github.sudo-megas.saat is proposed - CONFIRM THE EXACT ID WITH ME IN
   THE PLAN before generating anything; it is permanent once distributed,
   and note that hyphens are not legal in an applicationId so propose the
   sanitised form.
2. The four-destination bottom navigation shell: Grid, Specs, Calendar,
   Settings - each a placeholder screen with its name and nothing else.
   Predictive back enabled. State survives rotation.
3. Material 3 theming: dynamic colour on Android 12+, a static fallback
   palette below it modelled on the desktop's Default Light and Default
   Dark, and a System/Light/Dark preference wired into Settings (the only
   real control this milestone ships). Both modes checked for contrast.
4. Launcher icon: derive an adaptive icon from the existing desktop saat
   icon rather than composing a new identity. Monochrome layer included
   for themed icons on 13+.

=== COMMIT B: THE ZERO-PERMISSION RULE ===

5. The manifest declares NO uses-permission entries. None.
6. A test that parses the MERGED manifest (after manifest merger, so a
   library cannot smuggle one in) and fails if any uses-permission is
   present. This test is the guardian of SPEC-ANDROID rule 2 and runs in
   CI forever. If a future dependency injects a permission, the build
   breaks - which is exactly the desired behaviour.
7. Strings: every user-visible string in resources from this first commit.
   No hardcoded literals in composables - Turkish lands in AM11 and a
   string sweep at that point would be the expensive way to do it.

=== COMMIT C: CI ===

8. .github/workflows/android-ci.yml: on push and PR touching /android or
   the workflow itself - run unit tests (including the manifest test) and
   assembleDebug, upload the debug APK as an artifact. That artifact is
   how I sideload every milestone onto my phone.
9. Confirm, by reading the desktop workflows' trigger filters and by the
   Actions run list after pushing, that Android pushes do not trigger
   desktop jobs and desktop pushes will not trigger this one. Report what
   you found, not what should be true.
10. android/CHANGELOG-ANDROID.md created with the 0.1 entry.
11. docs/schema.md: verify it exists at the repository root and fully
    describes the watch.toml schema. If the desktop kept it under its own
    docs/, promote a copy to the root as the shared contract and note the
    provenance at the top. Do not edit its content.

=== DO NOT ===

- Touch anything under the desktop app's directories
- Add Firebase, analytics, crash reporting, or any telemetry SDK
- Add any dependency outside SPEC-ANDROID 2.1 without written
  justification in the commit message
- Build any real screen content - the shell is the deliverable
- Tag a release

=== VERIFICATION ===

12. CI green: tests pass, debug APK artifact produced.
13. The merged-manifest permission test demonstrably fails when a
    uses-permission is temporarily added, then passes clean. Show both.
14. The APK installs and runs on a real phone: four tabs, theme control
    works, dynamic colour follows the wallpaper on 12+.

=== WRAP UP ===

15. versionName 0.1, versionCode 1. Commit the three parts, no trailers:
      AM1a: Gradle scaffold, Compose shell, theme
      AM1b: zero-permission manifest and its guardian test
      AM1c: Android CI workflow and changelog
    git push, then report the three commit SHAs and the Actions run URL.

Enter plan mode and show me the plan before writing code.
```

---

## Milestone AM2 — Storage layer (0.2)

The most important milestone of the twelve. Everything above it is furniture;
this is the floor. It implements the shared schema exactly — the acceptance
question is never "does it work" but "does it read and write what the desktop
reads and writes".

```
Milestone AM2 - Storage layer (target: versionName 0.2).

Read SPEC-ANDROID.md sections 3 and 4, and docs/schema.md, before anything
else. No AI or tooling attribution anywhere - no commit trailers.

This milestone has no UI. Its deliverable is a storage package with tests,
and its acceptance criterion is parity: a watch.toml the desktop app wrote
loads here with every field intact, and a file written here loads there.

Commit as THREE commits.

=== COMMIT A: MODEL ===

1. Kotlin data classes for the full schema: identity, movement, case, dial,
   straps (list), acquisition, maintenance, log (list), worn (list of
   dates), timing (list), notes. Field-for-field against docs/schema.md -
   produce a parity checklist in the PR description mapping every schema
   field to its Kotlin property, so an omission is visible rather than
   discovered in AM4.
2. Absent semantics: every optional field nullable, never defaulted to 0 or
   "". The UI layer renders absence as an em-dash; the model must be able
   to represent absence in the first place.
3. Derived values as pure functions, not stored: last worn, days since,
   times worn this year, longest streak, next service due, bph to Hz.
   Unit-test each, including the empty-list cases.

=== COMMIT B: TOML AND FILES ===

4. Choose the TOML library - ktoml or tomlkt - by actually round-tripping a
   desktop-shaped fixture through both if necessary. Record the choice and
   reasons in the commit message. The chosen one must read TOML 1.0 tables,
   arrays of tables, dates, and mixed-presence fields.
5. Load: scan files/watches/, skip any entry whose name starts with _ or .,
   parse each watch.toml, tolerate malformed files by collecting
   (filename, error) pairs for the UI to surface later - never throw past
   the loader, never skip silently.
6. Save: serialise the model back to TOML. BYTE PRESERVATION RULE: a watch
   loaded from disk and never edited is never rewritten. Only an actual
   edit writes, and writes are atomic - temp file in the same directory,
   then rename.
7. Slugs: brand + model, lowercased, ASCII-safe with the Turkish dotless-i
   handled, non-alphanumerics to hyphens, Windows-reserved names and
   illegal characters sanitised, collisions detected CASE-INSENSITIVELY
   and resolved with -2, -3. Port the desktop's rules; do not reinvent
   them. Test every clause of this sentence.
8. Backups: before an edit rewrites a watch.toml, copy the previous version
   into files/backups/ with a timestamp, pruned to the newest 20. Deleting
   a watch moves its whole folder into files/backups/deleted/ rather than
   erasing it.

=== COMMIT C: REPOSITORY ===

9. An in-memory repository: loads everything at app start on a background
   dispatcher, exposes the collection as observable state, applies edits
   write-through (memory first, disk immediately after, error surfaced if
   the disk write fails). No caching layers, no database - the collection
   fits in memory hundreds of times over.
10. Tests build fixture trees in temp directories at runtime and delete
    them. NO fixture data is committed to the repository - the no-seed-data
    rule applies to test assets in the repo exactly as it applies to
    shipped code. Fixtures are constructed by test code, in code.

=== DO NOT ===

- Add Room, SQLite, or any persistence dependency
- Write anywhere outside filesDir and cacheDir
- Commit any watch data, real or invented
- Build any UI

=== VERIFICATION ===

11. All tests green in CI, including: parity load of a desktop-shaped
    fixture, malformed-file tolerance, slug rules, atomic write, backup
    pruning, byte preservation of an untouched file.
12. Report the parity checklist: every docs/schema.md field mapped, none
    missing, none renamed.

=== WRAP UP ===

13. versionName 0.2, versionCode unchanged (no release). Commits:
      AM2a: data model and derived values
      AM2b: TOML I/O, slugs, atomic writes, backups
      AM2c: in-memory repository and fixtures
    git push, report SHAs and the CI run.

Enter plan mode and show me the plan before writing code.
```

---

## Milestone AM3 — Grid (0.3)

The first screen worth looking at, and the first APK worth carrying on a phone.
The empty state gets real attention because for a while it is the whole app.

```
Milestone AM3 - Grid and empty state (target: versionName 0.3).

Read SPEC-ANDROID.md 5.2 and 5.8 first. No AI or tooling attribution
anywhere - no commit trailers.

Commit as TWO commits.

=== COMMIT A: GRID AND EMPTY STATE ===

1. The Grid tab becomes real: two columns portrait, three landscape, cards
   at a fixed 4:5 image crop, brand as overline, model as title, style and
   movement kind as small metadata beneath. All cards in a row the same
   height. Coil loads images from the watch's images/ directory with
   thumbnails cached in cacheDir - never inside watches/.
2. A watch without a photo gets the neutral placeholder tile with its
   diameter and lug width set in the middle - informative, not an empty
   grey box. Absent measurements degrade gracefully within the tile.
3. The collection empty state, per SPEC-ANDROID 5.8: centred, quiet, one
   line, one sentence about the data being plain TOML the owner can export
   at any time, one primary button (Add watch - a stub action until AM5,
   showing a plain "coming in a later milestone" notice rather than a dead
   button). No illustration, no mascot, no exclamation marks.
4. Malformed-file notices from AM2 surface here: a dismissible line above
   the grid naming the skipped files and their errors. Never a crash,
   never silence.
5. The FAB: Add watch, same stub. It is the app's one primary-weight
   control.

=== COMMIT B: SORT AND SEARCH ===

6. Sort menu in the top bar: Brand, Model, Acquired (newest first), Least
   worn. Persisted to config.toml.
7. Search field in the top bar: fuzzy across brand, model, reference,
   caliber and tags, filtering the grid live. Build the matcher in the
   repository layer, not the composable - AM6's Specs list reuses it.
8. Tapping a card navigates to a Detail placeholder (real in AM4).

=== DO NOT ===

- Add filter facets (AM6), selection mode (AM9), or wear actions (AM4)
- Cap the grid at two columns on a tablet-width landscape screen
- Ship any placeholder art or demo imagery

=== VERIFICATION ===

9. The app cannot add watches yet, so build the sanctioned test fixture
   from SPEC-ANDROID rule 1: a developer action in Settings, DEBUG BUILDS
   ONLY, clearly labelled, that generates exactly two demo watches in
   code at tap time - one mechanical with most fields filled (straps,
   log, worn days, timing readings), one quartz with almost nothing
   beyond brand and model, neither with photos so the placeholder tile
   is exercised. Plus a matching "clear demo watches" action. Nothing is
   committed as data files, nothing is bundled as an asset, and a test
   asserts the mechanism is absent from the release build.
10. Empty state screenshot-reviewed in light and dark.

=== WRAP UP ===

11. versionName 0.3. Commits:
      AM3a: grid, cards, empty state, error surfacing
      AM3b: sort and fuzzy search
    git push, report SHAs and CI run.

Enter plan mode and show me the plan before writing code.
```

---

## Milestone AM4 — Detail view (0.4)

Where the owner spends time. Also where "Wore this today" enters the codebase —
the wear-logging path built here is the same one the calendar, the widget and the
shortcut will call later, so it is built once, in the repository, properly.

```
Milestone AM4 - Detail view (target: versionName 0.4).

Read SPEC-ANDROID.md 5.6 first. No AI or tooling attribution anywhere - no
commit trailers.

Commit as TWO commits.

=== COMMIT A: THE PAGE ===

1. Detail as a full screen above the tabs, back affordance, opened from a
   grid card. Large primary image, thumbnail strip beneath, tap a thumb to
   view it large. Setting the primary is an AM5 (edit form) concern - here
   the strip is read-only.
2. Spec groups in the model's order: Movement, Case, Dial, Straps,
   Acquisition, Maintenance, Log, Timing, Notes. Single column. An absent
   field renders as a muted em-dash inside a shown group; a WHOLLY empty
   group is hidden, not rendered as dashes. A watch with only brand and
   model shows a short page, and that is correct.
3. Straps render as small cards with their own photo when present, the
   fitted one marked. The log renders newest first. Timing renders as a
   plain list for now - the sparkline is AM9. Maintenance shows its raw
   fields only - the due-date logic surfaces in AM9.
4. Field display rules from SPEC-ANDROID 4: dates DD.MM.YYYY, water
   resistance in metres with bar in parentheses, bph with derived Hz
   alongside.

=== COMMIT B: WEAR ===

5. The wear stats line: last worn, days since, times worn this year,
   longest streak - from the AM2 derived functions. Plus the compact
   twelve-month strip of this watch's worn days. Both hidden entirely when
   the watch has never been worn.
6. "Wore this today": one button, one tap, no dialog. Appends today's
   LOCAL date to this watch's worn list via a repository operation.
   Idempotent - a second tap the same day is a visible no-op ("already
   recorded"). ENFORCE THE ONE-WATCH-PER-DAY RULE HERE, in the repository:
   if today already belongs to another watch, it moves silently, exactly
   as the desktop calendar behaves. This repository operation is the
   single wear-logging path that AM7's calendar, AM8's widget and AM8's
   shortcut will all reuse - design its signature for that.

=== DO NOT ===

- Build edit, delete, or image management (AM5)
- Build the sparkline, maintenance-due logic, or strap compatibility (AM9)
- Add a share action, or any action not in the spec

=== VERIFICATION ===

7. Tests: wear idempotency within a local date, the silent-move rule,
   stats correctness across year boundaries.
8. Sideload: a hand-checked pass over a watch with most fields filled and
   a watch with almost none - both pages must look intentional.

=== WRAP UP ===

9. versionName 0.4. Commits:
     AM4a: detail page and spec groups
     AM4b: wear stats and the wear-logging path
   git push, report SHAs and CI run.

Enter plan mode and show me the plan before writing code.
```

---

## Milestone AM5 — Add / edit form (0.5)

The app stops being read-only. From this APK onward the phone is a full SAAT and
the debug fixture mechanism from AM3 loses its purpose — real data enters by
hand, which is the point of the hobby.

```
Milestone AM5 - Add and edit (target: versionName 0.5).

Read SPEC-ANDROID.md 5.7 first. No AI or tooling attribution anywhere - no
commit trailers.

Commit as THREE commits.

=== COMMIT A: THE FORM ===

1. One full-screen scrolling form with collapsible group headers in spec
   order - NOT tabs, NOT a wizard. The same screen serves add and edit.
2. Numeric fields: numeric keyboards, units as suffixes inside the field.
   Dates via the Material date picker, displayed DD.MM.YYYY. Water
   resistance accepts m, bar or atm and stores metres.
3. enum* fields per SPEC-ANDROID 4: an editable dropdown offering the
   schema's suggested values plus every value already used in the
   collection, and accepting free text. The owner will buy something the
   schema did not anticipate.
4. The Movement group swaps power_reserve_hours for battery_life_years and
   changes the accuracy unit when kind is Quartz or Solar.
5. Straps as an editable list; the fitted flag enforced to at most one.
6. SAVING WITH ONLY BRAND AND MODEL FILLED MUST SUCCEED. Validation blocks
   nothing else - it may advise, it may never obstruct. Backing out with
   unsaved changes prompts: discard or keep editing.

=== COMMIT B: IMAGES ===

7. The Images group: the system Photo Picker (no permission) and the
   ACTION_IMAGE_CAPTURE camera intent (no permission - the capture target
   is a FileProvider URI into this watch's images/ staging). Picked and
   captured files are COPIED into the watch's images/ directory - the
   collection must never depend on external URIs that can die.
8. EXIF orientation honoured on copy so no photo lies on its side.
   Reordering and set-as-primary supported. Thumbnails are Coil's problem
   in cacheDir - nothing derived is written into watches/.
9. Deleting an image from a watch moves the file into backups/deleted/
   alongside the watch-folder convention rather than erasing it.

=== COMMIT C: DELETE AND CLEANUP ===

10. Delete watch, from the detail page: requires typing the model name.
    The folder moves to backups/deleted/ per AM2. Its wear history goes
    with it - a watch folder is a complete record, desktop rule.
11. The AM3 two-watch debug fixture STAYS for the whole development
    cycle - later milestones (calendar ranges, compare, ZIP round-trip
    spot checks) keep using it. Re-verify its release-absence test still
    passes now that the form exists, and confirm the demo watches behave
    like any other watch under edit and delete.
12. First-run flow check: empty state -> Add -> form -> save -> grid shows
    one card. This is the app's founding user journey; walk it and fix
    what grates.

=== DO NOT ===

- Require any field beyond brand and model
- Fetch anything from the network, including brand logos or model data -
  there is no network
- Keep references to external image URIs instead of copies

=== VERIFICATION ===

13. Tests: save with minimal fields, enum free-text round-trip, fitted
    uniqueness, image copy + EXIF orientation, typed-name delete guard,
    unsaved-changes prompt logic.
14. Sideload: enter one real watch end to end, photograph it with the
    camera path, rotate the phone mid-edit and lose nothing.

=== WRAP UP ===

15. versionName 0.5. Commits:
      AM5a: the form
      AM5b: image import and management
      AM5c: delete and first-run polish
    git push, report SHAs and CI run.

Enter plan mode and show me the plan before writing code.
```

---

## Milestone AM6 — Specs list and filters (0.6)

The desktop table, rethought for a hand. The filter sidebar, folded into a
sheet. Nothing new conceptually — the work is making density survive a small
screen without becoming noise.

```
Milestone AM6 - Specs list and filters (target: versionName 0.6).

Read SPEC-ANDROID.md 5.3, 5.11 and 5.12 first. No AI or tooling attribution
anywhere - no commit trailers.

Commit as TWO commits.

=== COMMIT A: SPECS LIST ===

1. The Specs tab becomes real: a chip row of presets - Identity, Movement,
   Case, Dial, Straps, Acquisition - and one row per watch beneath:
   thumbnail, brand + model two-tier, then that preset's key fields in
   tabular figures so measurements align. Decide each preset's field set
   from the schema groups and record the choice in the commit message.
2. Absent fields inside a row render as the muted em-dash - a row never
   collapses or hides because a value is missing.
3. Sort and search from AM3 apply here identically - same repository
   matcher, same sort orders, one implementation.
4. Tap a row -> detail. The active preset persists to config.toml.

=== COMMIT B: FILTERS ===

5. A filter bottom sheet, reachable from the top bar on Grid and Specs,
   applying to both: Status, Style, Group, Movement kind, Case material,
   Lug width, Tags, and Not worn in 90 days. Each facet multi-select with
   live counts; a facet with no values across the collection is hidden.
   With an empty collection the sheet shows only the summary footer.
6. The collection summary as the sheet's footer: watch count, split by
   movement kind, total acquisition value by currency. Plain figures - no
   charts, no gauges, no progress rings.
7. Active filters visible as dismissible chips under the top bar, so state
   is never hidden behind the closed sheet.

=== DO NOT ===

- Implement filters twice - one filtered collection state feeds Grid,
  Specs, and (later) the calendar picker
- Add facets beyond the spec's list
- Hide a row for missing data

=== VERIFICATION ===

8. Tests: facet counts, combined facet + search filtering, the 90-day
   facet against fixed clock fixtures.
9. Sideload: switch presets across a real collection; figures align,
   nothing truncates into ellipsis soup on a 6-inch screen.

=== WRAP UP ===

10. versionName 0.6. Commits:
      AM6a: specs list with presets
      AM6b: filter sheet and collection summary
    git push, report SHAs and CI run.

Enter plan mode and show me the plan before writing code.
```

---

## Milestone AM7 — Calendar (0.7)

The most satisfying screen in the app, and the one whose desktop interaction
grammar — click-drag ranges, arrow keys — translates least. The touch grammar
from SPEC-ANDROID 5.5 replaces it entirely. The wear-logging path from AM4 is
reused, not reimplemented.

```
Milestone AM7 - Calendar and wear tracking (target: versionName 0.7).

Read SPEC-ANDROID.md 5.5 first. No AI or tooling attribution anywhere - no
commit trailers.

Commit as THREE commits.

=== COMMIT A: MONTH GRID ===

1. The Calendar tab becomes real: a month grid, seven columns, weeks
   starting Monday, swipe or header arrows to change month. A day with a
   watch shows its primary photo square-cropped filling the cell, day
   number in a corner over a subtle scrim; an empty day shows only its
   muted number; today carries an accent hairline border. Keep everything
   around the grid quiet - the photos are the interface.
2. The date -> watch index built in memory from every watch's worn list at
   load, per the desktop rule. Wear history stays stored per watch; there
   is no central log, and deleting a watch takes its days with it.
3. The calendar empty state: an empty month plus one muted line explaining
   that tapping a day records what was worn.

=== COMMIT B: THE PICKER AND THE RULES ===

4. Tap an empty day -> a picker bottom sheet: search field plus the
   collection as thumbnails. Pick one, the day fills. Tap a filled day ->
   the same picker with the current watch marked; picking another
   replaces, Clear empties.
5. Long-press a day -> range mode: extend the selection across days, pick
   one watch, the span fills. This replaces the desktop's click-drag and
   is how a year of backlog gets entered without losing patience.
6. One watch per day across the whole collection, enforced in the same
   repository operation AM4 built - assigning a day that belongs to
   another watch moves it silently, no prompt. Past and future days are
   equally editable; future days are how you plan. No concept of a rest
   day.

=== COMMIT C: STATS AND YEAR VIEW ===

7. Footer strip beneath the grid, three plain figures for the displayed
   month: days recorded, distinct watches worn, and the watches NOT worn
   this month - that last one is the only figure here that tells the
   owner something he did not already know.
8. Year view, toggled in the header: twelve compact month grids, cells as
   colour chips, one hue per watch derived deterministically from its
   slug. Same derivation function as any future use - write it once in
   the model layer and test its stability.

=== DO NOT ===

- Centralise wear storage for efficiency
- Add streaks, badges, goals, or any gamification
- Prompt on the silent-move rule

=== VERIFICATION ===

9. Tests: index construction, silent move across watches, range
   assignment, month stats, hue determinism.
10. Sideload: enter a month of backlog with range mode; it must feel fast
    enough that finishing a year seems plausible.

=== WRAP UP ===

11. versionName 0.7. Commits:
      AM7a: month grid and index
      AM7b: picker, range mode, the one-per-day rule
      AM7c: month stats and year view
    git push, report SHAs and CI run.

Enter plan mode and show me the plan before writing code.
```

---

## Milestone AM8 — Widget and shortcuts (0.8)

The phone's reason to exist, promoted ahead of compare on purpose: from this
build onward, logging today's watch never requires opening the app. Glance is
the one dependency added for it, and it is on the approved list.

```
Milestone AM8 - Widget and app shortcuts (target: versionName 0.8).

Read SPEC-ANDROID.md 5.9 first. No AI or tooling attribution anywhere - no
commit trailers.

Commit as TWO commits.

=== COMMIT A: THE WIDGET ===

1. A Glance home-screen widget showing TODAY: the assigned watch's primary
   photo and name, or "Nothing recorded today" in the quiet empty-state
   voice. One size done well beats four done badly - a small/medium
   resizable cell is enough.
2. Tap behaviour: empty widget -> the today-picker (the AM7 sheet hosted in
   a lightweight activity, not the full app shell); filled widget -> that
   watch's detail page.
3. Updates: at local midnight (the widget must roll over to "Nothing
   recorded today" without being tapped) and immediately whenever today's
   assignment changes from anywhere in the app. Use WorkManager or
   AlarmManager only if Glance's own update path cannot do midnight
   reliably - and if either is needed, justify it in the commit message
   per the dependency rule. No network, obviously; also no battery-hungry
   periodic polling - midnight is one scheduled tick, not a heartbeat.
4. The widget respects dynamic colour and dark mode.

=== COMMIT B: SHORTCUTS ===

5. Static app shortcuts on the launcher icon: "Wore this today" (straight
   to the today-picker) and "Add watch" (straight to the form). Both
   labelled in resources, both functional cold-start.
6. All three wear entry points - detail button, widget, shortcut - call
   the single AM4 repository operation. Verify there is exactly one
   implementation of the one-watch-per-day rule in the codebase and state
   where it lives.

=== DO NOT ===

- Add a notification, daily reminder, or any attention-seeking behaviour;
  the widget sits quietly on the launcher and that is all
- Build a widget configuration screen
- Poll on a timer

=== VERIFICATION ===

7. Tests: midnight rollover logic against a fake clock, update-on-change.
8. Sideload: place the widget, log from it, watch it update; log from the
   shortcut with the app killed; confirm the calendar shows both.

=== WRAP UP ===

9. versionName 0.8. Commits:
     AM8a: the today widget
     AM8b: app shortcuts and single-path verification
   git push, report SHAs and CI run.

Enter plan mode and show me the plan before writing code.
```

---

## Milestone AM9 — Compare and the studying features (0.9)

Feature-completeness for v1. Compare is the app's most useful screen for
deciding what to wear or what to buy next; the rest are the small intelligences
— timing, maintenance, strap fit — that make the catalogue smarter than a
spreadsheet.

```
Milestone AM9 - Compare, timing, maintenance, strap fit (target:
versionName 0.9).

Read SPEC-ANDROID.md 5.4 and the relevant parts of 5.6 first. No AI or
tooling attribution anywhere - no commit trailers.

Commit as THREE commits.

=== COMMIT A: COMPARE ===

1. Long-press on a grid card enters selection mode; selecting exactly two
   enables Compare in a contextual top bar. Two watches, side by side,
   portrait - two columns, attributes as rows grouped in the model's
   order.
2. Rows where both watches share a value are dimmed; rows that differ sit
   at full contrast so the differences read at a glance; rows where
   neither has a value are hidden. Reuse the detail view's field
   formatting - this screen must not become a second implementation of
   value display.

=== COMMIT B: TIMING AND MAINTENANCE ===

3. The timing sparkline on the detail page, rendered once a watch has
   three or more readings, hidden below that. Deviation over time, drawn
   with Compose primitives - no charting library. Add the entry form for
   a reading (date, deviation, position) to the edit form's Timing group
   if AM5 left it minimal.
4. Maintenance-due logic: next service due = the most recent Service log
   entry plus service_interval_years. Due within 90 days or overdue: the
   accent dot on the grid card and a single line at the top of the detail
   page. Silent when nothing is due, silent entirely when the interval is
   blank - most watches will never fill it and the UI must not nag.
   battery_due behaves the same way for quartz.

=== COMMIT C: STRAP COMPATIBILITY ===

5. On a watch's detail page, list straps belonging to OTHER watches whose
   width_mm matches this watch's case.lug_width_mm. Hidden when there are
   no matches. Tapping a listed strap navigates to its owner.

=== DO NOT ===

- Allow three- or four-way compare - two is the portrait-screen decision,
  recorded in SPEC-ANDROID 5.4
- Add a charting dependency
- Nag about maintenance

=== VERIFICATION ===

6. Tests: dim/contrast/hidden row classification, due-date derivation
   including the blank-interval silence, strap matching.
7. Sideload: compare two real watches; the differing rows must read at a
   glance in both themes.

=== WRAP UP ===

8. versionName 0.9. Commits:
     AM9a: two-up compare
     AM9b: timing sparkline and maintenance due
     AM9c: strap compatibility
   git push, report SHAs and CI run.

Enter plan mode and show me the plan before writing code.
```

---

## Milestone AM10 — The ZIP bridge (0.10)

The release gate. The ZIP is not a backup feature — it is the contract that the
phone and the desktop hold the same collection, and the proof that the owner's
data is never trapped in either. v1.0 does not exist until this milestone's
round-trip test is green.

```
Milestone AM10 - ZIP export and import (target: versionName 0.10).

Read SPEC-ANDROID.md 3.1 and 3.2 first. No AI or tooling attribution
anywhere - no commit trailers.

Commit as THREE commits.

=== COMMIT A: EXPORT ===

1. Settings -> Export: zip the exact watches/ tree - watches/<slug>/
   watch.toml and images/ - from the watches/ root, written wherever the
   user picks via ACTION_CREATE_DOCUMENT, filename saat-export-YYYY-MM-DD
   .zip. No config, no backups, no caches, nothing derived: clean data
   only, so unzipping into the desktop app's folder IS the import on that
   side.
2. Stream the zip - a collection with hundreds of photos must not be
   buffered whole in memory. Progress indication for large collections; a
   completion notice naming the destination.

=== COMMIT B: IMPORT ===

3. Settings -> Import via ACTION_OPEN_DOCUMENT. Accept an archive rooted
   at watches/ or directly at slug level - desktop users will produce
   both; detect which. Validate before touching disk: reject archives
   containing path traversal entries (../), absolute paths, or symlinks.
4. A slug that already exists is SKIPPED - only new watches are added, by
   the owner's decision. Imported watch.toml files keep their ORIGINAL
   BYTES on disk (the byte-preservation rule); parse them for the index
   but do not re-serialise them on import.
5. Finish with a summary: n added, n skipped, both named. A malformed
   watch inside the archive is reported by name and skipped without
   aborting the rest of the import.

=== COMMIT C: THE PROOF AND THE BACKUP RULES ===

6. The round-trip acceptance test: construct a desktop-shaped fixture
   tree in a temp directory at runtime (full schema coverage: straps,
   log, worn, timing, unicode brand names, a hand-comment in one
   watch.toml), zip it, import it, export it, and assert the exported
   tree is semantically identical field-for-field AND that every
   untouched watch.toml and every image is byte-identical. This test is
   the release gate for v1.0 and it says so in a comment at the top.
7. Android Auto Backup rules (backup_rules.xml, and the 12+ data
   extraction rules): include watches TOML files and config.toml, exclude
   every images/ directory and everything in cacheDir. Records must
   always fit the quota; photos are the ZIP's job. Document the split in
   the in-app About and the README section to come.
8. Settings gains a plain data section stating where data lives, what the
   cloud backup covers and does not, and that export is always available.
   One paragraph, no marketing voice.

=== DO NOT ===

- Merge or overwrite existing slugs on import
- Include anything derived in the export
- Extract archive entries without path validation
- Start AM11 before the round-trip test is green in CI

=== VERIFICATION ===

9. All tests green, the round-trip test proudly among them.
10. The real thing, both directions: export from the phone, unzip into a
    scratch copy of the desktop app, load it there; zip the desktop's
    watches/ and import to the phone. Report what was actually performed
    and on which machines - if the desktop side could not be tested, say
    so directly.

=== WRAP UP ===

11. versionName 0.10. Commits:
      AM10a: streaming export
      AM10b: import with skip-existing and validation
      AM10c: round-trip acceptance test and backup rules
    git push, report SHAs and CI run.

Enter plan mode and show me the plan before writing code.
```

---

## Milestone AM11 — v1.0, the public release

Turkish lands here so v1.0 ships with desktop language parity. Then the release
machinery: the keystore that must never be lost, the tag-triggered workflow, and
a README section written for people who will sideload an APK and deserve to know
exactly what it does and does not do.

```
Milestone AM11 - Release engineering (target: android-v1.0).

Read SPEC-ANDROID.md 8 and the desktop repo's release conventions in
docs/DEVELOPMENT.md first. No AI or tooling attribution anywhere - no
commit trailers.

Commit as FOUR commits.

=== COMMIT A: TURKISH ===

1. values-tr resources translating every string - the AM1 rule that no
   literal ever entered a composable pays off here. Translations must fit
   the watch-collecting context (the desktop's Turkish translations are
   the reference vocabulary - reuse their terminology).
2. The Settings language control switches EN/TR via per-app locales,
   explicit only - the app never reads the system locale to choose, per
   SPEC-ANDROID rule 7. Storage stays canonical English: a Turkish combo
   box shows the Turkish label and writes the English enum value. Add a
   test: a file written under one UI language loads identically under the
   other.

=== COMMIT B: SIGNING ===

3. Release signing config reading keystore path and passwords from
   environment / Gradle properties - NOTHING secret in the repository,
   enforced by .gitignore entries and a check in the workflow.
4. docs/ANDROID-RELEASING.md: how the keystore was generated (the exact
   keytool invocation, key validity 25+ years), which GitHub secrets hold
   it (base64 keystore, store password, key password), and in bold: LOSING
   THIS KEYSTORE MEANS NEVER UPDATING THE APP FOR EXISTING USERS - keep
   copies in at least two offline places. Generating the keystore is MY
   action - give me the command and wait; do not generate or commit one.

=== COMMIT C: THE RELEASE WORKFLOW ===

5. android-release.yml: on android-v* tags - run the full test suite
   (round-trip test included), build the signed release APK, attach it to
   a GitHub Release created for the tag. Path-filter irrelevant here (tags
   are explicit) but confirm again that desktop workflows ignore
   android-v* tags.
6. versionCode management: a monotonic integer bumped in the release
   commit. Add a guard test that versionName matches the newest
   CHANGELOG-ANDROID.md heading, mirroring the desktop's version guard.
7. An in-CI smoke check: install the built APK on an emulator and confirm
   it launches to the empty state. If emulator time makes CI miserable,
   scale back to apkanalyzer sanity checks and say so honestly.

=== COMMIT D: README ===

8. The repository README gains an Android section in the install area:
   what SAAT for Android is in two sentences, the APK download from
   Releases, how to sideload (the two taps past "unknown apps", stated
   plainly the way the Windows SmartScreen note is), the zero-permission
   claim with the one-line explanation of why it is verifiable, where
   data lives, what the cloud backup covers, and the ZIP bridge to the
   desktop app. Screenshots come from MY collection - ask me to take
   them; do not ship placeholders and do not fabricate a collection.
9. docs/release-notes/android-1.0.md - user-facing only.

=== DO NOT ===

- Commit a keystore, a password, or any secret
- Tag before AM10's round-trip test is green on master
- Add an auto-updater
- Mention Google Play

=== VERIFICATION ===

10. A dry-run tag on a throwaway branch produces a signed, installable
    APK whose signature verifies with apksigner. Report the verification
    output.
11. Turkish pass over every screen on a real phone - report any string
    that overflows its layout.

=== RELEASE ===

12. The real thing:
    a. versionName 1.0, versionCode bumped, CHANGELOG-ANDROID entry,
       guard test green.
    b. Commit the four parts, no trailers:
         AM11a: Turkish localisation
         AM11b: release signing
         AM11c: tag-triggered release workflow
         AM11d: README and release notes
    c. git push
    d. git tag -a android-v1.0 -m "SAAT Android v1.0"
       git push origin android-v1.0
    e. Watch the Actions run. If the workflow does not produce the
       release, fix the workflow - do not build or upload by hand.
    f. Report: four commit SHAs, the tag, the release URL, workflow
       iterations and what failed on each.

Enter plan mode and show me the plan before writing code.
```

---

## Milestone AM12 — Distribution

Metadata, not code — unless F-Droid's requirements force small build changes,
which is the only thing that would produce a version bump here. The app reaches
the two channels whose audience actually matches a local, zero-permission,
GPL watch catalogue.

```
Milestone AM12 - IzzyOnDroid and F-Droid (no version target unless
changes are required).

Read SPEC-ANDROID.md 9 first. No AI or tooling attribution anywhere - no
commit trailers.

Commit as TWO commits (plus any fixes the submissions force).

=== COMMIT A: FASTLANE METADATA ===

1. fastlane/metadata/android/en-US/: title, short_description,
   full_description, and the screenshot directory structure. The
   description is written in the README's plain register - what it is,
   what it never does (no network, no permissions, no accounts), the ZIP
   bridge. No superlatives, no emoji, no feature-list bloat.
2. values-tr descriptions under tr-TR to match the app's two languages.
3. Screenshots: MINE to take, from my real collection - request the exact
   set you need (grid, detail, calendar, compare at minimum) with the
   required resolutions, and wait. Do not generate, borrow, or mock
   anything.

=== COMMIT B: SUBMISSIONS ===

4. IzzyOnDroid: verify the release APK meets their requirements
   (reproducible-friendly build settings, no blobs, APK size within
   their limit) and prepare the submission - the request itself is MY
   action; give me the exact steps and links.
5. F-Droid: draft the metadata YAML for an RFP (build recipe against the
   android-v1.0 tag, GPL-3.0 license field, no anti-features - verify
   none apply). Note honestly in the report: their queue takes as long
   as it takes, and their build servers compile from source, so any
   build reproducibility issue surfaces here. If their recipe needs
   gradle tweaks, those become AM12 fix commits and, if user-visible,
   an android-v1.0.1.
6. Add both install channels to the README's Android section once each
   is actually live - not before. The README never claims a channel
   that does not exist yet.

=== DO NOT ===

- Submit to Google Play, Samsung Galaxy Store, Amazon, or anywhere else
- Add badges to the README
- Claim availability before it is real

=== VERIFICATION ===

7. Report the actual status of each channel: submitted, in review, or
   live, with links. Honest reporting over optimistic reporting - the
   desktop project's standing rule.

Enter plan mode and show me the plan before writing code.
```

---

*End of roadmap. SPEC-ANDROID.md governs; where these prompts and the spec
disagree, the spec wins and the prompt gets corrected before running.*
