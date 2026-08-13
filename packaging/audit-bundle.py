#!/usr/bin/env python3
"""Audits a staged SAAT tree before it is turned into a .deb.

Three things, all walking the same list of ELF objects under
/usr/lib/saat, all of which would otherwise be guesswork re-done by hand
every release:

  1. Writes the manifest of every bundled shared object with its SONAME,
     which ships as /usr/share/doc/saat/bundled-libraries.txt.
  2. Derives what the bundle actually needs from the *system* -- the
     DT_NEEDED sonames it does not carry itself -- and checks every one is
     either covered by the Depends line in debian/control.in or listed
     below as a deliberate exclusion. An unclassified soname fails the
     build rather than silently shipping a package that cannot start.
  3. Checks the highest glibc symbol version the bundle references against
     the floor the Depends line promises, so `libc6 (>= 2.35)` is a
     measured claim rather than a hopeful one.

Plus a licence-coverage check: every bundled library family must be named
somewhere in debian/copyright. That file is what makes the package legally
distributable, and PyInstaller decides what goes into the bundle from
whatever the build machine's wheels link against -- so the set can shift
under it without anyone noticing.

Run from build-deb.sh; also runnable by hand against a staged tree:

    ./packaging/audit-bundle.py --stage <dir>
"""

import argparse
import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

# --- what the bundle is allowed to want from the system -------------------
#
# soname -> the Debian package that provides it. Every one of these must
# appear in control.in's Depends, and the check below enforces that in the
# direction that matters: a soname the bundle needs, with no package named
# for it, is a package that fails to start on a clean machine.
REQUIRED = {
    "ld-linux-x86-64.so.2": "libc6",
    "libc.so.6": "libc6",
    "libdl.so.2": "libc6",
    "libm.so.6": "libc6",
    "libpthread.so.0": "libc6",
    "libresolv.so.2": "libc6",
    "librt.so.1": "libc6",
    "libutil.so.1": "libc6",
    "libnsl.so.1": "libc6",
    "libanl.so.1": "libc6",
    "libEGL.so.1": "libegl1",
    "libGL.so.1": "libgl1",
    "libGLX.so.0": "libgl1",
    "libGLdispatch.so.0": "libgl1",
    "libOpenGL.so.0": "libgl1",
    "libwayland-client.so.0": "libwayland-client0",
    "libwayland-cursor.so.0": "libwayland-cursor0",
    "libwayland-egl.so.1": "libwayland-egl1",
    "libwayland-server.so.0": "libwayland-server0",
    # The xcb platform plugin's own dependencies. PyInstaller bundles most
    # of the xcb stack but not these -- which build machine it runs on
    # decides that, so it is scanned rather than assumed. All are needed by
    # libQt6XcbQpa.so.6, which IS how the app puts a window on an X11
    # session: without them the plugin fails to load and SAAT does not
    # start at all.
    "libxcb.so.1": "libxcb1",
    "libxcb-cursor.so.0": "libxcb-cursor0",
    "libxcb-icccm.so.4": "libxcb-icccm4",
    "libxcb-image.so.0": "libxcb-image0",
    "libxcb-keysyms.so.1": "libxcb-keysyms1",
    "libxcb-randr.so.0": "libx11-xcb1",
    "libxcb-render-util.so.0": "libxcb-render-util0",
    "libxcb-render.so.0": "libxcb-render0",
    "libxcb-shape.so.0": "libxcb-shape0",
    "libxcb-shm.so.0": "libxcb-shm0",
    "libxcb-sync.so.1": "libxcb-sync1",
    "libxcb-util.so.1": "libxcb-util1",
    "libxcb-xfixes.so.0": "libxcb-xfixes0",
    "libxcb-xkb.so.1": "libxcb-xkb1",
    "libxkbcommon.so.0": "libxkbcommon0",
    "libxkbcommon-x11.so.0": "libxkbcommon-x11-0",
    "libX11.so.6": "libx11-6",
    "libX11-xcb.so.1": "libx11-xcb1",
}

