# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.7.0] - 2026-07-27

### Added

- Export to PDF: `Ctrl+P` or the new top-bar button renders whatever the
  collection view is currently showing — the active scope (Collection or
  Wishlist), active filters, active search, and current sort order — to a
  document you save wherever you like. A summary page (title, generation
  date, item count and total value by currency, a compact table) is
  followed by one page per watch: a generously sized primary photo (or an
  informative placeholder if it doesn't have one yet), its identity, and
  full specs in the same order and vocabulary the detail page uses —
  minute-track section headers, monospace figures — continuing onto
  further pages rather than clipping anything for a watch detailed enough
  to need them. A4 by default, Letter for a US/Canada locale. Exporting an
  empty view (nothing currently visible) is refused with a plain message
  rather than producing an empty document.
- SPEC.md §9 narrowed to permit this: local document generation to a path
  you choose remains the one exception to the export ban — cloud sync,
  sharing, a showcase mode, and any other export format stay exactly as
  banned as before.

## [1.6.5] - 2026-07-27

### Added

- Single-instance enforcement: launching SAAT while it's already running against
  the same collection now raises and focuses the existing window instead of
  starting a second process against the same files. Two portable copies pointing
  at different collections still both run fine.
- A system tray icon, on desktops that provide one (checked at startup, never
  assumed). Left click shows or hides the window; right click opens a menu with
  Show/Hide, a "Wore today" submenu listing your most recently worn watches,
  "Close to tray" (closing hides instead of quitting; off by default), "Start
  minimised", and Quit. The first time the window is hidden to the tray, a
  one-time message explains how to bring it back. On a desktop with no tray,
  none of this appears — closing always quits, exactly as before.
- Autostart, offered only in an installed copy: a "Start at login" option in the
  tray menu registers SAAT to launch at login via the standard XDG mechanism.
  Combined with "Start minimised", an autostarted launch can go straight to the
  tray without showing a window — a manual launch always shows one.

### Changed

- `uninstall.sh` now also removes the autostart entry, alongside everything else
  it already reversed.

## [1.6.0] - 2026-07-26

### Added

- The collection empty state now centres on a `QPainter` watch dial showing the real
  current time — chapter ring, hour and minute hands, a gilt centre pinion, lug blocks
  top and bottom — above the same quiet copy as before. The minute hand moves exactly on
  the minute, and the clock only ever runs while the empty state is on screen.
- A full-screen image viewer: click the detail page's primary photo or any gallery
  thumbnail to open the original file (not a thumbnail) at fit-to-window, zoomable with
  the mouse wheel and pannable by dragging once zoomed in, double-click to toggle 100%,
  arrow keys to move through the gallery, Escape to close.
- The detail page's primary photo is now substantially larger and composed beside the
  brand/model header rather than stacked above it, with a hairline accent in the watch's
  own colour beneath the title — the same hue already used to tell watches apart in the
  compare view and calendar year view.
- A perlage micro-texture — the same graining finish real movement plates carry — on the
  sidebar background and the empty-state backdrop, at a contrast low enough to read as
  texture rather than pattern in both themes.

### Changed

- Clicking a detail-page thumbnail now opens the full-screen viewer instead of promoting
  it to the primary photo; choosing a different primary photo is still available, from
  the edit form's Images tab.
- Fixed a latent bug the image viewer surfaced: a photo's EXIF rotation tag (as most
  phone cameras record) is now applied when displaying an original file, matching what
  the gallery thumbnails already showed correctly.

## [1.5.0] - 2026-07-24

### Added

- A cohesive hand-drawn icon set (grid/table/calendar view, compare, search, add,
  back, edit, delete, wore-today, today, month navigation, sidebar collapse, clear
  filters, sort direction, image actions, collection/wishlist scope) replacing bare
  Unicode stand-ins throughout, always alongside the existing text label or tooltip,
  never in place of one. A small clear-all control in the sidebar, visible only while
  a filter is active, and a real ascending/descending toggle beside the top bar's
  sort combo.
- Motion: view and mode switches cross-fade, the sidebar's collapse/expand eases its
  width, and a grid card's border eases between hairline and gilt on hover — one
  160ms duration and easing curve throughout, nothing animating on first paint.
- A partial tick arc — the same "minute track" vocabulary already used for the
  detail page's spec groups — behind a grid card's placeholder tile when a watch has
  no photo yet, and a second, undecorated minute track separating sections in the
  calendar's Stats mode.

