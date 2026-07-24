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
2. **Portable by default, installed by explicit opt-in.** All paths resolve through
   `data_dir()`, `config_dir()` or `resource_dir()` — never a bare `~/.config`,
   `~/.local/share`, `~/.cache`, `/tmp`, or hardcoded absolute path. In portable mode
   (the default), `data_dir()` and `config_dir()` both resolve beside the executable:
   copying the folder to a USB stick and running it elsewhere must work with all data
   intact. Installed mode redirects both to the OS's standard per-user locations, and
   only activates when the executable is frozen *and* a `.installed` marker file sits
   beside it, written by `install.sh` or a future `.deb` postinst — never inferred from
   XDG variables alone. The marker opts IN; portable never opts OUT. A missing marker
   must never silently relocate a portable user's collection into their home directory,
   so a mispackaged installer should fail loudly (a permissions error writing beside a
   read-only system executable) rather than silently splitting a collection across two
   locations.
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
├── sellers.toml               seller directory — optional, created on first use
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

### Sellers

`sellers.toml` lives in `data_dir()` beside `watches/` — **not** `config_dir()`. It is
user-authored content that travels with the collection and falls under the same backup
scheme as `watch.toml`, unlike `config.toml`, which is UI state. Ships absent; the app
works normally without it and creates it only the first time the owner adds a seller
through the manage-sellers dialog.

One `[[seller]]` block per entry:

```toml
[[seller]]
name = "Some Shop"
url = "https://example.com"
city = "Istanbul"
notes = "Good prices on vintage Seiko"
```

`name` is required; `url`, `city` and `notes` are optional. Rebuilt fresh via `tomlkit`
on every save, the same treatment `docs/schema.md` already documents for `watch.toml`'s
own array-of-table sections (`straps`, `log`, `timing`) — no per-entry comment
preservation, not a new pattern.

**Loose coupling, deliberately.** A watch's `acquisition.seller` (§4) is always a plain
string, never a reference into `sellers.toml`. There is no foreign key and no
referential-integrity check — this project has no relational model, and adding one for
a convenience directory would be exactly the abstraction-ahead-of-need §9 rules out.
Deleting a `sellers.toml` entry must never orphan or alter a watch: the seller name stays
on the watch exactly as typed, and only the ability to render it as a link (§5.6, when
the name matches an entry that has a `url`) is lost.

### Git

The code is version-controlled; **the collection is not**. Watch data contains serial
numbers, purchase prices and seller details and must never be committed. Create this
`.gitignore` in milestone 1, before the storage layer exists:

