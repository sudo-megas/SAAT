# Packaging

How SAAT becomes a `.deb`, and why it is built this way. The scripts here are
driven by `.github/workflows/release.yml`; nothing in a real release is run by
hand.

## What the package contains

The `.deb` ships **the PyInstaller one-folder build** — the same `dist/SAAT`
tree the portable tarball is made from, dropped into `/usr/lib/saat`. It
carries its own Qt, its own Python interpreter and its own copy of every
Python dependency, so it needs almost nothing from the system beyond the C
library and the handful of X11/Wayland/GL libraries Qt's platform plugins
dlopen at runtime.

**One build, two artifacts.** The `deb` job in the release workflow does not
build anything itself: it downloads the tarball the `build-linux-x86_64` job
produced, unpacks it, and wraps it. The tarball and the `.deb` are therefore
byte-identical inside, and cannot drift apart between one release and the
next.

## Why not repackage against Debian's `python3-pyside6`

Debian ships PySide6, and a "proper" Debian package would depend on it rather
than bundling a second copy of Qt. That was considered and rejected:

- It means a **second build to test**. The bundled build is the one the
  tarball, the CI smoke test and every manual verification already exercise.
  A system-Qt build is a different binary against a different Qt point
  release, with its own failure modes, and would have to be tested separately
  on every distribution that ships a different PySide6 version.
- The versions genuinely differ. `requirements.txt` pins PySide6 exactly, on
  purpose — one tag produces more than one platform artifact, and unpinned
  means two of them could be built against different Qt versions while
  claiming the same version number. Depending on `python3-pyside6` throws that
  guarantee away and hands the app's behaviour to whatever Debian, Ubuntu,
  Mint and their derivatives each happen to ship.
- The benefit is disk space and a shared security-update path for Qt. Both are
  real, and neither is worth a second differently-behaving build for a
  single-maintainer hobby project with one user.

The cost is paid in size and is stated plainly in the package description
rather than buried: the installed package is a few hundred megabytes, almost
all of it Qt.

## Why `dpkg-deb` rather than `debhelper`

The payload is a **prebuilt binary tree**, not a source package. `debhelper`'s
`dh` sequencer exists to drive a build system — configure, make, make install
— and to derive packaging facts from the sources it just built. Given a tree
that already exists, most of the sequence has to be actively neutralised
rather than used:

- `dh_shlibdeps` would walk the bundled Qt libraries and generate a `Depends`
  line naming Debian's own `libqt6*` packages, which is precisely wrong here —
  the bundle must not resolve Qt from the system. The dependency list is
  instead derived by scanning only for libraries the bundle does *not* carry
  (see `audit-bundle.py`).
- `dh_strip`, `dh_dwz` and `dh_strip_nondeterminism` all want to rewrite the
  shipped binaries. Rewriting PyInstaller's bundled `.so` files invalidates
  the bundle's own integrity assumptions for no gain.
- `dh_install`, `dh_installdocs`, `dh_installchangelogs` and friends reduce to
  a handful of `install` and `cp` calls once there is nothing to build.

What is left is: compose a tree, write a `DEBIAN/` directory, run `dpkg-deb`.
That is what `build-deb.sh` does, in about a hundred readable lines, with no
`debian/rules` and no build-system indirection between the input and the
output. The result is the same binary package format either way — `debhelper`
is a convenience for source packages, not a requirement of the format.

## `audit-bundle.py`

The one part of this that is not simple file copying. It walks every ELF
object in the staged tree and refuses to let the build continue unless three
claims hold, each of which would otherwise be a fact somebody remembered:

- **The `Depends` line is complete.** Every `DT_NEEDED` soname the bundle
  does not carry itself is either mapped to a package named in `Depends`, or
  listed as a deliberate exclusion with a reason. A soname in neither table
  fails the build — nothing gets to be silently missing.
- **`libc6 (>= 2.35)` is measured.** The highest `GLIBC_x.y` symbol version
  referenced anywhere in the bundle is compared against that floor. Building
  on a newer runner than `ubuntu-22.04` fails here rather than shipping a
  package that will not start on the distributions the release notes
  promise.
- **`debian/copyright` covers everything shipped.** Each bundled shared
  object is glob-matched against the copyright's own `Files:` stanzas. If
  PyInstaller starts bundling a library nobody accounted for, the build stops
  until it is licensed properly.

It also writes `/usr/share/doc/saat/bundled-libraries.txt` — every shared
object shipped, with its SONAME — from the actual package contents, so what
is claimed and what is inside cannot drift.

## Layout

```
/usr/lib/saat/                              the one-folder build
/usr/lib/saat/SAAT                          the executable
/usr/lib/saat/_internal/                    bundled Qt and Python
/usr/lib/saat/.installed                    installed-mode marker
/usr/bin/saat                               symlink -> ../lib/saat/SAAT
/usr/share/applications/saat.desktop        launcher entry (shared with install.sh)
/usr/share/icons/hicolor/256x256/apps/saat.png
/usr/share/man/man1/saat.1.gz
/usr/share/doc/saat/copyright               DEP-5
/usr/share/doc/saat/changelog.Debian.gz     packaging changelog
/usr/share/doc/saat/changelog.gz            upstream CHANGELOG.md
/usr/share/lintian/overrides/saat
```

### The `.installed` marker is shipped, not written by `postinst`

SPEC.md §2's opt-in rule needs a `.installed` file beside the executable for
the app to use `~/.local/share/saat` and `~/.config/saat` instead of its own
directory. `install.sh` `touch`es it; the `.deb` **ships it as a package
file** instead of creating it in `postinst`.

That is deliberate. A file a maintainer script creates is not in dpkg's file
list, so dpkg would leave it behind on removal, and the now-empty
`/usr/lib/saat` with it. Shipping the marker means dpkg owns it, verifies it,
and removes it cleanly — and `dpkg -V saat` can tell you it is still there.

### `/usr/bin/saat` is a symlink, and that is load-bearing

`paths.py` resolves installed mode from `Path(sys.executable).resolve().parent`.
Two things have to hold for a symlinked entry point:

1. PyInstaller's bootloader must find `_internal/` relative to the *real*
   executable, not the symlink. On Linux it reads `/proc/self/exe`, which the
   kernel has already resolved, so it does.
2. `.resolve()` follows symlinks, so even if the bootloader reported the
   symlink path instead, `/usr/bin/saat` still resolves to
   `/usr/lib/saat/SAAT` and the marker is still found beside it.

Both are belt and braces for the same outcome, and the outcome is asserted for
real — not reasoned about — by the CI smoke test, which launches
`/usr/bin/saat` from an actually-installed package and confirms it starts.

## Data safety

**Removing or purging the package never deletes a collection.** The package
owns nothing under `$HOME`: `watches/`, `backups/` and `config.toml` live in
`~/.local/share/saat` and `~/.config/saat`, which no maintainer script here
writes to or removes. This mirrors `uninstall.sh`'s own promise, and it is
asserted automatically in CI — the `deb` job plants a file in a fake
`~/.local/share/saat`, purges the package, and fails if the file is gone.

One deliberate divergence from `uninstall.sh`: it removes the XDG autostart
entry a user may have enabled from the tray menu, and the maintainer scripts
here do **not**. Debian policy forbids maintainer scripts from touching files
under `/home` — they run as root, and there is no reliable way to know which
user's home to reach into. A leftover `~/.config/autostart/saat.desktop` is
inert once the binary it names is gone, and the tray menu will report
autostart as enabled again the moment the package is reinstalled, which is
the honest reading of "does the entry exist".