### Changed

- A full pass of stock Qt chrome that had never been explicitly styled: scrollbars
  (now a thin hairline, widening slightly on hover), tooltips, combo-box popups,
  context menus, checkboxes, spin-box step buttons, the date-edit calendar popup,
  dialog button boxes, line-edit placeholder text, and disabled states across the
  above.
- Grid card photos now clip to the card's own corner radius with a hairline at the
  photo edge instead of square corners overrunning it; compare-selection gets its
  own static border and background treatment, distinct from hover's animated one.
  Monospace figures in the table and compare views are right-aligned so they land in
  a column instead of merely sharing a font; uppercase small-caps labels carry a
  slight letter-spacing.
- No tooling attribution anywhere in the project going forward — see SPEC.md §9.

## [1.4.0] - 2026-07-24

### Added

- Compare view: three `QPainter` visuals above the existing comparison table, each
  hiding itself independently when it has nothing to show.
  - **Case silhouette** — every selected watch's case outline at one shared, true
    scale, sharing a single centre point so size differences read as concentric
    offsets rather than a side-by-side lineup. A side-profile strip (width x
    thickness) at the same scale, an mm scale bar, and a legend naming any watch too
    incomplete to draw.
  - **Accuracy ranges** — one horizontal span per watch on a shared sec/day axis with
    zero marked prominently. A watch specifying sec/month is converted for the axis
    but labelled with its original value and unit; a quartz movement's span is meant
    to render as a near-invisible hairline beside a mechanical's wide one, and the
    axis is never compressed or rescaled to hide that.
  - **Dimension bars** — one row per qualifying attribute (weight, water resistance,
    power reserve, lug width, and price or target price depending on scope), one bar
    per watch, scale shared within a row only. Diameter, lug-to-lug and thickness are
    excluded — the silhouette already covers case geometry.
  - Every compare column header now carries a thin bar in that watch's per-slug hue
    (the same one Year view uses), visually linking the table to the visuals above it.
- SPEC.md §5.4 documents the three visuals and their hide-when-empty rules; §6's data
  visualisation vocabulary gains to-scale technical drawing as a permitted form,
  alongside the existing hairline-bar/tick/colour-chip/monospace set.

## [1.3.0] - 2026-07-24

### Added

- Wishlist scope: a Collection/Wishlist selector in the top bar, orthogonal to the
  Grid/Table/Calendar view toggle. Wishlist is exactly the watches whose status is
  Wishlist; Collection is everything else, unchanged. Calendar and Stats are hidden
  (not disabled) in Wishlist scope, since a watch not yet owned has no wear history.
  Sidebar facets and the summary footer, table defaults, sort options and remembered
  column choices all follow the active scope.
- Two new Acquisition fields: `target_price` (what it costs) and `target_date` (when
  the owner hopes to buy), distinct from `price`/`date`. The existing rating field
  doubles as desire on a Wishlist watch rather than adding a separate priority field.
- Wishlist grid cards show target price and rating in place of the Owned-only
  Wore-today action and maintenance indicator; the sidebar's summary swaps to total
  target price by currency, item count, and — when any target date is set — the
  subtotal due in the next 12 months.