# Sonames the bundle references but which are deliberately NOT depended on.
#
# The line between this table and the one above is not "is it in DT_NEEDED"
# -- everything here is -- it is whether its absence stops SAAT working on
# the desktops this package targets. Each of these is needed only by a Qt
# plugin that a normal X11 or Wayland session never loads, so a machine
# without it runs SAAT perfectly; Qt simply skips the plugin. Depending on
# them anyway would inflate the dependency list for backends nobody here
# uses, and in libtiff's case would make the package outright
# uninstallable.
#
# libxcb1 and the libwayland-* trio sit in REQUIRED rather than here for
# the opposite reason: one of those two stacks *is* how the app puts a
# window on screen. Depending on both is the cheap way to guarantee the
# package installs on a machine where it will actually run, whichever
# session type that machine uses.
OPTIONAL = {
    "libdrm.so.2": (
        "eglfs KMS/DRM platform integration -- an embedded/no-desktop backend "
        "SAAT never selects on X11 or Wayland"
    ),
    "libgbm.so.1": ("same eglfs KMS/DRM backend as libdrm"),
    "libtiff.so.5": (
        "Qt's TIFF image-format plugin, which SAAT never uses (Pillow decodes "
        "every image it loads). Depending on it would ALSO break the package: "
        "Ubuntu 22.04 ships this soname as libtiff5, Debian 12 and Ubuntu "
        "24.04+ ship libtiff.so.6 instead, so a libtiff5 dependency would make "
        "the .deb uninstallable on every current Debian"
    ),
    "libcups.so.2": (
        "Qt print support, dlopened on demand. SAAT's only document output is "
        "a PDF written through QPdfWriter, which does not go through CUPS"
    ),
    # Qt's GTK3 platform-theme plugin (platformthemes/libqgtk3.so), dlopened
    # only when QT_QPA_PLATFORMTHEME=gtk3 is set. SAAT never sets it, so a
    # machine without a GTK3 desktop stack runs SAAT exactly as it would with
    # one -- Qt silently skips the plugin, the same reasoning as libtiff and
    # libcups above. This masked itself on Ubuntu CI runners, which happen to
    # have the whole GTK3/X11 stack pre-installed regardless of Depends; the
    # Arch container that builds the .pkg.tar.zst has none of it, which is
    # what surfaced this whole group. Everything from libgdk-3 down is pulled
    # in only transitively through this one plugin.
    "libgtk-3.so.0": "GTK3 platform-theme plugin, see the comment above",
    "libgdk-3.so.0": "same GTK3 theme plugin",
    "libgdk_pixbuf-2.0.so.0": "same GTK3 theme plugin",
    "libatk-1.0.so.0": "same GTK3 theme plugin",
    "libatk-bridge-2.0.so.0": "same GTK3 theme plugin, via libgtk-3",
    "libatspi.so.0": "accessibility bus client, pulled in by libatk-bridge-2.0",
    "libcairo.so.2": "same GTK3 theme plugin",
    "libcairo-gobject.so.2": "same GTK3 theme plugin",
    "libpango-1.0.so.0": "same GTK3 theme plugin",
    "libpangocairo-1.0.so.0": "same GTK3 theme plugin",
    "libpangoft2-1.0.so.0": "pulled in by libgtk-3, same GTK3 theme plugin",
    "libharfbuzz.so.0": "text shaping, pulled in by libpango-1.0",
    "libgraphite2.so.3": "font-shaping backend, pulled in by libharfbuzz",
    "libthai.so.0": "Thai text segmentation, pulled in by libpango-1.0",
    "libdatrie.so.1": "trie data structure, pulled in by libthai",
    "libfribidi.so.0": "bidirectional text, pulled in by libgdk-3",
    "libepoxy.so.0": "GL dispatch library, pulled in by libgdk-3",
    "libjpeg.so.8": "JPEG codec, pulled in by libgdk_pixbuf-2.0",
    "libselinux.so.1": (
        "SELinux labelling, pulled in transitively through GLib's libgio -- "
        "Arch does not use SELinux"
    ),
    "libpcre.so.3": "regex engine, pulled in transitively through GLib",
    "libpixman-1.so.0": "pixel manipulation, pulled in by libcairo",
    "libpng16.so.16": "PNG codec, pulled in by libcairo",
    "libXcomposite.so.1": "X11 compositing extension client, pulled in by libgdk-3",
    "libXcursor.so.1": "X11 cursor-theme client, pulled in by libgdk-3",
    "libXdamage.so.1": "X11 damage extension client, pulled in by libgdk-3",
    "libXfixes.so.3": "X11 fixes extension client, pulled in by libXcursor",
    "libXi.so.6": "X11 input extension client, pulled in by libatspi",
    "libXinerama.so.1": "X11 multi-monitor extension client, pulled in by libgdk-3",
    "libXrandr.so.2": "X11 RandR extension client, pulled in by libgdk-3",
    "libXrender.so.1": "X11 rendering extension client, pulled in by libXcursor",
    # Transitive dependencies of the already-optional libtiff.so.5 above --
    # moot for the same reason: the TIFF plugin they belong to never loads.
    "libwebp.so.7": "WebP codec, pulled in by the already-optional libtiff.so.5",
    "libjbig.so.0": "JBIG codec, pulled in by the already-optional libtiff.so.5",
    "libdeflate.so.0": "compression library, pulled in by the already-optional libtiff.so.5",
    # Same eglfs KMS/DRM backend as libdrm/libgbm above -- font lookup and
    # rasterising for a QPA backend SAAT never selects on X11 or Wayland.
    "libfontconfig.so.1": "font lookup for the eglfs QPA backend, see libdrm.so.2 note above",
    "libfreetype.so.6": "font rasterising for the eglfs QPA backend, see libdrm.so.2 note above",
    # libXdmcp (bundled, and itself unconditionally provided) implements the
    # X Display Manager Control Protocol -- authenticating a *remote* X
    # login -- which a SAAT session run from a local desktop or Wayland
    # session never negotiates.
    "libbsd.so.0": "legacy BSD compatibility routines, pulled in by libXdmcp's XDMCP support",
    "libmd.so.0": "message-digest routines, pulled in by libbsd",
}

