# SAAT — Watch Collection Manager

A local, offline desktop app for cataloguing a mechanical-watch collection: grid,
table and calendar views, a photo-forward detail page, wear tracking, side-by-side
comparison, and light/dark themes. Every watch is a plain TOML file on disk — no
database, no network, no accounts. See [`SPEC.md`](SPEC.md) for the full design.

Built with PySide6 (Qt 6). Runs natively on Wayland.

## Requirements

- Python 3 and a Wayland session
- Three runtime dependencies, installed for you by `run.sh`: **PySide6**, **tomlkit**, **Pillow**

## Run it (development)

From a fresh clone, with no arguments:

```sh
./run.sh
```

`run.sh` creates a local `.venv/` if one is absent, installs the three dependencies
into it, sets `QT_QPA_PLATFORM=wayland`, and launches the app. Your data —
`watches/`, `config.toml`, `backups/` — lives in the project root, beside `run.sh`.

## Build a portable version

The portable build is a self-contained folder you can copy anywhere — it carries its
own Qt and Python runtime and needs nothing installed on the target machine.

It is produced with [PyInstaller](https://pyinstaller.org), which is a **build-time
tool only** — not one of the app's three runtime dependencies. Install it alongside
them in a venv (the one `run.sh` created works), then build from the committed spec:

```sh
.venv/bin/pip install pyinstaller
.venv/bin/pyinstaller SAAT.spec
```

The result is `dist/SAAT/`:

```
SAAT/
├── SAAT          the executable
├── _internal/    bundled Qt and Python runtime (read-only)
├── watches/      created on first use
├── config.toml   created on first use
└── backups/      created on first use
```

Copy the whole `SAAT/` folder wherever you like and run `./SAAT`. Your data
(`watches/`, `config.toml`, `backups/`) is created and read **beside the
executable**, never inside `_internal/`, so the folder is fully portable — move it to
a USB stick or another machine and the collection travels with it.

The build is deliberately **one-folder** (`--onedir`), not one-file: one-file
re-extracts the whole Qt runtime to a temp directory on every launch and would put
your data outside the app folder. AppImage is not used either (mounted read-only, so
the data directory can't live inside it, and it needs FUSE 2). See `SAAT.spec` for
the specifics.

## Where your data lives

Each watch is its own folder under `watches/`, containing a `watch.toml` and an
`images/` subfolder. [`watches/_template.toml`](watches/_template.toml) documents
every field; copy it into a new `watches/<some-slug>/watch.toml` to hand-author a
watch, or just use **Add watch** in the app. Edits back up the previous `watch.toml`
into `backups/` (pruned to the newest 20) before overwriting.

## Notes

- **Wayland.** The app runs natively on Wayland and picks the Wayland Qt backend
  automatically. If your session ever falls back to X11, force it with
  `QT_QPA_PLATFORM=wayland` (which is exactly what `run.sh` does).
- **Arch / PEP 668.** Arch's system Python is externally managed, so a bare
  `pip install` into it is refused. The `run.sh` venv route sidesteps this and is
  self-contained; alternatively `sudo pacman -S pyside6 python-pillow` installs the
  Qt and imaging pieces system-wide if you prefer.
