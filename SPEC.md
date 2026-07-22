# SAAT — Watch Collection Manager

**Project specification. This document is authoritative.**

---

## 1. Brief

A standalone, local, portable desktop application for cataloguing a personal wristwatch
collection. It organises watches into categories, displays them as a photo-forward grid,
a dense spec table and a wear calendar, shows a detail page per watch, compares watches
side by side, and lets the owner add, edit and delete entries through a form.

**Ship it empty.** The owner enters every watch himself — that is the point of the
hobby. Build the framework, not the contents.

Target: Arch Linux (CachyOS), Wayland, Niri compositor, 2560×1440. Single user, offline,
no accounts.

---

## 2. Hard rules

Non-negotiable. Do not improve past them.

1. **No seed data. No demo watches. No sample collection.** `watches/` ships empty except
   for `_template.toml`. On first launch the user sees an empty state, not a populated
   catalogue. Do not invent watches to demonstrate the UI — not in the repo, not in
   tests, not in screenshots. Tests build fixtures in a temp directory at runtime and
   delete them.
2. **Portable.** Every path resolves relative to the application directory. Never write
   to `~/.config`, `~/.local/share`, `~/.cache`, `/tmp`, or any absolute path outside the
   app folder. Copying the folder to a USB stick and running it elsewhere must work with
   all data intact.
3. **No database.** No SQLite, no ORM, no embedded server. Storage is plain files.
4. **No network.** No API calls, no image fetching, no update checks, no telemetry. The
   app never opens a socket. The single exception is handing a URL to the system browser
   on explicit user click, which is a hand-off, not a request.
5. **Three dependencies:** `PySide6`, `tomlkit`, `Pillow`. Anything else needs written
   justification in the commit message.
6. **Python 3.11+, PySide6 (Qt 6), native widgets.** No webview, no QtWebEngine, no HTML
   rendering layer.
7. **Never silently swallow an exception.** Surface it in the UI with the message intact.

---

## 3. Storage

One directory per watch. Metadata lives beside its own images.

```
saat/
├── main.py
├── run.sh
├── saat/                      package: models, storage, ui
├── watches/                   THE DATA — ships empty
│   └── _template.toml         commented blank template, skipped by the loader
├── config.toml                window geometry, last view, column choices
├── backups/                   timestamped copies, pruned to the newest 20
│   └── deleted/
└── docs/schema.md
```

A populated watch folder will eventually look like this — **do not create one:**

```
watches/<slug>/
├── watch.toml
└── images/
    ├── main.jpg
    └── strap-nato.jpg
```

Rules for the storage layer:

- `<slug>` derives from brand + model, lowercased, non-alphanumerics to hyphens. On
  collision append `-2`, `-3`.
- Any file or directory whose name starts with `_` or `.` is skipped by the loader. That
  is how `_template.toml` stays out of the collection.
- Format is **TOML**, read and written with `tomlkit` so hand-written comments and key
  order survive a round trip. Someone editing `watch.toml` in a text editor and leaving
  `# accuracy not published by the manufacturer` must still find that note after the app
  saves the file.
- Dates use TOML's native date type, not strings.
- Write atomically: `watch.toml.tmp`, `fsync`, `os.replace`. A crash mid-save must never
  leave a truncated file.
- Before any destructive operation, copy the affected `watch.toml` to
  `backups/<slug>-<ISO timestamp>.toml`. Prune to the newest 20.
- Deleting a watch moves its whole folder to `backups/deleted/`. Never `rm -rf`.
- A malformed `watch.toml` must not crash the app. Load what parses, show the broken
  entry in the UI with an error badge and the parser message, keep going.
- Images are files. Never base64, never embedded in TOML. The TOML stores filenames
  relative to that watch's `images/` folder.

### Git

The code is version-controlled; **the collection is not**. Watch data contains serial
numbers, purchase prices and seller details and must never be committed. Create this
`.gitignore` in milestone 1, before the storage layer exists:

```gitignore
watches/*
!watches/_template.toml
!watches/.gitkeep
config.toml
backups/
.venv/
build/
dist/
__pycache__/
```

