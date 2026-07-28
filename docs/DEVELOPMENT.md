# Development

Working notes for building SAAT. SPEC.md is authoritative on behavior and design —
this document covers process: how a milestone lands, and how a release ships.

## Release discipline

Every milestone bumps `__version__` in `saat/__init__.py` and adds its entry to
`CHANGELOG.md`, in the same commit. `tests/test_version.py` enforces this: the test
suite fails if `__version__` doesn't match the most recent version heading in
`CHANGELOG.md`.

## Platforms

SAAT runs on Linux and Windows. Since milestone 24 the test suite runs on both in CI
(`test.yml` has a matrix over `ubuntu-22.04` and `windows-latest`, `fail-fast: false`
so a failure on one cannot hide behind the other), and a release produces four
artifacts from two builds: a `.tar.gz` and a `.deb` from the Linux build, and a
`.zip` and an Inno Setup installer from the Windows one.

**The Wayland platform hint is Linux-only.** `run.sh` exports
`QT_QPA_PLATFORM=wayland` because Qt would otherwise sometimes pick the X11 backend
on the Wayland session this project targets. `run.ps1`, the Windows developer
launcher, deliberately does not set `QT_QPA_PLATFORM` at all: Windows has one
platform plugin, Qt selects it correctly, and forcing anything there is at best
redundant and at worst breaks the app. Nothing in `saat/` reads the variable — it is
a launcher concern on both platforms, which is why there are two launchers rather
than one with a branch.

Building on Windows:

```powershell
.\run.ps1                      # dev: creates .venv, installs, runs

.venv\Scripts\pip install -r requirements-build.txt
.venv\Scripts\pyside6-lrelease saat\resources\i18n\saat_tr.ts -qm saat\resources\i18n\saat_tr.qm
.venv\Scripts\pyinstaller SAAT.spec
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" /DAppVersion=2.1 packaging\windows\saat.iss
```

`SAAT.spec` is platform-aware in exactly one place: it generates a Windows
`VERSIONINFO` resource from `saat.__version__` when `sys.platform == 'win32'`, and
does nothing extra elsewhere. Everything else in it was already portable.

Three invariants are enforced on **every** platform rather than only where they are
needed, and the tests for them do not skip on Linux — see
`tests/test_platform_invariants.py`. Slug collisions are detected
case-insensitively; slugs are sanitised against Windows' reserved device names and
length limit; and the atomic write retries a locked destination. The reasoning is in
SPEC.md §2 and §3: a collection is a folder of plain files that gets copied between
machines, so a rule applied on one platform only produces collections the other
cannot open.

`docs/PLATFORM-AUDIT.md` is the inventory milestone 24 was built against — every
place the codebase assumed Linux, with file and line references. Worth reading
before touching the path layer or `autostart.py`.

## Localisation

SAAT ships English (default, no translation file) and Turkish. See SPEC.md's
localisation section for the design (why English is never auto-detected,
why storage stays canonical English). This section covers the mechanics.

Source strings live in `saat/*.py`/`saat/ui/*.py`, wrapped in `self.tr(...)`,
`QCoreApplication.translate(context, ...)`, or `QT_TRANSLATE_NOOP(context,
...)` depending on whether the call site has a live `self` (see the comments
at the top of `saat/ui/columns.py` and `saat/ui/detail_view.py` for which
shape a given file needs). `saat/resources/i18n/saat_{en,tr}.ts` are the
translation sources, committed. `saat/resources/i18n/*.qm` are compiled
build output, gitignored — never commit one.

**Regenerating after changing any translatable string:**

```
.venv/bin/pyside6-lupdate -extensions py saat -ts saat/resources/i18n/saat_en.ts saat/resources/i18n/saat_tr.ts
```

