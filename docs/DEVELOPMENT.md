# Development

Working notes for building SAAT. SPEC.md is authoritative on behavior and design —
this document covers process: how a milestone lands, and how a release ships.

## Release discipline

Every milestone bumps `__version__` in `saat/__init__.py` and adds its entry to
`CHANGELOG.md`, in the same commit. `tests/test_version.py` enforces this: the test
suite fails if `__version__` doesn't match the most recent version heading in
`CHANGELOG.md`.

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
5. Build the portable tarball:
   ```
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