`watches/.gitkeep` and `watches/_template.toml` are the only tracked files under
`watches/`, so a fresh clone gets the directory structure and nothing else. The
repository is private.

---

## 4. Data model

Every field is optional except `brand` and `model`. The collection will always be partly
incomplete — manufacturers do not publish everything, and the owner fills gaps over
months. An absent field renders as a muted em-dash, never as `None`, never as `0`, and
never hides its row.

Fields marked `enum*` are **suggestions, not constraints**: render as an editable combo
box offering the listed values plus every value already used elsewhere in the collection,
and accepting free text. The owner will buy something you did not anticipate.

### identity
| field | type | notes |
|---|---|---|
| `brand` | string | required |
| `model` | string | required — the model name, e.g. a line or family |
| `reference` | string | manufacturer reference code. Separate from `model` because catalogues mix them into one string and they sort, search and display differently |
| `nickname` | string | named edition |
| `serial` | string | case-back serial — what an insurance claim needs |
| `group` | enum* | Seiko Group, Casio, Swatch Group, Citizen Group, Micro Brand, Independent, Other |
| `style` | enum* | Field, Pilot, Diver, Dress, Sport, Chronograph, GMT, Racing, Skeleton, Digital, Other |
| `status` | enum | Owned, Incoming, Wishlist, Sold, Gifted — default Owned |
| `storage` | string | where it physically lives — box slot, winder, drawer |
| `rating` | int 0–5 | personal, not a review score |
| `tags` | list[string] | free-form, feeds the filter sidebar |

### movement
| field | type | notes |
|---|---|---|
| `caliber` | string | |
| `kind` | enum* | Automatic, Manual, Automatic + Handwinding, Quartz, Solar, Mecha-quartz, Kinetic |
| `power_reserve_hours` | number | mechanical |
| `battery_life_years` | number | quartz — show one or the other, driven by `kind` |
| `accuracy_min` / `accuracy_max` | number | signed, e.g. −20 / +40 |
| `accuracy_unit` | enum | sec/day, sec/month |
| `jewels` | int | |
| `bph` | int | show derived frequency in Hz alongside: bph ÷ 7200 |
| `hacking` | bool | |
| `handwinding` | bool | |
| `origin` | string | Japan, Switzerland, China, Germany… |

### case
| field | type | notes |
|---|---|---|
| `diameter_mm` | number | case diameter excluding crown |
| `lug_to_lug_mm` | number | |
| `thickness_mm` | number | |
| `lug_width_mm` | int | drives strap compatibility — see §5.9 |
| `material` | enum* | Stainless Steel, Titanium, Bronze, Ceramic, Resin, Silicone, Gold-plated |
| `crystal` | enum* | Sapphire, Mineral, Hardlex, Acrylic, Sapphire-coated |
| `crown` | enum* | Screw-down, Push-pull, Screw-down + guards — what a water resistance rating actually depends on |
| `bezel` | enum* | Fixed, Unidirectional, Bidirectional, Tachymeter, GMT, None |
| `caseback` | enum* | Solid, Exhibition, Engraved |
| `water_resistance_m` | int | **stored in metres, always.** The form accepts bar/atm and converts on entry: 1 bar ≈ 10 m, 1 atm ≈ 10 m. Display in metres with the bar equivalent in parentheses. |
| `weight_g` | number | |

### dial
| field | type | notes |
|---|---|---|
| `colour` | string | |
| `material` | string | sunburst brass, enamel, meteorite — distinct from `case.crystal` |
| `indices` | enum* | Applied, Printed, Arabic, Roman, Mixed, Inverted, None |
| `lume` | string | compound name, or None |
| `complications` | list[string]* | Date, Day-Date, GMT, Chronograph, Power Reserve, Moonphase, Open-Heart, Small Seconds, Alarm |

### straps — a list
| field | type | notes |
|---|---|---|
| `material` | enum* | Leather, Calf Leather, Nylon, NATO, Silicone, Rubber, FKM, Canvas, Steel Bracelet, Mesh |
| `colour` | string | |
| `width_mm` | int | defaults to `case.lug_width_mm` |
| `clasp` | enum* | Pin Buckle, Deployant, Butterfly, Ratcheting |
| `fitted` | bool | at most one strap per watch is `true` — the app enforces this |
| `image` | string | filename in that watch's `images/` |