`-extensions py` must come *before* the path argument — PySide6's
`pyside6-lupdate` doesn't scan `.py` files by default, and the flag has no
effect if it trails the path instead of leading it. This updates both `.ts`
files' `<source>` text and locations; new strings appear as
`type="unfinished"`, needing a real Turkish translation before compiling
(not a machine-literal one — horological terms have an established Turkish
vocabulary; see the git history of `saat_tr.ts` for the existing glossary's
choices). `saat_en.ts` is a committed reference catalog only — English is
the source language and is never compiled to a `.qm` or loaded via a
translator (`saat/ui/i18n.py`'s "absent means English" — the same shape as
`saat/config.py`'s `theme_mode()`), so re-running `lupdate` against it is
just how `pyside6-lupdate`'s multi-target invocation naturally works, not a
build requirement.

**Compiling before running or building** (only `saat_tr.ts` needs this —
`saat_en.ts` is never compiled):

```
.venv/bin/pyside6-lrelease saat/resources/i18n/saat_tr.ts -qm saat/resources/i18n/saat_tr.qm
```

Run this before `pyinstaller SAAT.spec` every time — locally for development, and in the
same order in `.github/workflows/release.yml`'s build job for an actual release — since
the `.spec`'s `datas` entry copies whatever's already in `saat/resources/i18n/` at build
time, so a stale or missing `.qm` ships silently otherwise (SAAT falls back to English,
which "looks almost right" rather than failing loudly). Qt's own dialog-chrome strings
(`QMessageBox`/`QFileDialog`/`QDialogButtonBox` button labels) come from a *second*,
separate translation file, `qtbase_tr.qm`, which ships inside the PySide6
wheel itself, not this repo — nothing to regenerate here, and PyInstaller's
PySide6 hook bundles it into the frozen build automatically (`QtCore` is
always a transitive dependency, and it's always registered for `qtbase`
translations).

## Palettes

SAAT ships ten fixed palette presets (SPEC.md §6) — data files, not a theme editor; see
SPEC.md §9 for why an actual theme editor is out of scope. This covers adding an
eleventh.

Each palette is one file, `saat/resources/palettes/<id>.toml`, four keys plus the seven
colour roles:

```toml
id = "your-palette-id"
name = "Display Name"
is_dark = true

plate       = "#XXXXXX"
plate_high  = "#XXXXXX"
rule        = "#XXXXXX"
text        = "#XXXXXX"
text_muted  = "#XXXXXX"
gilt        = "#XXXXXX"
ruby        = "#XXXXXX"
```

If reproducing an existing named palette (the way the current eight beyond Default
Light/Dark do), cite the exact upstream source and the role-mapping decision behind each
value in a header comment — check against the source, don't eyeball it. `is_dark` drives
nothing in the UI directly, but is asserted against every palette's own measured plate
luminance in `tests/test_theme_contrast.py`, so it has to be right.

Register the new id in `saat/ui/theme.py`'s `_PALETTE_ORDER` tuple, at whichever position
it should appear in the popover — this tuple is the single source of truth for display
order; `_load_palette_registry()` reads each id from it explicitly, it never globs the
directory. `SAAT.spec`'s `datas` entry already bundles the whole
`saat/resources/palettes/` directory, so a new file needs no build-config change of its
own.

A generic English name (only "Default Light"/"Default Dark" today) needs an entry in
`theme.py`'s `_TRANSLATABLE_NAMES` plus a real Turkish translation (see Localisation
above); a proper noun like a named community palette passes through untranslated on
purpose.

A few tests hardcode the current count of ten and need updating alongside a new palette:
`tests/test_theme.py`'s `EXPECTED_PALETTE_ORDER`, `tests/test_palette_picker.py`'s copy
of the same list, and `tests/test_theme_contrast.py`'s
`test_exactly_ten_palettes_are_registered`. The rest of `test_theme_contrast.py` iterates
`theme.palettes()` rather than hardcoding a count, so a new palette gets the exact same
WCAG contrast checks automatically the moment it's registered — a failure there means the
values themselves need adjusting, not the test.

## Release checklist

Standing procedure for every milestone, once its feature work and tests are green. Later
milestones can just say "follow the release checklist."

The build, smoke test, and the GitHub release itself are handled by
`.github/workflows/release.yml`, triggered by pushing a tag — there is no manual
`pyinstaller`/`tar`/`gh release create` step in an actual release anymore. This checklist
is about landing the right source commit and tagging it; CI does the rest.

Since milestone 24 a release produces **four artifacts from two builds**. The Linux
build makes the portable `.tar.gz`, and the `deb` job wraps that same tarball rather
than building again — one build, two artifacts, so they cannot drift. The Windows
build has to happen on a Windows runner, so it produces its own `.zip` and Inno
Setup installer from one `pyinstaller` run. All four attach to the same release, and
every build job is in the release job's `needs:` list so one platform failing can
never leave a half-populated release behind. The `deb`
job also builds the package with `lintian` gating on errors and warnings, installs it
with `apt`, launches the installed `/usr/bin/saat` to confirm installed-mode path
resolution works through the symlink, and then removes *and purges* it while asserting a
planted collection under `~/.local/share/saat` survives both. That last assertion is not
a nicety — see `packaging/README.md`. Nothing in the packaging is built by hand; see
`packaging/` for the scripts and why they are shaped the way they are.

