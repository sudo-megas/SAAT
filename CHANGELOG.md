# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