### acquisition
| field | type | notes |
|---|---|---|
| `date` | date | ISO in storage, `DD.MM.YYYY` in the UI |
| `price` | number | |
| `currency` | string | default TRY |
| `seller` | string | |
| `url` | string | opens in the system browser via `QDesktopServices` |
| `condition` | enum | New, Pre-owned |
| `box_and_papers` | bool | |
| `warranty_until` | date | expires quietly and is impossible to remember |

### maintenance
| field | type | notes |
|---|---|---|
| `service_interval_years` | number | typical mechanical interval is 5–8; blank means don't track |
| `battery_due` | date | quartz only |

Derived, not stored: **next service due** = the most recent `log` entry of kind Service
plus `service_interval_years`. A watch overdue, or due within 90 days, gets a small gilt
dot on its grid card and a line at the top of its detail page. Silent when nothing is
due, and silent entirely when the interval is blank — most watches will never have this
filled in and the UI must not nag about it.

### log — a list, chronological
`date`, `kind` (Service, Battery, Regulation, Strap Swap, Note), `note`. Newest first in
the detail view.

### worn — a list of dates
Nothing but dates. One entry per day the watch was worn. See §5.5 for the calendar that
drives it.

Derived: **last worn**, **days since worn**, **times worn this year**, **longest streak**.
These feed a "Least worn" sort option and a `Not worn in 90 days` filter facet.

### timing — a list
`date`, `deviation_sec`, `position` (Dial Up, Dial Down, Crown Up, Crown Down, Crown
Left, Worn). How a mechanical watch owner tracks whether a watch is running well. Render
as a small sparkline in the detail view once there are three or more readings. Hide the
section entirely when the list is empty.

### notes
A single free-text field, plain text, multiline.

---

## 5. Interface

### 5.1 Layout
Main window, three regions:

- **Left sidebar, ~260 px, collapsible.** Filter facets: Status, Style, Group, Movement
  kind, Case material, Lug width, Tags, `Not worn in 90 days`. Each facet is multi-select
  with live counts. Facets with no values across the collection are hidden — with an
  empty collection the sidebar shows only the summary footer.
- **Top bar.** Search field, view toggle (Grid / Table / Calendar), sort dropdown, and
  "Add watch" as the one primary-weight control in the app.
- **Main area.** Whichever view is selected.

Window opens at 1600×1000, remembers geometry in `config.toml`, minimum 1100×700. On a
1440p display the grid shows four to five cards per row — do not cap content width at a
fashionable 1200 px, use the screen.

### 5.2 Grid view
Image-forward cards. Primary photo fills the card top at a consistent 4:5 portrait crop —
watches photograph tall. Brand as an overline, model as the title, style and movement
kind as small metadata beneath. All cards in a row are the same height. A watch with no
photo yet gets a neutral placeholder tile with its diameter and lug width set in the
middle — informative, not an empty grey box. Card hover reveals a "Wore this today"
action and a compare checkbox.

### 5.3 Table view
Dense, sortable by clicking any header, tabular figures so measurements align. Columns
configurable through a right-click header menu, persisted to `config.toml`. Defaults:
Brand, Model, Style, Movement, Diameter, Lug width, Water resistance, Acquired.

Ship **column presets** matching the data model groups — Identity, Movement, Case, Dial,
Straps, Acquisition — in a dropdown beside the view toggle. Each shows every watch
against one family of attributes. This is how a collection is actually studied.

### 5.4 Compare view
Select two to four watches — checkbox on the grid card, or multi-select in the table —
and open a side-by-side comparison. Watches as columns, attributes as rows, grouped in
the model's order. Rows where every selected watch shares a value are dimmed; rows where
they differ sit at full contrast, so the differences read at a glance. Rows where no
selected watch has a value are hidden.

This is the app's most useful screen for deciding what to wear or what to buy next.
Build it in milestone 8, but shape the table view's data access so it isn't a second
implementation.

### 5.5 Calendar view
A month grid, seven columns, weeks starting Monday.