```gitignore
watches/*
!watches/_template.toml
!watches/.gitkeep
config.toml
sellers.toml
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
| `rating` | int 0–5 | personal, not a review score. Dual meaning by status (§5.12): desire on a Wishlist watch, satisfaction on an Owned one — the same field, not a separate priority field |
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
| `price` | number | what was paid |
| `target_price` | number | what it costs — distinct from `price`, never overloaded onto it. A wishlist watch's asking or expected price |
| `target_date` | date | optional — when the owner hopes to buy |
| `currency` | string | default TRY |
| `seller` | string | editable combo (§5.7); rendered as a link in the detail view (§5.6) when it matches a `sellers.toml` entry (§3) with a `url` |
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
- **Top bar.** A Collection / Wishlist scope selector (§5.12), search field, view toggle
  (Grid / Table / Calendar), sort dropdown, and "Add watch" as the one primary-weight
  control in the app. Scope is orthogonal to view.
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
selected watch has a value are hidden. Each column header carries a thin bar in that
watch's `slug_color()` (§5.5's year-view hue, one per watch) — the same hue the three
visuals above the table use, so the whole screen reads as one linked comparison rather
than four unrelated widgets.

This is the app's most useful screen for deciding what to wear or what to buy next.
Build it in milestone 8, but shape the table view's data access so it isn't a second
implementation.

**Milestone 15 adds three visuals above the table**, all `QPainter`, the same restrained
vocabulary as the Stats mode charts below (§6). Each hides itself independently when it
has nothing to show — a selection with no case, accuracy or bar-eligible data at all
shows only the plain table, not three empty husks above it.

- **Case silhouette.** Every selected watch's case outline at one shared scale, sharing a
  single centre point so differences read as concentric offsets, not a side-by-side
  lineup: a circle at `diameter_mm` with lug blocks above and below extending to
  `lug_to_lug_mm`, thin-stroked in the watch's slug colour, never filled. Beneath it, a
  side-profile strip — one outline per watch, width `diameter_mm`, height
  `thickness_mm`, the dimension a spec table alone under-communicates — at the same
  scale, plus an mm scale bar so the drawing's trueness to scale is checkable, not just
  asserted. A legend names every selected watch in its slug colour with `diameter_mm`
  and `lug_to_lug_mm` in monospace. A watch missing `diameter_mm` cannot be drawn — it is
  omitted from the drawing and named in the legend as having no case data, never drawn
  as a zero-radius circle. The whole section hides when fewer than two selected watches
  have `diameter_mm`; the side-profile strip additionally hides on its own when fewer
  than two drawable watches have `thickness_mm`.
- **Accuracy ranges.** One horizontal span per watch with both `accuracy_min` and
  `accuracy_max`, in its slug colour, on one shared sec/day axis with zero marked
  prominently. A watch specifying sec/month is converted (÷30) for the axis but labelled
  with its original value and unit, never the converted one. A quartz movement's span is
  meant to render as a near-invisible hairline beside a mechanical's wide one — that
  contrast is the point, so the axis is never compressed, clipped or log-scaled to make
  spans look more comparable, only clamped to a minimum visible width so "near-invisible"
  does not become "literally invisible." Hidden when fewer than two selected watches have
  both accuracy endpoints.
- **Dimension bars.** One row per qualifying numeric attribute, one bar per watch in its
  slug colour with the value in monospace at the end, scale shared within a row and never
  across rows — comparing weight against water resistance on one axis would be
  meaningless. Qualifying attributes are weight, water resistance, power reserve, lug
  width, and price or target price depending on the active scope (§5.12); diameter,
  lug-to-lug and thickness are excluded since the silhouette above already covers case
  geometry. A watch with no value for a row shows an em-dash in its slot, not a
  zero-length bar; a row hides itself when fewer than two selected watches have a value
  for it.

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

**Navigation.** A Today button returns Month mode to the current month and Year mode to
the current year. A compact month (dropdown) and year (spinbox) jump sits inline in the
header beside the prev/next arrows — inline controls, not a dialog, and not a separate
"jump to date" screen.

**Stats mode**, the third choice in the same header toggle as Month and Year. A period
selector — This month / This year / All time, three fixed choices, not a date-range
picker (§9 still bans settings GUIs) — drives every section below it. This month and This
year are the full calendar unit containing today, not "elapsed so far"; All time runs
from the earliest date any watch was ever worn through today. Sections, in this order:

- **Rotation** — every watch worn at least once this period, ranked by days worn
  descending, each a hairline bar with a tick at the even-split mark (period days ÷ watch
  count) and a monospace day count plus its share of days recorded. The even-split tick
  is omitted below two watches — meaningless with one, and it would land at the same
  spot as a full bar.
- **Not worn in this period** — the complementary list, plain, no bars.
- **Coverage and the period-over-period deltas** — monospace figures; the deltas compare
  against the previous equivalent month or year and use explicit `+`/`-` signs. All time
  has no previous equivalent, so it shows coverage alone.
- **Weekday strip** — seven cells, each carrying the colour chip of the watch worn most
  often on that weekday this period, reusing Year view's slug colour.
- **Streaks** — the longest run of consecutive days on one watch this period, and the
  longest run of consecutive days with nothing recorded.

Every section hides itself when it has nothing to say — Rotation and the weekday strip
disappear when nothing was worn this period, but Not worn still lists the whole
collection and Coverage still prints a plain 0%, rather than the page going blank. Only a
genuinely empty collection (no watches at all) replaces the sections with the same quiet
tone the app uses elsewhere, not a page of zeroed-out figures.

Clicking a watch in Rotation switches to Month mode with that watch's days at full
strength and every other day — including empty ones — dimmed toward the plate. This is
what makes the stats actionable rather than decorative: keep navigating months and the
emphasis follows. It clears on Escape or on switching mode again, never on its own.

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
- A watch's seller, in Acquisition, renders as a `QDesktopServices` link — the same
  hand-off the acquisition URL already uses — when it matches a `sellers.toml` entry
  (§3) that has a `url`. Plain text otherwise.
- Edit and Delete at the bottom. Delete requires typing the model name to confirm. A
  Wishlist watch additionally gets a one-click "Mark as Owned" action (§5.12).

### 5.7 Add / edit form
A tabbed dialog mirroring the data model groups; the same dialog serves both operations.

- Tab order matches the spec group order. Never force a wizard.
- Numeric fields are numeric inputs with units as suffixes inside the field, not as
  separate labels.
- The Movement tab swaps `power_reserve_hours` for `battery_life_years` and changes the
  accuracy unit when `kind` is Quartz or Solar.
- The seller field is an enum*-style combo (§4): `sellers.toml` entries plus every
  seller value already used in the collection, plus free text. A "Manage sellers…"
  action beside it opens a small add/edit/delete dialog over `sellers.toml` (§3); typing
  free text directly never touches that file.
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

### 5.12 Wishlist
A second scope alongside the collection itself, for watches not yet owned — selected in
the top bar (§5.1), orthogonal to the Grid/Table/Calendar view toggle. **Collection** is
every watch whose `status` is not Wishlist (Owned, Incoming, Sold, Gifted, exactly as
before — still narrowable through the Status sidebar facet). **Wishlist** is exactly the
watches whose `status` is Wishlist. Persisted in `config.toml` alongside the active view.

Grid and Table both work in either scope. Calendar and Stats are Collection-only —
hidden, not disabled, when the scope is Wishlist, since a watch that isn't owned yet has
no wear history to show. Sidebar facets follow the active scope's watches; the Status
facet and the "Not worn in 90 days" facet are both dropped in Wishlist scope — the first
is fixed by the scope selector itself, the second is trivially true for every watch in it.

**Correctness.** A watch whose `status` is not Owned — Wishlist, but also Incoming, Sold
or Gifted — never wears anything: excluded from the calendar, all calendar stats
(including the Stats mode even-split reference, which a Wishlist watch previously
inflated), and strap compatibility in both directions, as a target and as a donor.
Enforced once, at the source, in `wear.py` and `strap_compat.py` — not per view.

**Presentation.** Grid cards replace the "Wore this today" affordance and the
maintenance-due dot (both Owned-only) with target price and rating, always visible
rather than hover-only. Table's default columns become Brand, Model, Target Price,
Rating, Seller — the existing column-preset dropdown still applies, and column choices
are remembered separately per scope. Sort gains Rating and Target Price in place of
Least Worn and Acquired, which don't apply before a purchase. The sidebar's summary
footer (§5.10) is replaced by total target price by currency, item count, and — only
when at least one watch has a target date set — the subtotal falling in the next twelve
months. Plain monospace figures, same restraint as §5.10.

**Moving to Owned.** A watch's detail page gets a "Mark as Owned" action when its status
is Wishlist — one click, no dialog. It sets `status` to Owned and carries `target_price`
into `price` as a default, only when `price` isn't already set; `target_price` and
`target_date` are left as they are afterward, not discarded. Adding a watch while in
Wishlist scope defaults its status to Wishlist for the same reason a Collection-scope
add defaults to Owned — otherwise it would vanish from the scope it was just added from.

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

**Type.** Ubuntu — bundled in `saat/resources/fonts/` (Ubuntu Font Licence 1.0) rather
than relying on a system package, with a detected fallback so the app does not break
if loading fails. Ubuntu Sans Condensed for labels and column headers, Ubuntu Sans
for body and titles, **Ubuntu Mono for every number**: diameters, bph, accuracy,
prices, dates. Measurements in monospace with tabular figures is not decoration, it
makes a spec table readable at a glance. Scale: 11 / 13 / 15 / 20 / 28. Weights 400
and 600 only.

**Signature element.** One, in one place: spec group headers in the detail view sit on a
**minute track** — a hairline rule bearing fine ticks, longer every fifth, the way a
dial's chapter ring is printed. Draw it with `QPainter` in `--rule`, running to the edge
of the column, so it adapts automatically to whichever mode is active. That is the app's
only flourish. Everything else stays plain: no gradients, no glows, no escalating corner
radii, no drop shadows beyond a 1 px hairline border.

**Data visualisation.** The calendar's Stats mode (§5.5) and the compare view's three
visuals (§5.4) are the only places the app draws anything resembling a chart, and both
stay inside one narrow, plain vocabulary: hairline bars, a tick mark referencing a
reference value (the even-split figure in Stats mode, zero in compare's accuracy
ranges), colour chips or strokes reusing Year view's per-slug hue, monospace figures for
every count, percentage, delta and measurement, and — added by the compare view's case
silhouette — **to-scale technical drawing**: outlines at one shared, honestly-computed
scale with an accompanying mm scale bar, no fill, the same restraint as everything else
here. All of it `QPainter` in the active palette, the same discipline as the minute
track — nothing rasterised, nothing imported. Every axis this vocabulary produces is
single-unit — millimetres, sec/day, one physical unit per dimension-bar row — and never
implies an ordering or a shared scale that doesn't exist; mixing units on one axis is
banned exactly as before, this vocabulary just now has more places it applies. Pie
charts, gauges, progress rings and any charting dependency stay out of bounds everywhere
in the app, the collection summary included (§5.10, unchanged: plain figures there too).

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
milestone *n+1* before *n* runs. Every milestone — including follow-ups like
packaging fixes that never made it into the numbered list below — bumps
`__version__` (`saat/__init__.py`) and adds its entry to `CHANGELOG.md` in the same
commit. `tests/test_version.py` enforces that the two never drift apart, the same
as every other invariant here: checked, not remembered.

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

Three ways to run, all supported, all documented in the README.

**Development:** `run.sh` — creates `.venv` if absent, installs the three dependencies,
sets `QT_QPA_PLATFORM=wayland`, runs `main.py`. Works from a fresh clone with no
arguments. Always portable mode (never frozen, so a `.installed` marker is moot).

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
`_internal/`. This is the default the moment the folder is copied anywhere — no marker
file, no setup step.

**Installed build:** `install.sh` copies the portable build to `/opt/saat`, writes a
`.installed` marker beside the executable, symlinks `/usr/local/bin/saat`, and adds an
application-launcher entry. The marker is what switches the app to installed mode:

```
/opt/saat/                    ~/.local/share/saat/    ~/.config/saat/
├── SAAT        executable    ├── watches/             └── config.toml
└── _internal/                └── backups/
```

`uninstall.sh` reverses everything `install.sh` did and never touches
`~/.local/share/saat` or `~/.config/saat`. Both scripts are the reference a future
`.deb`'s postinst/prerm will follow — same steps, just invoked by dpkg instead of by
hand.

Do **not** use `--onefile`: it extracts to a temp directory on every launch, which is
slow with Qt bundled and puts application files outside the data directory.

Do **not** build an AppImage: they are mounted read-only, so the data directory cannot
live inside one, and they need FUSE 2, which Arch does not install by default.

### Path resolution — implement in milestone 1, split in milestone 12

Every path derives from one of three helpers — never a bare `~/.config`,
`~/.local/share`, or hardcoded absolute path. A frozen executable resolves `__file__`
differently than a script, and PyInstaller's `sys._MEIPASS` points at bundled
resources, never at writable data. Getting this wrong breaks portability silently.

```python
import os, sys
from pathlib import Path

