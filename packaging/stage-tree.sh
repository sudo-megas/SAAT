#!/usr/bin/env bash
# Composes the FHS tree a SAAT installation consists of, from an existing
# PyInstaller one-folder build. This is the payload half of the .deb; the
# DEBIAN/ control metadata is added on top by build-deb.sh.
#
#   ./packaging/stage-tree.sh [--dist dist/SAAT] --stage <dir>
#
# The result is a directory that could be `cp -a`'d onto / and be a working
# installation. Keeping it a plain tree, separate from packaging metadata,
# is what lets the layout be inspected and tested without dpkg present --
# which matters, because the machine this is developed on is Arch and has
# no dpkg at all.
#
# See packaging/README.md for why the bundled build is shipped as-is rather
# than repackaged against Debian's own PySide6, and why /usr/bin/saat is a
# symlink.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dist_dir="$repo_root/dist/SAAT"
stage_dir=""

while [ $# -gt 0 ]; do
    case "$1" in
        --dist)  dist_dir="$2"; shift 2 ;;
        --stage) stage_dir="$2"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

[ -n "$stage_dir" ] || { echo "--stage <dir> is required" >&2; exit 2; }

if [ ! -x "$dist_dir/SAAT" ]; then
    echo "no PyInstaller build at $dist_dir -- run 'pyinstaller SAAT.spec' first" >&2
    exit 1
fi

version="$(cd "$repo_root" && python3 -c 'import saat; print(saat.__version__)')"

rm -rf "$stage_dir"
mkdir -p "$stage_dir"

# --- the one-folder build ------------------------------------------------
# cp -a, not cp -r: PyInstaller's bundle contains symlinks between Qt's
# versioned .so names, and flattening them into copies would roughly double
# an already-large package.
install -d -m 0755 "$stage_dir/usr/lib"
cp -a "$dist_dir" "$stage_dir/usr/lib/saat"

# SPEC.md §2's opt-in marker: frozen AND this file beside the executable is
# what switches data from "beside the binary" to ~/.local/share/saat. It is
# shipped as a package file rather than written by postinst so dpkg owns it
# and removes it cleanly -- see packaging/README.md.
touch "$stage_dir/usr/lib/saat/.installed"

# --- entry point ---------------------------------------------------------
# A relative symlink, per Debian policy 10.5 (symlinks within the same
# top-level hierarchy are relative). Verified to work: PyInstaller's Linux
# bootloader resolves its own path through /proc/self/exe, and paths.py
# calls .resolve() besides, so the marker above is still found beside the
# real executable when the app is launched as /usr/bin/saat.
install -d -m 0755 "$stage_dir/usr/bin"
ln -sfn ../lib/saat/SAAT "$stage_dir/usr/bin/saat"

# --- desktop integration -------------------------------------------------
# The same .desktop file install.sh installs, and the same icon that ships
# inside the bundle -- one source of truth for each, so a packaged install
# and a scripted install cannot drift apart.
install -Dm644 "$repo_root/packaging/saat.desktop" \
    "$stage_dir/usr/share/applications/saat.desktop"
install -Dm644 "$stage_dir/usr/lib/saat/_internal/resources/icon/saat.png" \
    "$stage_dir/usr/share/icons/hicolor/256x256/apps/saat.png"

# --- documentation -------------------------------------------------------
install -Dm644 "$repo_root/packaging/saat.1" "$stage_dir/usr/share/man/man1/saat.1"
gzip -9n "$stage_dir/usr/share/man/man1/saat.1"

# The upstream changelog. -n so gzip records no timestamp, keeping the
# package reproducible across rebuilds of the same commit.
install -d -m 0755 "$stage_dir/usr/share/doc/saat"
gzip -9nc "$repo_root/CHANGELOG.md" > "$stage_dir/usr/share/doc/saat/changelog.gz"
chmod 0644 "$stage_dir/usr/share/doc/saat/changelog.gz"

# --- permissions ---------------------------------------------------------
# PyInstaller writes the bundle with the building user's umask. Normalise so
# the package contents do not depend on how the build machine was configured:
# no group/other write anywhere, directories traversable.
find "$stage_dir" -type d -exec chmod 0755 {} +
find "$stage_dir" -type f -perm -0100 -exec chmod 0755 {} +
find "$stage_dir" -type f ! -perm -0100 -exec chmod 0644 {} +

echo "staged SAAT $version at $stage_dir"