A day with a watch shows that watch's primary photo, square-cropped, filling the cell,
day number in the corner over a subtle scrim. An empty day shows only its number in
`--text-muted`. Today carries a gilt hairline border. A month of photographed days is the
most satisfying screen in the app — keep everything around it quiet: hairline rules,
muted month label, no chrome.

Interaction:

- Click an empty day → a compact picker (search field plus the collection as thumbnails).
  Pick one, the day fills.
- Click a filled day → the picker opens with the current watch marked. Picking another
  replaces it; Clear empties it.
- Click-drag across days → assign one watch to a range. This is how a year of backlog
  gets entered without losing patience.
- Every day is editable, past or future. Future days are how you plan.
- Arrow keys move between days, `Enter` opens the picker, `Delete` clears, `PgUp`/`PgDn`
  change month.

Rules:

- **One watch per day, across the whole collection.** Assigning a day that already belongs
  to another watch moves it — the previous owner loses that date silently, no prompt.
- **Wear history is stored per watch**, in each `watch.toml`'s `worn` list, not in a
  central log. A watch folder must remain a complete record of that watch, so deleting a
  watch takes its history with it. Build the date→watch index in memory at load. Do not
  centralise this for efficiency; the collection fits in memory many times over.
- No concept of a rest day. An empty cell means nothing was recorded, and that is fine.

Footer strip beneath the grid, three plain figures for the displayed month: days
recorded, distinct watches worn, and the watches *not* worn this month. That last one is
the point — it is the only thing here that tells you something you did not already know.

**Year view**, toggled in the calendar header: twelve compact month grids, cells reduced
to colour chips instead of photos, one hue per watch derived deterministically from its
slug. Reveals rotation at a glance — which watch owned the summer, which one you stopped
reaching for in March.

### 5.6 Detail view
Opens in the main area with a back affordance — not a modal. This is where the owner
spends time.

- Large primary image, thumbnail strip beneath, click to promote.
- Wear stats line: last worn, days since, times worn this year, longest streak. Plus a
  compact twelve-month strip of this watch's days only, hidden when it has never been
  worn.
- A single "Wore this today" button. One click, no dialog. Pressing it twice in a day is
  a no-op.
- Spec groups in the model's order: Movement, Case, Dial, Straps, Acquisition,
  Maintenance, Log, Timing, Notes. Two columns on a wide window, one when narrow.
- Empty groups are hidden, not rendered as a list of dashes. A watch with only a brand
  and model shows a short page, and that is correct.
- Straps render as small cards with their own photo, the fitted one marked.
- Edit and Delete at the bottom. Delete requires typing the model name to confirm.

### 5.7 Add / edit form
A tabbed dialog mirroring the data model groups; the same dialog serves both operations.

- Tab order matches the spec group order. Never force a wizard.
- Numeric fields are numeric inputs with units as suffixes inside the field, not as
  separate labels.
- The Movement tab swaps `power_reserve_hours` for `battery_life_years` and changes the
  accuracy unit when `kind` is Quartz or Solar.
- The Images tab accepts drag-and-drop and a file picker, copies files into the watch's
  `images/`, generates thumbnails with Pillow, allows reordering and setting the primary.
- Saving with only brand and model filled must succeed. Validation blocks nothing else.
- Closing with unsaved changes prompts.

### 5.8 Empty states
The collection empty state is the first screen the owner ever sees and, for a while, the
most frequent. Give it real attention. Centred and quiet: a line stating the collection
is empty, a sentence explaining that watches live in the `watches/` folder as editable
TOML files, one primary button to add the first watch, and a secondary text link that
opens `watches/` in the file manager. No illustration, no mascot, no exclamation marks.

The calendar's empty state is simply an empty month — correct as-is, plus one muted line
explaining that clicking a day records what was worn.

### 5.9 Strap compatibility
On a watch's detail page, list straps belonging to *other* watches whose `width_mm`
matches this watch's `case.lug_width_mm`. The owner swaps straps between watches; the app
should know which ones physically fit. Hide the section when there are no matches.

### 5.10 Collection summary
Sidebar footer: watch count, split by movement kind, total acquisition value by currency.
Plain figures. No charts, no gauges, no progress rings.

