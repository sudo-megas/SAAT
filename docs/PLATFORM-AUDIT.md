# Platform audit — every Linux assumption in SAAT

Milestone 24 commit A. **This document changes no behaviour.** It is the
inventory the rest of milestone 24 is scoped against, so that the commits which
follow are aimed at something real rather than at a guess about what a
cross-platform port involves.

Every entry carries a file and a line. The line numbers are as of the commit
that adds this file; they will drift as the following commits fix things, and
that is fine — the point of writing them down is that the work was found by
reading the code, not by recalling it.

Findings were produced by reading each area against a specific question, then
**re-checked against the source a second time** before landing here: 230
confirmed as written, 59 corrected, 6 rejected outright as plausible-sounding
claims the code did not actually support. Corrected entries are marked. The
corrections mattered — several things that read like outright failures are
merely wrong-but-working, and saying so is the difference between a plan and a
panic.

## The shape of the problem

SAAT is 10,000-odd lines of Python across 60 modules and 57 test files, and the
damage is not evenly spread. Two modules carry almost all of it:

- **`saat/paths.py`** — 60 lines, and every writable path in the application
  funnels through it. Its installed-mode branch is purely XDG: an environment
  variable name plus a `~`-relative default.
- **`saat/autostart.py`** — 76 lines, and *all* of it is the freedesktop
  Desktop Entry mechanism. There is no abstraction to extend; the whole module
  is one platform's answer.

Against that, three things came out better than expected, and they shape how
much of the rest is real work:

- **Nothing in `saat/` shells out.** No `subprocess`, no `os.system`, no
  `QProcess`, anywhere in the application. The five bash scripts in the
  repository are developer and Linux-installer tooling only; no Windows user
  ever executes one, so they need no port — only a Windows equivalent for the
  jobs they do (`run.sh` for developers, an installer for users).
- **Every path is composed with `pathlib`.** There is not one hardcoded `/`
  used as a separator in application code. The forward slashes that exist are
  URLs, Qt resource paths and QSS.
- **`SAAT.spec` is already nearly portable.** It uses the tuple form of
  `datas`, so there is no `:` versus `;` separator problem, it already sets
  `console=False`, and it already points at a real multi-resolution `.ico`.

## What the verification pass changed

Worth recording, because it is the difference between the port being risky and
being tractable. The path layer was first reported as outright breaking on
Windows. It is not: `Path.home()` resolves through `%USERPROFILE%`, and
`C:\Users\<name>\.local\share\saat` is a perfectly writable directory. An
installed Windows build today would **run correctly** and simply keep the
collection somewhere no Windows user would think to look, un-roamed and
un-backed-up. That is a must-fix, and it is a wrong-location defect rather than
a functional failure.

The one place this genuinely does break is conditional on commit D: if the
Windows installer fails to write the `.installed` marker, the app falls into
portable mode under `C:\Program Files`, and the failure surfaces not at
startup but at the *first write*. That makes the installer's marker step
load-bearing rather than incidental.

## Severity

- **breaks** — SAAT will not work correctly on Windows until this changes.
- **degrades** — works, but wrongly or fragilely; worth fixing, not fatal.

Findings at *none* and *cosmetic* — checked and found already portable, or
cosmetic only — are not listed individually; there were 163 of them, and the
three bullets above are their summary.

## Inventory

92 items across 28 files: 55 breaking, 37 degrading.


#### `saat/paths.py`
- [ ] `:18` — degrades — Installed mode requires `sys.frozen` AND a `.installed` marker beside the executable. Two corrections: line is 18, not 14; and "only install.sh creates it" is inaccurate — packaging/stage-tree.sh:54 also writes it for the .deb, and the current docstring (lines 11-15) explicitly names "the Windows installer" as a third writer. The real, narrower finding is that no Windows installer exists yet (M24d pending), so today every Windows build resolves data_dir() to _portable_dir(). *(corrected in verification)*
- [ ] `:31` — **breaks** — The single point where the XDG env var and the home-relative fallback are composed; both halves are POSIX conventions.
- [ ] `:34` — degrades — Any frozen build without the .installed marker resolves its data directory to the executable's own folder, and line 35 mkdir()s it. *(corrected in verification)*
- [ ] `:42` — **breaks** — data_dir()'s installed-mode fallback is the XDG Base Directory default ~/.local/share, a Linux-only convention.
- [ ] `:48` — **breaks** — config_dir()'s installed-mode fallback is ~/.config, the XDG config default.

