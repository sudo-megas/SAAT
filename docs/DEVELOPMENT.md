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

Run this before `pyinstaller SAAT.spec` (step 5 below) every time — the
`.spec`'s `datas` entry copies whatever's already in `saat/resources/i18n/`
at build time, so a stale or missing `.qm` ships silently otherwise
(SAAT falls back to English, which "looks almost right" rather than
failing loudly). Qt's own dialog-chrome strings (`QMessageBox`/
`QFileDialog`/`QDialogButtonBox` button labels) come from a *second*,
separate translation file, `qtbase_tr.qm`, which ships inside the PySide6
wheel itself, not this repo — nothing to regenerate here, and PyInstaller's
PySide6 hook bundles it into the frozen build automatically (`QtCore` is
always a transitive dependency, and it's always registered for `qtbase`
translations).

## Release checklist

Standing procedure for every milestone, once its feature work and tests are green.
Later milestones can just say "follow the release checklist."

1. Bump `__version__` in `saat/__init__.py` and add the matching `## [x.y.z]` entry to
   `CHANGELOG.md`, in the same commit. Run `tests/test_version.py` to confirm they
   match (see Release discipline above).
2. Commit, following the repository's existing message convention (see recent
   `git log` for tone and structure).
3. Push to master.
4. Tag and push the tag:
   ```
   git tag -a vX.Y.Z -m "SAAT vX.Y.Z - <one-line summary>"
   git push origin vX.Y.Z
   ```
5. Compile `saat_tr.qm` first (see Localisation above) — `pyinstaller`
   bundles whatever's already on disk, silently, so a stale translation
   ships if this is skipped. Then build the portable tarball:
   ```
   .venv/bin/pyside6-lrelease saat/resources/i18n/saat_tr.ts -qm saat/resources/i18n/saat_tr.qm
   .venv/bin/pyinstaller SAAT.spec
   cd dist && tar -czf SAAT-vX.Y.Z-linux-x86_64.tar.gz SAAT && cd ..
   ```
   Then verify it: extract the tarball to a fresh path under `/tmp`, run the binary
   from there, and confirm the window title reads the new version. Do not skip this
   — it is the only check that the shipped artifact matches the tagged source.
6. Write release notes to a temporary file — user-facing changes only, not
   implementation detail — then:
   ```
   gh release create vX.Y.Z \
     --title "SAAT vX.Y.Z - <one-line summary>" \
     --notes-file <that file> \
     dist/SAAT-vX.Y.Z-linux-x86_64.tar.gz
   ```
   Notes must include: what changed, the download-and-extract instruction, the
   standing caveat that the build is produced on Arch and may not run on older
   distributions, and a line stating data lives beside the executable.
7. Report back: the commit SHA(s), the tag, and the release URL.