### 5.11 Keyboard
`Ctrl+N` add, `Ctrl+F` search, `Ctrl+E` edit current, `Ctrl+W` wore-today on the current
watch, `Escape` back or close, `Ctrl+Q` quit. Arrow keys navigate the grid and calendar,
`Enter` opens. Visible focus rings throughout.

---

## 6. Visual direction

The reference is a **movement plate**, not a generic dark-mode app. Watch movements are
grey nickel and warm brass, punctuated by red ruby jewels and the deep indigo of blued
steel. That is the palette in both modes. Do not reach for near-black with a bright acid
accent, and do not reach for stark white with a saturated accent — both are the default
look of every app in their category and say nothing about watches.

**Dark (default).** The plate as seen with the case back off, under a loupe.

```
--plate       #1C1B19   base background: warm-shifted charcoal, not blue-black
--plate-high  #262421   elevated surfaces: cards, sidebar, dialogs
--rule        #38352F   hairlines, borders, dividers
--text        #E8E4DC   primary text, warm off-white
--text-muted  #938C81   labels, units, absent values
--gilt        #C9A227   accent: primary buttons, active filters, focus rings, today
--ruby        #CF3931   destructive only: delete, unsaved-changes warning
```

**Light.** The same plate, brushed nickel in daylight — not an inverted dark mode.
Same hue relationships, lightness re-tuned for a light background.

```
--plate       #F1EEE6   warm platinum, not stark white
--plate-high  #FFFFFF   elevated surfaces — lifts off the platinum base
--rule        #DAD4C5   hairlines, borders, dividers
--text        #2B2822   primary text, warm near-black, not pure black
--text-muted  #70695E   labels, units, absent values
--gilt        #8A6A16   accent — same hue as dark mode, deepened for AA contrast on light
--ruby        #A82F24   destructive — same hue as dark mode, deepened for AA contrast on light
```

Verify actual contrast once rendered (4.5:1 for body text, 3:1 for large text and UI
components against its own background) and nudge lightness if Qt's rendering falls short
of these values — they are a starting point, not measured output.

In both modes, gilt appears only on things that are interactive or currently active.
Ruby appears in exactly two places in the whole app.

**Toggle.** A single icon-button in the top bar — sun/moon glyph, drawn to match the
line weight used elsewhere, not a font icon. This is a toggle, not a settings page: no
font-size options, no per-section colors, no theme file to import. Toggling re-applies
`theme.qss` and repaints immediately; it must not require a restart. The active mode
persists in `config.toml` alongside window geometry. Default on first launch: dark.

**Type.** IBM Plex — Arch package `otf-ibm-plex`, with a detected fallback so the app
does not break without it. Plex Sans Condensed for labels and column headers, Plex Sans
for body and titles, **Plex Mono for every number**: diameters, bph, accuracy, prices,
dates. Measurements in monospace with tabular figures is not decoration, it makes a spec
table readable at a glance. Scale: 11 / 13 / 15 / 20 / 28. Weights 400 and 600 only.

**Signature element.** One, in one place: spec group headers in the detail view sit on a
**minute track** — a hairline rule bearing fine ticks, longer every fifth, the way a
dial's chapter ring is printed. Draw it with `QPainter` in `--rule`, running to the edge
of the column, so it adapts automatically to whichever mode is active. That is the app's
only flourish. Everything else stays plain: no gradients, no glows, no escalating corner
radii, no drop shadows beyond a 1 px hairline border.

**Spacing.** 8 px base unit. Card padding 16, group spacing 32, page margin 24. Table
rows get 12 px vertical padding — a spec table crammed to 6 px is unreadable, and this
one is meant to be studied.

Implement both palettes in `saat/ui/theme.qss` (templated, not duplicated) with values
as named constants in a `theme.py` that also exposes them to `QPainter` code, plus a
function that swaps the active palette and reapplies. No inline stylesheets scattered
through widget constructors — this is what makes the toggle a small feature instead of a
find-and-replace across every view.

---

## 7. Build order

`git init` before writing a line of code. Commit at each milestone. Do not start
milestone *n+1* before *n* runs.

1. **Skeleton.** Package layout, `main.py`, a window that opens on Wayland, `config.toml`
   read/write, theme loaded, collection empty state rendering, and the `app_dir()` /
   `resource_dir()` helpers from §8. No data layer yet.