#### `saat/storage.py`
- [ ] `:26` — degrades — The slug sanitiser is a single negated character class: `[^a-z0-9]+`. It is purely character-level and has no notion of names that are legal character-by-character yet forbidden as a whole — Windows' reserved DOS device names. *(corrected in verification)*
- [ ] `:55` — **breaks** — unique_slug decides "is this slug free?" with `base not in existing`, plain Python set membership, which is byte-exact and therefore case-sensitive — the same assumption ext4 makes. *(corrected in verification)*
- [ ] `:58` — degrades — The disambiguation loop that appends -2/-3 probes with the same exact-case `in existing` membership test as line 55.
- [ ] `:204` — **breaks** — create_watch builds the `existing` set from raw on-disk directory names (`p.name`) with no case folding, then hands it to the case-sensitive check on line 55.
- [ ] `:219` — **breaks** — save_watch creates the watch folder with `exist_ok=True`, relying on unique_slug having already guaranteed the name is unused.
- [ ] `:228` — **breaks** — The hottest write_atomic call site -- every watch edit, wear toggle and status change -- inheriting atomic.py:13's unretried replace.
- [ ] `:242` — **breaks** — delete_watch moves the whole watch directory (watch.toml, images/, images/.thumbnails/) in one call. *(corrected in verification)*
- [ ] `:257` — degrades — The pre-write backup reads the live watch.toml with no retry and copies its mode bits. *(corrected in verification)*
- [ ] `:268` — **breaks** — Backup rotation deletes the oldest files with a bare unlink -- no missing_ok, no PermissionError handling.

#### `saat/atomic.py`
- [ ] `:8` — degrades — Fixed sibling temp name with no try/finally around write+replace, so any failure strands the .tmp permanently.
- [ ] `:13` — **breaks** — The rename-into-place is attempted exactly once, with no retry and no error handling.

#### `saat/autostart.py`
- [ ] `:11` — **breaks** — Hardcodes the FHS system-wide XDG applications directory as the source file that enable() copies from.
- [ ] `:13` — **breaks** — Names the artifact type: a freedesktop.org .desktop entry.
- [ ] `:29` — **breaks** — Resolves the autostart parent directory from XDG_CONFIG_HOME, falling back to ~/.config.
- [ ] `:30` — **breaks** — Appends the literal XDG subdirectory name 'autostart'.
- [ ] `:34` — **breaks** — Single choke point composing the target path; is_enabled(), enable() and disable() all route through it.
- [ ] `:48` — **breaks** — is_enabled() decides the feature's on/off state purely by stat()ing the .desktop path — exactly what the tray menu's 'Start at login' item reads for its checked state (saat/ui/tray.py:171).
- [ ] `:55` — **breaks** — _with_autostart_flag() parses the source file as INI-style Desktop Entry text and appends --autostart to the Exec= key.
- [ ] `:64` — **breaks** — enable() refuses to proceed unless the /usr/share/applications source file is present.
- [ ] `:68` — **breaks** — Reads the launcher entry as UTF-8 text so it can be re-emitted verbatim (the 'reuse, do not compose a second file' rule stated in the module docstring at lines 7-10).
- [ ] `:71` — **breaks** — Registers autostart by writing a text file into the autostart directory.
- [ ] `:75` — degrades — disable() deletes the .desktop entry; missing_ok=True makes a missing file a silent no-op.

#### `saat/single_instance.py`
- [ ] `:66` — degrades — When the post-removeServer retry of listen() also fails, the guard prints a warning to stderr and returns True — deliberately failing open and running without single-instance enforcement. Verified verbatim at line 66; the code is unmodified in the working tree.

#### `saat/config.py`
- [ ] `:28` — degrades — The config save inherits atomic.py:13's unretried replace.

#### `saat/sellers.py`
- [ ] `:69` — degrades — Third write_atomic call site with no retry, preceded by a backup that reuses storage.backup_watch_toml.

#### `saat/wear.py`
- [ ] `:38` — degrades — One calendar gesture writes N watch.toml files in a bare loop with no rollback.

#### `saat/image_import.py`
- [ ] `:21` — degrades — Copies the chosen photo straight to its final name, no temp file, and preserves the source's mode bits.
- [ ] `:26` — degrades — missing_ok=True covers absence but nothing covers undeletability.
- [ ] `:37` — degrades — The thumbnail derivative is written straight to its final path, with no temp+replace. *(corrected in verification)*

#### `saat/ui/images_tab.py`
- [ ] `:110` — degrades — ImagesTab._unique_filename de-duplicates staged image filenames with `if name not in existing` against a Python set of names — exact-case membership, the same Linux assumption as unique_slug.

