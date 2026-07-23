# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