The same workflow also runs on `workflow_dispatch` as a dry run that builds and verifies
without publishing anything (step 5) — use it before spending a tag.

1. Write the release notes to `docs/release-notes/x.y.md` — user-facing changes only,
   not implementation detail. Must include: what changed, how to install (the `.deb` for
   Debian/Ubuntu, the tarball everywhere else), the compatibility statement (PySide6's
   manylinux wheel needs glibc 2.35+; building on `ubuntu-22.04` gives that floor, so the
   binary runs on anything with glibc 2.35 or newer — in practice Ubuntu 22.04+, Debian
   12+, Fedora 36+, Mint 21+, and current Arch), a line stating where data lives in each
   install mode, and — for any release that ships the package — the statement that
   removing or purging it never deletes the collection.

   Version numbers are whatever the milestone says. Two-numeral versions (`2.0`) and
   three-numeral ones (`1.8.2`) are both valid and both accepted by
   `tests/test_version.py`; the release-notes filename, the `CHANGELOG.md` heading, the
   tag and `__version__` just all have to agree.
2. Bump `__version__` in `saat/__init__.py` and add the matching `## [x.y.z]` entry to
   `CHANGELOG.md`, in the same commit as the release notes file above. Run
   `tests/test_version.py` to confirm `__version__` and the CHANGELOG heading agree (see
   Release discipline above).
3. Commit, following the repository's existing message convention (see recent `git log`
   for tone and structure).
4. Push to master, and confirm the Test workflow goes green on it before going further.
5. **Dry-run the release build before spending a tag.** Run the Release workflow manually
   — Actions → Release → "Run workflow" on `master`, or:
   ```
   gh workflow run release.yml --ref master
   ```
   `workflow_dispatch` runs everything a real release runs — both guards, the full test
   suite, the translation compile, the PyInstaller build and the headless smoke test —
   and then stops. It publishes nothing: the release job is gated on the tag-push event,
   so a manual run leaves the tarball as a downloadable workflow artifact and creates no
   tag and no release. Its artifact is labelled `vX.Y.Z-dev-<sha>` so it can never be
   confused with a released one.

   Do this whenever the change touches packaging at all — `SAAT.spec`, a bundled
   resource, the workflow itself, a dependency pin. A tag is a public, awkward-to-retract
   thing; a dry run is free and repeatable, so packaging problems should be found here,
   not by watching a tagged release fail.
6. Tag and push the tag:
   ```
   git tag -a vX.Y.Z -m "SAAT vX.Y.Z - <one-line summary>"
   git push origin vX.Y.Z
   ```
7. Watch the Release workflow run in the Actions tab. On a tag it does everything the dry
   run did, and then publishes: it creates the GitHub release as a **draft**, attaches
   every artifact each build job produced, and only then promotes the draft to published
   — so a second platform's build failing can never leave a half-populated release on the
   Releases page. Publishing is idempotent (the release is created only if absent, and
   assets upload with `--clobber`), so re-running the same tag replaces a bad binary
   rather than failing on it.

   If it still fails and the fix needs a new commit, **delete the release and the tag
   together, in that order**:
   ```
   gh release delete vX.Y.Z --cleanup-tag --yes
   git fetch --prune --prune-tags
   git tag -l vX.Y.Z          # must print nothing
   ```
   The order is the point. `--cleanup-tag` removes the tag *after* the release it belongs
   to; deleting the tag first — the old `git push --delete origin vX.Y.Z` on its own —
   leaves the release behind, orphaned against a ref that no longer exists, still on the
   Releases page and still serving whatever binary it was built from. That stale release
   is also what makes a plain re-tag fail: `gh release create` refuses a release that
   already exists.

   Then fix it on master and repeat from step 5 — re-pushing an unchanged tag just
   rebuilds the same broken commit.
8. Report back: the commit SHA(s), the tag, and the release URL.

## Local builds (development only)

`.venv/bin/pyinstaller SAAT.spec` (see README's "Build a portable version") still works
locally and is useful for testing a `SAAT.spec` change or a new bundled resource before
tagging — a free local iteration instead of spending a tag/wait-for-CI/delete-tag cycle on
what's really a spec-content problem. It is development tooling only now: an actual
release is never built or published by hand anymore — `git tag` + `git push` is the
entire release action on the source side, and `.github/workflows/release.yml` is the only
path to a published release, gated on the full test suite and a headless smoke test that
neither a by-hand build nor the old checklist ever enforced.