#### `saat/ui/main_window.py`
- [ ] `:110` — **breaks** — The tray menu's "Start at login" item is gated on saat/autostart.py, which is an XDG-only implementation (reads /usr/share/applications/saat.desktop, writes $XDG_CONFIG_HOME/autostart/saat.desktop).
- [ ] `:576` — degrades — "Start minimised" requires started_via_autostart, which main.py derives from the --autostart flag appended to the Exec= line of the XDG .desktop file by autostart.enable().

#### `saat/ui/sidebar.py`
- [ ] `:132` — degrades — The sidebar's fallback Language button is the no-tray path for language switching and is hidden whenever a tray exists, on the Linux assumption that a present tray icon is a visible tray icon.

#### `SAAT.spec`
- [ ] `:81` — degrades — The EXE() call closes at line 81 with no `version=` argument (verified: the string "version" does not appear anywhere in SAAT.spec), so PyInstaller embeds no Windows VERSIONINFO resource. *(corrected in verification)*

#### `.gitattributes`
- [ ] `:1` — degrades — No `.gitattributes` is tracked in the repository (`git ls-files` has no match; `git cat-file -p HEAD:.gitattributes` fails), so the project declares no line-ending normalization policy. CORRECTED: an untracked `.gitattributes` does exist in this worktree on disk (created after HEAD commit 060349f by concurrent work in this session, timestamped 01:37) -- it is not in HEAD or the index, so it affects no other clone, but a fix must `git add` it rather than assume the path is free. *(corrected in verification)*

#### `.github/workflows/test.yml`
- [ ] `:22` — degrades — The English ambient locale the i18n tests depend on is forced by setting the POSIX environment variables LANG and LC_ALL (line 23), with the rationale at lines 17-21. release.yml repeats it at lines 53-54.
- [ ] `:27` — degrades — The single `test` job is hard-pinned to `ubuntu-22.04` with no `strategy.matrix` (verified: no `strategy:`/`matrix:` key anywhere under .github/workflows/), so the automated suite has never been executed on Windows. *(corrected in verification)*
- [ ] `:47` — **breaks** — No `shell:` is declared on any step in either workflow and no workflow-level `defaults: run: shell: bash` exists (verified: `grep -rn 'shell:|defaults:' .github/workflows/` returns nothing), so every `run: |` block relies on the runner default. *(corrected in verification)*
- [ ] `:49` — **breaks** — System Qt dependencies are installed with `sudo apt-get install` (update at line 48), naming Debian package names (libegl1, libgl1, libxkbcommon0, libxcb1, libx11-6, libfontconfig1, libfreetype6, libglib2.0-0, libdbus-1-3).
- [ ] `:63` — **breaks** — The plugin-verification step hardcodes both the `Qt` path segment and the `.so` extension when locating the offscreen QPA plugin inside the PySide6 wheel.
- [ ] `:64` — **breaks** — Shared-library resolution is verified with `ldd`, grepping its output for the literal string "not found".

#### `.github/workflows/release.yml`
- [ ] `:67` — **breaks** — The only artifact-producing build job, `build-linux-x86_64`, runs on `ubuntu-22.04`; so do `deb` (line 201) and `release` (line 371). There is no Windows build job anywhere in the file.
- [ ] `:91` — **breaks** — The dry-run build label is composed with `${GITHUB_SHA::7}`, a bash substring expansion, written to `$GITHUB_OUTPUT` via `>>`.
- [ ] `:118` — **breaks** — The release build installs Linux system libraries with `sudo apt-get` (update at line 117), naming Debian package names, exactly as test.yml does.
- [ ] `:146` — **breaks** — The distributable is produced by `tar -czf ...-linux-x86_64.tar.gz`, preceded by a bare `cd dist` (line 145) inside the run block, and the artifact name/path repeat that string at lines 189-190. *(corrected in verification)*
- [ ] `:160` — **breaks** — The smoke test extracts into the absolute path `/tmp/smoke` and later writes `/tmp/smoke.log` (line 168, read again at 176, 181, 183).
- [ ] `:165` — **breaks** — The bundle assertion hardcodes the Linux plugin path and filename: `_internal/PySide6/Qt/plugins/iconengines/libqsvgicon.so` (verified present at that exact path in the local dist/ tree).
- [ ] `:168` — **breaks** — The launch test invokes GNU coreutils `timeout --kill-after=5s 15s` against the executable at path `/tmp/smoke/SAAT/SAAT` -- no `.exe` suffix. The deb job repeats the pattern at line 291.
- [ ] `:173` — **breaks** — The healthy-launch exit codes are `0|124|137|143` -- coreutils' timeout sentinel plus 128+SIGKILL and 128+SIGTERM (same case block repeated at line 295 in the deb job).