- A one-click "Mark as Owned" action on a Wishlist watch's detail page, carrying
  target price into price as a default (only when price isn't already set) without
  discarding either target field. Adding a watch from Wishlist scope now defaults its
  status to Wishlist.
- Sellers: an optional `sellers.toml` directory (name, url, city, notes) living beside
  `watches/`, managed through a new "Manage sellers…" dialog reachable from the
  add/edit form. The seller field is now an editable combo offering `sellers.toml`
  entries plus every seller already used in the collection, still accepting free text.
  A watch's seller renders as a clickable link on its detail page when it matches a
  `sellers.toml` entry with a URL. Deliberately loosely coupled — a watch's seller
  stays a plain string, and deleting a `sellers.toml` entry never touches a watch.

### Fixed

- A watch whose status wasn't Owned (Wishlist, but also Incoming, Sold or Gifted)
  previously counted toward wear tracking: it showed up in the calendar's assignment
  picker and, if it had any recorded wear, in every calendar stat — including
  inflating the Stats mode even-split reference's denominator even though it could
  never actually be worn. Non-Owned watches are now excluded from the calendar, all
  calendar stats, and strap compatibility (in both directions), fixed once at the
  source rather than per view.

## [1.2.0] - 2026-07-24

### Added

- Calendar Stats mode: rotation ranked by days worn with an even-split reference tick,
  a not-worn list, coverage and period-over-period deltas, a weekday-most-worn strip, and
  longest-run/longest-gap streaks, over three fixed periods (This month / This year / All
  time). Every section hides itself when it has nothing to say rather than rendering
  zeroed-out figures. Clicking a watch in the Rotation list switches to Month mode with
  that watch's days emphasised and the rest dimmed, until mode change or Escape.
- Calendar navigation: a Today button, and an inline month/year jump beside the prev/next
  arrows, in Month and Year mode.
- SPEC.md §6 gains a Data visualisation subsection formalising the hairline-bar/tick/
  colour-chip/monospace vocabulary Stats mode uses, and re-banning pie charts, gauges,
  progress rings and any charting dependency app-wide.

## [1.1.0] - 2026-07-23

### Added

- Dual-mode paths: portable (default, unchanged from v1.0.x — data lives beside the
  executable) and installed (opt-in, for a future `.deb`). `data_dir()` and
  `config_dir()` replace `app_dir()`, resolving to the OS's standard per-user
  locations (`XDG_DATA_HOME`/`XDG_CONFIG_HOME`, default `~/.local/share/saat` and
  `~/.config/saat`) when the build is frozen *and* a `.installed` marker file sits
  beside the executable — never inferred, so a bare portable copy always stays
  portable.
- `SAAT_DATA_DIR` environment variable to override both locations at once, for
  testing and power users.
- `install.sh` / `uninstall.sh`: installs the portable build to `/opt/saat`, writes
  the `.installed` marker, symlinks `/usr/local/bin/saat`, and adds an
  application-launcher entry (and reverses all of it, without ever touching the
  user's collection).

### Fixed

- `install.sh` looked for the app icon at `/opt/saat/resources/icon/saat.png`; the
  correct path is `/opt/saat/_internal/resources/icon/saat.png` — PyInstaller's
  onedir layout puts every bundled resource under `_internal/`, not at the top
  level. Caught by actually running the installer against a real build.

## [1.0.1] - 2026-07-23

### Added

- GPL-3.0 licensing: `LICENSE` at the repo root, licence headers on `main.py` and
  `saat/__init__.py`, and a Licence section in the README covering PySide6's LGPL-3.0
  terms.
- Bundled Ubuntu Sans, Ubuntu Sans Condensed and Ubuntu Mono fonts
  (`saat/resources/fonts/`), loaded at startup via `QFontDatabase`. Previously the
  app shipped no fonts at all and silently fell back to a system default on any
  machine without IBM Plex installed.
- Application icon, hand-drawn to match the app's own visual language, set as the
  window icon and referenced in the PyInstaller build.
- `__version__` as a single source of truth (`saat/__init__.py`), shown in the
  window title.
- This changelog.

### Changed

- Typography: IBM Plex → Ubuntu (SPEC.md §6). Same Condensed/Sans/Mono role split,
  now bundled instead of relying on a system package.

## [1.0.0] - 2026-07-23

Initial release: a local, offline desktop app for cataloguing a mechanical-watch
collection. Every watch is a plain, editable TOML file on disk — no database, no
network, no accounts.

### Added

- Grid, table and calendar views — a photo-forward reflowing card grid, a
  configurable column table with presets, and a wear calendar with a year view.
- Detail page — spec groups, image gallery, a timing sparkline, a maintenance-due
  indicator, and strap-compatibility suggestions across the collection.
- Add / edit / delete — a full form dialog with image import and Pillow
  thumbnailing, backed by atomic writes and automatic backups (pruned to the newest
  20).
- Filter, search, sort — sidebar facets with live counts and fuzzy search across
  brand, model, reference, caliber and tags.
- Wear tracking — drag-range assignment on the calendar, a one-watch-per-day rule,
  wear stats, a per-watch strip, and "Wore this today".
- Compare view — up to four watches side by side, with matching values dimmed so
  the differences stand out.
- Light and dark themes — two hand-tuned palettes with a top-bar toggle, persisted
  to `config.toml`, contrast-checked across every view.
- Keyboard-driven navigation — `Ctrl+N/F/E/W/Q`, `Escape`, and arrow-key navigation
  in the grid and calendar, with visible focus rings throughout.
- Portable packaging — a PyInstaller one-folder build; data lives beside the
  executable, so the whole folder is portable.
