# Building SAAT

Everything below is for building SAAT yourself. If you only want to use it, the
[README](../README.md) has the two commands you need — this page is not on that
path.

Released binaries are built by CI, not by hand: pushing a tag runs
`.github/workflows/release.yml`, which produces the portable tarball and the `.deb`
from one build and attaches both to the release. See
[DEVELOPMENT.md](DEVELOPMENT.md) for the release procedure and `packaging/README.md`
for how the package is put together and why.

## Run from a clone

```sh
./run.sh
```

From a fresh clone, with no arguments. `run.sh` creates a local `.venv/` if one is
absent, installs `requirements.txt` into it, sets `QT_QPA_PLATFORM=wayland`, and
launches the app.

This is always portable mode — it is never frozen, so the `.installed` marker is
moot. Your data (`watches/`, `config.toml`, `backups/`) lives in the project root,
beside `run.sh`.

SAAT has three runtime dependencies, pinned to exact versions in `requirements.txt`:
**PySide6**, **tomlkit** and **Pillow**. That file is the single place they are
declared — `run.sh` and both CI workflows install from it rather than naming
packages themselves.

On Arch, the system Python is externally managed (PEP 668), so a bare `pip install`
into it is refused. The `run.sh` venv route sidesteps that and is self-contained;
`sudo pacman -S pyside6 python-pillow` also works if you prefer.

On Windows, use `run.ps1` instead:

```powershell
.\run.ps1
```

If PowerShell refuses to run it, Windows is blocking unsigned local scripts — either
`powershell -ExecutionPolicy Bypass -File .\run.ps1` once, or
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` permanently.

It is a separate file rather than something clever because of one deliberate
difference: `run.sh` exports `QT_QPA_PLATFORM=wayland` and `run.ps1` does not set
`QT_QPA_PLATFORM` at all. Windows has one platform plugin, Qt selects it correctly,
and forcing anything there is at best redundant and at worst breaks the app.

## Run the tests

```sh
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -t .
```

Roughly a thousand tests, all headless — no test needs a real display or `xvfb`.
`LANG`/`LC_ALL` should be set to something UTF-8 and English: several i18n tests
assert against an English ambient default, matching a real desktop rather than a
locale-less container.

## Build the portable folder

PyInstaller is a **build-time tool only**, which is why it lives in
`requirements-build.txt` rather than in the app's three runtime dependencies.
Install it alongside them in the venv `run.sh` created, then build from the
committed spec:

```sh
.venv/bin/pip install -r requirements-build.txt
.venv/bin/pyside6-lrelease saat/resources/i18n/saat_tr.ts -qm saat/resources/i18n/saat_tr.qm
.venv/bin/pyinstaller SAAT.spec
```

The `lrelease` step is not optional. `SAAT.spec` bundles whatever is already in
`saat/resources/i18n/` at build time, and the compiled `.qm` is gitignored — so a
build without it silently ships without the Turkish translation and falls back to
English, which looks almost right rather than failing.

The result is `dist/SAAT/`:

```
SAAT/
├── SAAT          the executable
├── _internal/    bundled Qt and Python runtime (read-only)
├── watches/      created on first use
├── config.toml   created on first use
└── backups/      created on first use
```

Copy the whole folder anywhere and run `./SAAT`. Data is created and read beside the
executable, never inside `_internal/`.

The build is deliberately **one-folder** (`--onedir`), never one-file: one-file
re-extracts the whole Qt runtime to a temp directory on every launch and would put
your data outside the app folder. AppImage is not used either — they are mounted
read-only, so the data directory cannot live inside one, and they need FUSE 2.
`SAAT.spec` documents the rest of the shape.

## Build for Windows

Needs a Windows machine — a Windows binary cannot be cross-built from Linux, which
is why CI has a separate `windows-latest` job rather than reusing the Linux one.

```powershell
.venv\Scripts\pip install -r requirements-build.txt
.venv\Scripts\pyside6-lrelease saat\resources\i18n\saat_tr.ts -qm saat\resources\i18n\saat_tr.qm
.venv\Scripts\pyinstaller SAAT.spec
```

That produces `dist\SAAT\` — the same one-folder layout as Linux, with `SAAT.exe` in
place of `SAAT`. Zip it for the portable artifact. Then, for the installer:

```powershell
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" /DAppVersion=2.1 packaging\windows\saat.iss
```

which writes `dist\SAAT-v2.1-windows-x64-setup.exe`.

`SAAT.spec` needs no separate Windows variant. It is platform-aware in exactly one
place — it generates a `VERSIONINFO` resource from `saat.__version__` when
`sys.platform == 'win32'` — and everything else in it was already portable:
tuple-form `datas`, `console=False`, and a real multi-resolution `.ico`.

The installer is per-user (`PrivilegesRequired=lowest`), installs to
`%LOCALAPPDATA%\Programs\SAAT`, and ships the `.installed` marker as a file so the
uninstaller removes it. Note that the program directory and the data directory
(`%LOCALAPPDATA%\SAAT`) are **siblings, not nested** — that is what makes "uninstall
never removes the collection" structural rather than a promise, and it is why
`DefaultDirName` must never be changed to `{localappdata}\SAAT`.

**The installer is unsigned and will trip SmartScreen.** There is no way around that
without a code-signing certificate, and attempting one is out of scope. The README
tells users the two clicks needed.

## Install it system-wide without a package

For distributions without `apt`. Build the portable folder first, then:

```sh
sudo ./install.sh
```

This copies `dist/SAAT` to `/opt/saat`, writes the `.installed` marker that switches
it to the per-user data locations, symlinks `/usr/local/bin/saat` onto your PATH, and
installs the launcher entry and icon.

```sh
sudo ./uninstall.sh
```

reverses all of it. It never touches `~/.local/share/saat` or `~/.config/saat`.

The launcher entry is `packaging/saat.desktop`, shared with the `.deb` so the two
installs cannot drift apart. Its `Exec` is the bare command `saat`, which resolves
through PATH to whichever of the two is installed.

## Build the `.deb`

Needs a Debian or Ubuntu machine — `dpkg-deb` and, for the checks, `lintian`.

```sh
sudo apt install dpkg-dev lintian
.venv/bin/pyinstaller SAAT.spec        # if you have not already
./packaging/build-deb.sh
lintian dist/saat_*.deb
```

The output is `dist/saat_<version>-1_amd64.deb`.

`build-deb.sh` composes the FHS tree with `packaging/stage-tree.sh`, adds the
`DEBIAN/` control metadata, and calls `dpkg-deb`. Before it does, it runs
`packaging/audit-bundle.py`, which fails the build unless three things hold: every
system library the bundle needs is covered by the `Depends` line or explicitly
excluded with a reason; the highest glibc symbol version in the bundle is within the
2.35 floor `Depends` promises; and every bundled shared object is covered by a
`Files:` stanza in `packaging/debian/copyright`.

That last one matters more than it looks. PyInstaller decides what goes into the
bundle from whatever the build machine's wheels link against, so the set shifts
under you — and this package redistributes all of it.

`packaging/README.md` explains why the package bundles Qt rather than depending on
Debian's `python3-pyside6`, why `dpkg-deb` rather than `debhelper`, and why
`/usr/bin/saat` being a symlink is safe.

Note that a `.deb` built on a machine newer than Ubuntu 22.04 will fail the glibc
check on purpose — the released package is built on `ubuntu-22.04` so that it runs
on every distribution the release notes name. A locally built one is fine for
testing packaging changes, but is not a release artifact.