#### `run.sh`
- [ ] `:1` — degrades — Developer bootstrap script written for bash with a POSIX shebang.
- [ ] `:3` — degrades — Uses the bash-only BASH_SOURCE array plus dirname to locate the repo root.
- [ ] `:6` — degrades — Invokes the interpreter as python3.
- [ ] `:9` — degrades — Hard-codes the POSIX venv layout, .venv/bin/.
- [ ] `:15` — degrades — The dev launcher unconditionally pins Qt's platform plugin to `wayland` before exec'ing main.py, with no session detection and no `${QT_QPA_PLATFORM:-wayland}` escape hatch. Verified: it is the only line in the repo that forces a non-offscreen backend. *(corrected in verification)*
- [ ] `:16` — degrades — Uses the POSIX exec builtin to replace the shell process, plus the bin/ venv path again.

#### `install.sh`
- [ ] `:14` — degrades — Gates the whole install on the effective UID being 0 (root).
- [ ] `:27` — degrades — Installs the payload to /opt, the FHS location for add-on application packages.
- [ ] `:28` — **breaks** — The marker that flips the app from portable to installed mode is written only by the Linux installers (mirrored at packaging/stage-tree.sh:54 for the .deb).
- [ ] `:31` — degrades — Puts the app on PATH by symlinking into /usr/local/bin.
- [ ] `:46` — **breaks** — The only producer of the source file autostart.enable() reads — a bash script using install(1), requiring root, targeting FHS.

#### `uninstall.sh`
- [ ] `:13` — degrades — Same root/EUID gate as install.sh, for the removal path.
- [ ] `:32` — **breaks** — Resolves the invoking (non-root) user's home via SUDO_USER plus getent passwd, because $HOME under sudo is root's.
- [ ] `:39` — **breaks** — Uninstall removes the user's XDG autostart entry — the one OS-integration artifact the install caused.
- [ ] `:51` — degrades — Deletes the install prefix.

#### `packaging/stage-tree.sh`
- [ ] `:70` — **breaks** — The .deb staging tree places the same launcher entry at the same FHS path, keeping the packaged install consistent with the scripted one.

#### `docs/BUILDING.md`
- [ ] `:39` — degrades — The documented test invocation uses the POSIX `VAR=value command` inline-environment prefix. Confirmed at line 39, under '## Run the tests' at line 36.

#### `tests/test_autostart.py`
- [ ] `:34` — **breaks** — AutostartTestCase uses the same $HOME-only isolation and asserts a ~/.config/autostart location (lines 82 and 91).
- [ ] `:82` — **breaks** — Asserts the XDG layout as the one correct answer for the autostart path.
- [ ] `:91` — **breaks** — Asserts the XDG empty-string-means-unset rule for XDG_CONFIG_HOME falls back to $HOME/.config/autostart.
- [ ] `:142` — **breaks** — Precondition assertion that the autostart directory does not yet exist, relying on it living inside this test's private tmp HOME. *(corrected in verification)*

#### `tests/test_i18n.py`
- [ ] `:20` — degrades — _find_lrelease() prefers the interpreter's own venv by hardcoding the POSIX venv layout: <prefix>/bin/<name>, no extension.
- [ ] `:146` — **breaks** — Asserts Qt applies Turkish-specific casing (i -> dotted İ), which QLocale::toUpper only does when Qt is compiled with ICU.

#### `tests/test_packaging.py`
- [ ] `:70` — degrades — Checked whether the test suite executes any of the shell scripts: it does not — the packaging tests assert against the scripts' source text via read_text. *(corrected in verification)*
- [ ] `:88` — **breaks** — Pins autostart.INSTALLED_DESKTOP_PATH to the exact POSIX string, cross-checking that install.sh and stage-tree.sh write to the path autostart.py reads.
- [ ] `:147` — **breaks** — test_scripts_are_executable (line 145) applies the same S_IXUSR check on line 148 to packaging/stage-tree.sh.
- [ ] `:148` — **breaks** — Asserts packaging/stage-tree.sh carries the owner-execute permission bit.
- [ ] `:228` — **breaks** — Asserts the Debian maintainer scripts (postinst/prerm/postrm) carry the POSIX owner-execute bit.