INSTALLED_MARKER = ".installed"

def _installed_mode() -> bool:
    # Opt-in only: frozen AND the marker install.sh writes is present beside
    # the executable. A missing marker must always mean portable.
    if not getattr(sys, "frozen", False):
        return False
    return (Path(sys.executable).resolve().parent / INSTALLED_MARKER).exists()

def _portable_dir() -> Path:
    if os.environ.get("APPIMAGE"):            # AppImage: the .AppImage file's folder
        return Path(os.environ["APPIMAGE"]).resolve().parent
    if getattr(sys, "frozen", False):         # PyInstaller: the executable's folder
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent    # source checkout

def _resolve(xdg_env: str, xdg_default_subpath: tuple[str, ...]) -> Path:
    # Precedence: SAAT_DATA_DIR env var > installed mode (XDG) > portable.
    if "SAAT_DATA_DIR" in os.environ:
        path = Path(os.environ["SAAT_DATA_DIR"])
    elif _installed_mode():
        base = os.environ.get(xdg_env) or str(Path.home().joinpath(*xdg_default_subpath))
        path = Path(base) / "saat"
    else:
        path = _portable_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path

def data_dir() -> Path:
    return _resolve("XDG_DATA_HOME", (".local", "share"))

def config_dir() -> Path:
    return _resolve("XDG_CONFIG_HOME", (".config",))
```

`watches/` and `backups/` resolve from `data_dir()`; `config.toml` from `config_dir()`.
`SAAT_DATA_DIR`, when set, collapses both to the same directory regardless of mode — an
escape hatch for testing and for a power user who wants one folder either way. Bundled
read-only resources — the QSS theme, fonts, icons — resolve from `sys._MEIPASS` when
frozen and from the package directory otherwise, via a separate `resource_dir()`, wholly
unaffected by portable vs. installed. The three must never be confused.

Verify before calling either build done: copy the portable build to a different path,
run it, add a watch, confirm the file lands in the copied folder. Then `install.sh`,
launch via the launcher entry, add a watch, confirm it lands under `~/.local/share/saat`
and that `/opt/saat` stays untouched. Then `uninstall.sh` and confirm the collection
survives.

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