2. **Storage layer.** Dataclasses for the model, TOML load and save, slug generation,
   atomic writes, backups, the `_`-prefix skip rule, malformed-file tolerance. Unit tests
   against a temp directory.
3. **Grid and table views.** Read-only. View toggle, sorting, column presets.
4. **Detail view.** Spec groups, minute-track headers, image display, gallery strip.
5. **Add and edit.** The form dialog, image import and thumbnailing, delete with
   confirmation.
6. **Filter, search, sort.** Sidebar facets with live counts, fuzzy search across brand,
   model, reference, caliber and tags.
7. **Calendar and wear tracking.** Month grid, picker, drag-range assignment, the
   one-watch-per-day rule, wear stats, year view, per-watch strip, "Wore this today".
8. **Light and dark theme.** Second palette, the top-bar toggle, `config.toml`
   persistence, a contrast pass over both modes across every view built so far.
9. **Compare view and extras.** Comparison table, timing sparkline, maintenance-due
   indicator, strap compatibility, collection summary, keyboard shortcuts.
10. **Packaging.** Per §8.

---

## 8. Packaging and paths

Two ways to run, both supported, both documented in the README.

**Development:** `run.sh` — creates `.venv` if absent, installs the three dependencies,
sets `QT_QPA_PLATFORM=wayland`, runs `main.py`. Works from a fresh clone with no
arguments.

**Portable build:** PyInstaller in **one-folder mode** (`--onedir`), committed as a
`SAAT.spec` file rather than a pile of command-line flags:

```
SAAT/
├── SAAT              executable
├── _internal/        bundled Qt and Python runtime
├── watches/
├── config.toml
└── backups/
```

`watches/`, `config.toml` and `backups/` sit beside the executable, never inside
`_internal/`.

Do **not** use `--onefile`: it extracts to a temp directory on every launch, which is
slow with Qt bundled and puts application files outside the app directory.

Do **not** build an AppImage: they are mounted read-only, so the data directory cannot
live inside one, and they need FUSE 2, which Arch does not install by default.

### Path resolution — implement in milestone 1

Every path derives from one helper. A frozen executable resolves `__file__` differently
than a script, and PyInstaller's `sys._MEIPASS` points at bundled resources, never at
writable data. Getting this wrong breaks portability silently.

```python
import os, sys
from pathlib import Path

def app_dir() -> Path:
    """The directory the app and its data live in. Never a temp dir."""
    if os.environ.get("APPIMAGE"):            # AppImage: the .AppImage file's folder
        return Path(os.environ["APPIMAGE"]).resolve().parent
    if getattr(sys, "frozen", False):         # PyInstaller: the executable's folder
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent    # source checkout
```

`watches/`, `config.toml` and `backups/` all resolve from `app_dir()`. Bundled read-only
resources — the QSS theme, fonts, icons — resolve from `sys._MEIPASS` when frozen and
from the package directory otherwise, via a separate `resource_dir()`. The two must never
be confused.

Verify before calling the build done: copy the built folder to a different path, run it,
add a watch, confirm the file lands in the copied folder.

### Environment note

Arch's system Python is externally managed (PEP 668), so `pip install` into it is
refused. The venv route in `run.sh` is self-contained and matches the portability goal;
`sudo pacman -S pyside6 python-pillow` also works if preferred. The app must run natively
on Wayland — if Qt selects the X11 backend, set `QT_QPA_PLATFORM=wayland` in the launcher
and document it.

---

## 9. Do not

- Add a database, a settings GUI for the settings file, a plugin system, or a theme
  editor. The two fixed palettes in §6 and their single toggle are not a theme editor:
  no arbitrary colors, no user-saved palettes, no theme file import or export.
- Add cloud sync, sharing, export, or a showcase mode.
- Fetch watch data, images or prices from anywhere.
- Write files outside the application directory.
- Create example, demo, sample, placeholder or test watches anywhere in `watches/`.
- Centralise the wear log into one file. It lives per watch.
- Abstract ahead of need. There is one storage backend and one window; a
  `StorageProviderFactory` is wrong.
- Silently swallow exceptions.