#### `tests/test_paths.py`
- [ ] `:26` — **breaks** — PathsTestCase isolates the home directory by patching $HOME only.
- [ ] `:111` — **breaks** — XdgFallbackDefaultTests asserts the ~/.local/share and ~/.config layout as the only installed-mode answer (also line 112 and line 117).
- [ ] `:112` — **breaks** — Asserts the config fallback is $HOME/.config/saat. *(corrected in verification)*
- [ ] `:117` — **breaks** — Asserts the XDG empty-string-means-unset rule falls back to $HOME/.local/share. *(corrected in verification)*
- [ ] `:161` — **breaks** — SymlinkedEntryPointTests builds a real filesystem symlink to model the packaged /usr/bin/saat -> ../lib/saat/SAAT entry point.

#### `tests/test_retranslation.py`
- [ ] `:48` — degrades — A third copy of the same POSIX venv-layout lookup.
- [ ] `:125` — **breaks** — Asserts the table header renders MEKANİZMA with a dotted İ, produced by table_view.py's QLocale().toUpper() under a Turkish default locale.

#### `tests/test_single_instance.py`
- [ ] `:139` — **breaks** — The stale-socket recovery test fabricates a crash by binding a raw `socket.AF_UNIX` stream socket to the path Qt handed back from fullServerName(). Correction to the report: an AttributeError here errors only `test_stale_socket_left_by_a_crash_is_recovered`; the sibling test `test_clean_close_lets_a_new_guard_become_primary_without_recovery` (line 149) runs independently and is unaffected, so the class is not "taken down with it". *(corrected in verification)*
- [ ] `:143` — **breaks** — The same test treats `QLocalServer.fullServerName()` (captured at line 131) as a filesystem path and asserts the file exists. Correction: this is the second half of the finding above, inside the same test method — it is one skip decision, not two independent defects, and line 143 is never reached on Windows because line 139 raises first. *(corrected in verification)*

#### `tests/test_table_view.py`
- [ ] `:82` — degrades — A second, copy-pasted _find_lrelease() with the same POSIX venv-layout assumption.

## What this means for the commits that follow

**Commit B — paths and filesystem.** `saat/paths.py` gains a Windows branch;
`saat/storage.py` gains case-insensitive collision detection and reserved-name
sanitisation, both unconditionally on every platform so a collection stays
loadable in both directions; `saat/atomic.py` gains a retry and a `try/finally`
so a locked destination is survivable and a `.tmp` is never orphaned;
`.gitattributes` is added.

The case-sensitivity finding deserves restating, because it is the subtlest
thing in this list. `slugify()` lowercases, so *generated* slugs never collide
by case. The exposure is hand-authored folders: SPEC.md §3 explicitly supports
copying `_template.toml` into `watches/<some-slug>/watch.toml` by hand, and a
folder named `Seiko-SKX007` alongside a generated `seiko-skx007` is two
watches on ext4 and one on NTFS.

**Commit C — OS integration.** `saat/autostart.py` gains a Windows
implementation writing a Startup-folder shortcut, with `is_enabled()` still
meaning "does the entry exist" rather than a stored flag. The Wayland hint
leaves Windows alone. The tray needs nothing: detection is already a runtime
capability check that will simply always answer yes — and its Linux no-tray
fallback must not be deleted on that basis.

**Commit D — build and installer.** `SAAT.spec` gains a `version=` resource;
both CI workflows gain a `shell:` declaration and a platform matrix. Note that
`.github/workflows/release.yml`'s Linux smoke test is written in bash against
`/tmp` and coreutils `timeout` — the Windows job needs its own, not a
translation of that one. And per the note above, the installer writing
`.installed` is the difference between a working install and one that fails at
first save.

**Commit E — documentation.** SPEC.md §2 and §8, `docs/DEVELOPMENT.md`, and the
README's install section, which becomes three platforms.

## Two findings that are not portability problems

Recorded because they were found while looking for portability problems, and
because both are real:

- **`saat/storage.py`'s `_prune_backups`** treats every file in `backups/` as a
  backup, with no extension filter, and unlinks the oldest to hold the
  directory at 20. Anything else a user puts there is deleted. Nothing to do
  with Windows.
- **`saat/ui/pdf_renderer.py`'s failed-export cleanup** unlinks the PDF while
  the `QPdfWriter` that created it is still alive and in scope. On POSIX that
  is harmless, which is why it has never been noticed. It is listed under
  Windows because that is where it would surface, but the ordering is
  questionable on any platform.

Neither is fixed in milestone 24 — both are out of its scope, and inventing
scope is how a port stops shipping.
