#!/usr/bin/env bash
# Turns a built SAAT tarball into an Arch Linux .pkg.tar.zst, via makepkg.
#
#   ./packaging/build-pkg.sh --tarball dist/SAAT-vX.Y.Z-linux-x86_64.tar.gz \
#       [--version X.Y.Z] [--pkgrel 1] [--output dist]
#
# --tarball is always a local path -- the ordinary case wraps the tarball
# build-linux-x86_64 just produced, exactly as build-deb.sh wraps it into
# the .deb. The backfill workflow (arch-backfill.yml, for a release that
# already shipped without a package) curls the historical release tarball
# down first and hands it to this script the same way; --sha256 is there so
# that download can be cross-checked before it is trusted. Its digest is
# computed here regardless.
#
# --version defaults to saat.__version__, same as build-deb.sh -- the
# ordinary case packages whatever tag is checked out. Pass --version
# explicitly only for the backfill case, where the tarball being wrapped
# (an already-published release) is not necessarily the tag checked out on
# disk right now.
#
# makepkg refuses to run as root -- this script does not create or drop to
# a build user itself, because that is CI-environment plumbing, not
# packaging logic. Run it as an unprivileged user with sudo configured for
# pacman, same division of concerns as build-deb.sh needing dpkg-deb
# already on PATH.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir="$repo_root/dist"
pkgrel="1"
tarball=""
version=""
sha256=""

while [ $# -gt 0 ]; do
    case "$1" in
        --tarball) tarball="$2"; shift 2 ;;
        --version) version="$2"; shift 2 ;;
        --pkgrel)  pkgrel="$2"; shift 2 ;;
        --sha256)  sha256="$2"; shift 2 ;;
        --output)  output_dir="$2"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

[ -n "$tarball" ] || { echo "--tarball <path> is required" >&2; exit 2; }
[ -f "$tarball" ] || { echo "no such file: $tarball" >&2; exit 1; }
if [ -z "$version" ]; then
    version="$(cd "$repo_root" && python3 -c 'import saat; print(saat.__version__)')"
fi

command -v makepkg >/dev/null 2>&1 || {
    echo "makepkg not found -- this runs on an Arch Linux machine or CI runner" >&2
    exit 1
}
[ "$EUID" != 0 ] || {
    echo "makepkg refuses to run as root -- invoke this as an unprivileged user" >&2
    exit 1
}

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

tarball_name="$(basename "$tarball")"
cp "$tarball" "$work/$tarball_name"
computed="$(sha256sum "$tarball" | cut -d' ' -f1)"
if [ -n "$sha256" ] && [ "$sha256" != "$computed" ]; then
    echo "--sha256 $sha256 does not match $tarball ($computed)" >&2
    exit 1
fi
sha256="$computed"

echo "==> generating PKGBUILD"
sed -e "s/@VERSION@/${version}/" \
    -e "s/@PKGREL@/${pkgrel}/" \
    -e "s|@SOURCE@|${tarball_name}|" \
    -e "s/@SHA256@/${sha256}/" \
    "$repo_root/packaging/arch/PKGBUILD.in" > "$work/PKGBUILD"

echo
echo "==> makepkg"
(
    cd "$work"
    export SAAT_REPO="$repo_root"
    makepkg --syncdeps --noconfirm --clean
)

mkdir -p "$output_dir"
package="$(ls "$work"/saat-"${version}"-"${pkgrel}"-*.pkg.tar.zst)"
mv "$package" "$output_dir/"
package="$output_dir/$(basename "$package")"

echo
ls -lh "$package"
echo "built $package"
