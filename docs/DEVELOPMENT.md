# Development

Working notes for building SAAT. SPEC.md is authoritative on behavior and design —
this document covers process: how a milestone lands, and how a release ships.

## Release discipline

Every milestone bumps `__version__` in `saat/__init__.py` and adds its entry to
`CHANGELOG.md`, in the same commit. `tests/test_version.py` enforces this: the test
suite fails if `__version__` doesn't match the most recent version heading in
`CHANGELOG.md`.

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

1. Write the release notes to `docs/release-notes/x.y.z.md` — user-facing changes only,
   not implementation detail. Must include: what changed, the download-and-extract
   instructions, the compatibility statement (PySide6's manylinux wheel needs glibc 2.35+;
   building on `ubuntu-22.04` gives that floor, so the binary runs on anything with glibc
   2.35 or newer — in practice Ubuntu 22.04+, Debian 12+, Fedora 36+, Mint 21+, and current
   Arch), and a line stating data lives beside the executable.
2. Bump `__version__` in `saat/__init__.py` and add the matching `## [x.y.z]` entry to
   `CHANGELOG.md`, in the same commit as the release notes file above. Run
   `tests/test_version.py` to confirm `__version__` and the CHANGELOG heading agree (see
   Release discipline above).
3. Commit, following the repository's existing message convention (see recent `git log`
   for tone and structure).
4. Push to master.
5. Tag and push the tag:
   ```
   git tag -a vX.Y.Z -m "SAAT vX.Y.Z - <one-line summary>"
   git push origin vX.Y.Z
   ```
6. Watch the Release workflow run in the Actions tab: it re-runs the full test suite as a
   gate, checks the tag matches `__version__`, compiles the Turkish translation, builds
   the portable tarball on `ubuntu-22.04` (see the workflow file's own comment for why
   that runner specifically), smoke-tests the built binary headless, and — only once
   every prior step has succeeded — publishes the GitHub release using the notes file
   from step 1. If a step fails, fix it on master and replace the tag rather than
   reusing it:
   ```
   git push --delete origin vX.Y.Z && git tag -d vX.Y.Z
   ```
   then repeat step 5 — re-pushing an unchanged tag just rebuilds the same broken commit.
7. Report back: the commit SHA(s), the tag, and the release URL.

## Local builds (development only)

`.venv/bin/pyinstaller SAAT.spec` (see README's "Build a portable version") still works
locally and is useful for testing a `SAAT.spec` change or a new bundled resource before
tagging — a free local iteration instead of spending a tag/wait-for-CI/delete-tag cycle on
what's really a spec-content problem. It is development tooling only now: an actual
release is never built or published by hand anymore — `git tag` + `git push` is the
entire release action on the source side, and `.github/workflows/release.yml` is the only
path to a published release, gated on the full test suite and a headless smoke test that
neither a by-hand build nor the old checklist ever enforced.