GLIBC_FLOOR = (2, 35)  # the ubuntu-22.04 build runner; see release.yml's header


def _elf_objects(root: Path) -> list[Path]:
    out = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            with open(path, "rb") as handle:
                if handle.read(4) != b"\x7fELF":
                    continue
        except OSError:
            continue
        out.append(path)
    return out


def _readelf_d(path: Path) -> str:
    return subprocess.run(
        ["readelf", "-d", str(path)], capture_output=True, text=True
    ).stdout


_NEEDED_RE = re.compile(r"\(NEEDED\)\s+Shared library: \[([^\]]+)\]")
_SONAME_RE = re.compile(r"\(SONAME\)\s+Library soname: \[([^\]]+)\]")
_GLIBC_RE = re.compile(r"GLIBC_(\d+)\.(\d+)(?:\.(\d+))?")


def _check_resolution(root: Path) -> int:
    """Post-install check: every soname the bundle needs actually resolves
    on this machine.

    The build-time audit proves the Depends list *names a package* for
    every external soname. This proves those package names were the right
    ones -- run against a genuinely apt-installed copy, with only the
    declared dependencies pulled in, an unresolved soname here means the
    package installs and then fails to start. That is the failure mode
    worth catching, and reasoning about Debian package names cannot catch
    it."""
    objects = _elf_objects(root)
    print(f"resolving shared libraries for {len(objects)} objects under {root}")

    unresolved: dict[str, set[str]] = {}
    for path in objects:
        out = subprocess.run(
            ["ldd", str(path)], capture_output=True, text=True
        ).stdout
        for line in out.splitlines():
            if "not found" not in line:
                continue
            soname = line.strip().split()[0]
            unresolved.setdefault(soname, set()).add(str(path.relative_to(root)))

    hard = {s: v for s, v in unresolved.items() if s not in OPTIONAL}
    for soname in sorted(unresolved):
        users = sorted(unresolved[soname])
        if soname in OPTIONAL:
            print(f"  [optional, absent] {soname:<28} -- {OPTIONAL[soname][:60]}...")
        else:
            print(f"  [UNRESOLVED] {soname:<28} <- {users[0]}")

    if not unresolved:
        print("  every soname resolves")
    if hard:
        print("\nRESOLUTION CHECK FAILED:", file=sys.stderr)
        for soname in sorted(hard):
            print(
                f"  - {soname} does not resolve; Depends is missing the "
                f"package that provides it (needed by {sorted(hard[soname])[0]})",
                file=sys.stderr,
            )
        return 1
    print("\nresolution check passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path)
    parser.add_argument(
        "--check-resolution",
        type=Path,
        metavar="INSTALLED_ROOT",
        help="verify every soname resolves in an installed copy, e.g. /usr/lib/saat",
    )
    parser.add_argument("--control", type=Path, default=None)
    parser.add_argument("--copyright", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    args = parser.parse_args()

    if args.check_resolution:
        return _check_resolution(args.check_resolution)
    if not args.stage:
        parser.error("one of --stage or --check-resolution is required")

    here = Path(__file__).resolve().parent
    control = args.control or here / "debian" / "control.in"
    copyright_file = args.copyright or here / "debian" / "copyright"

    app_root = args.stage / "usr" / "lib" / "saat"
    if not app_root.is_dir():
        print(f"error: no staged tree at {app_root}", file=sys.stderr)
        return 1

    objects = _elf_objects(app_root)
    print(f"scanning {len(objects)} ELF objects under {app_root}")

    provided: set[str] = set()
    needed: dict[str, set[str]] = {}
    manifest_rows: list[tuple[str, str]] = []

    # Symlinked .so names count as provided too: PyInstaller uses them for
    # Qt's versioned library names, and a NEEDED entry resolves through one
    # exactly as the dynamic linker would.
    for path in app_root.rglob("*"):
        if path.is_symlink():
            provided.add(path.name)

    for path in objects:
        text = _readelf_d(path)
        rel = str(path.relative_to(app_root))
        provided.add(path.name)
        soname_match = _SONAME_RE.search(text)
        if soname_match:
            provided.add(soname_match.group(1))
            manifest_rows.append((rel, soname_match.group(1)))
        for match in _NEEDED_RE.finditer(text):
            needed.setdefault(match.group(1), set()).add(rel)

    external = {s: v for s, v in needed.items() if s not in provided}

    # --- 1. manifest -----------------------------------------------------
    if args.manifest:
        lines = [
            "Shared libraries bundled inside this package, under",
            "/usr/lib/saat/_internal. Generated from the package contents at",
            "build time -- see /usr/share/doc/saat/copyright, which names the",
            "licence covering every one of them.",
            "",
        ]
        width = max((len(r) for r, _ in manifest_rows), default=0)
        for rel, soname in sorted(manifest_rows):
            lines.append(f"{rel.ljust(width)}  {soname}")
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote manifest: {len(manifest_rows)} shared objects")

    # --- 2. dependency coverage ------------------------------------------
    depends_line = ""
    for line in control.read_text(encoding="utf-8").splitlines():
        if line.startswith("Depends:"):
            depends_line = line.partition(":")[2]
    declared = {
        re.split(r"[ (]", part.strip())[0]
        for part in depends_line.split(",")
        if part.strip()
    }

    print(f"\ndeclared Depends: {', '.join(sorted(declared))}")
    print(f"\nexternal sonames the bundle needs ({len(external)}):")

    failures = []
    for soname in sorted(external):
        users = sorted(external[soname])
        if soname in REQUIRED:
            package = REQUIRED[soname]
            status = "ok" if package in declared else "MISSING FROM Depends"
            if package not in declared:
                failures.append(
                    f"{soname} needs {package}, which control.in does not name"
                )
            print(f"  [required] {soname:<28} -> {package:<22} {status}")
        elif soname in OPTIONAL:
            print(f"  [optional] {soname:<28} -> not depended on")
            print(f"             reason: {OPTIONAL[soname]}")
        else:
            failures.append(
                f"{soname} is needed by {users[0]}"
                f"{f' (and {len(users) - 1} more)' if len(users) > 1 else ''} "
                "but is classified in neither REQUIRED nor OPTIONAL in "
                "packaging/audit-bundle.py"
            )
            print(f"  [UNKNOWN]  {soname:<28} <- {users[0]}")

    unused = declared - {REQUIRED[s] for s in external if s in REQUIRED}
    if unused:
        print(
            f"\nnote: Depends names {', '.join(sorted(unused))}, which no "
            "DT_NEEDED entry in this build requires. That is expected for the "
            "platform stack the app dlopens through Qt, but worth re-reading "
            "if the list grows."
        )

    # --- 3. glibc floor --------------------------------------------------
    highest = (0, 0)
    for path in objects:
        out = subprocess.run(
            ["readelf", "--dyn-syms", "--wide", str(path)],
            capture_output=True,
            text=True,
        ).stdout
        for match in _GLIBC_RE.finditer(out):
            version = (int(match.group(1)), int(match.group(2)))
            highest = max(highest, version)
    print(f"\nhighest glibc symbol version referenced: {highest[0]}.{highest[1]}")
    print(f"floor promised by Depends:               {GLIBC_FLOOR[0]}.{GLIBC_FLOOR[1]}")
    if highest > GLIBC_FLOOR:
        failures.append(
            f"the bundle references GLIBC_{highest[0]}.{highest[1]}, above the "
            f"libc6 (>= {GLIBC_FLOOR[0]}.{GLIBC_FLOOR[1]}) floor Depends "
            "promises -- it was built on too new a runner"
        )

    # --- 4. licence coverage ---------------------------------------------
    # Matched against the copyright's own Files: globs rather than by
    # substring, so a stanza covering `libQt6*` genuinely accounts for
    # libQt6Core.so.6 -- and, more to the point, so a library nothing
    # matches is reported rather than accidentally passing because its name
    # happens to appear in a comment somewhere.
    patterns = []
    in_files = False
    for line in copyright_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("Files:"):
            in_files = True
            patterns.extend(line.partition(":")[2].split())
            continue
        if in_files and line.startswith(" ") and line.strip():
            patterns.extend(line.split())
            continue
        in_files = False
    patterns = [p for p in patterns if p]

    uncovered = []
    for rel, _ in manifest_rows:
        target = f"usr/lib/saat/{rel}"
        if not any(fnmatch(target, pattern) for pattern in patterns):
            uncovered.append(target)

    print(f"\nbundled shared objects: {len(manifest_rows)}")
    if uncovered:
        for target in sorted(uncovered):
            failures.append(
                f"{target} is shipped but matches no Files: stanza in "
                "debian/copyright"
            )
            print(f"  [UNCOVERED] {target}")
    else:
        print("  every one matches a Files: stanza in debian/copyright")

    if failures:
        print("\nAUDIT FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print("\naudit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
