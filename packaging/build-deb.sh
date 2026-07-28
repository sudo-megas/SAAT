#!/usr/bin/env bash
# Turns a staged FHS tree (packaging/stage-tree.sh) into a .deb.
#
#   ./packaging/build-deb.sh [--dist dist/SAAT] [--output dist]
#
# Composes DEBIAN/ on top of the staged payload and hands the result to
# dpkg-deb. See packaging/README.md for why dpkg-deb rather than debhelper,
# and why the bundled Qt is shipped as-is.
#
# The audit step is not optional decoration: it is what makes the Depends
# line and the copyright file claims about this build rather than about a
# build someone remembers. It fails the package rather than warning.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dist_dir="$repo_root/dist/SAAT"
output_dir="$repo_root/dist"
revision="1"

while [ $# -gt 0 ]; do
    case "$1" in
        --dist)     dist_dir="$2"; shift 2 ;;
        --output)   output_dir="$2"; shift 2 ;;
        --revision) revision="$2"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

command -v dpkg-deb >/dev/null 2>&1 || {
    echo "dpkg-deb not found -- this runs on a Debian/Ubuntu machine or CI runner" >&2
    exit 1
}

version="$(cd "$repo_root" && python3 -c 'import saat; print(saat.__version__)')"
deb_version="${version}-${revision}"
maintainer="$(sed -n 's/^Maintainer: //p' "$repo_root/packaging/debian/control.in")"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
stage="$work/stage"

echo "==> staging the filesystem tree"
"$repo_root/packaging/stage-tree.sh" --dist "$dist_dir" --stage "$stage"

echo
echo "==> documentation and licensing"
install -Dm644 "$repo_root/packaging/debian/copyright" \
    "$stage/usr/share/doc/saat/copyright"

# A non-native version (2.0-1) means the packaging changelog is
# changelog.Debian.gz, alongside the upstream changelog.gz stage-tree.sh
# already installed. Dated from the commit rather than from the clock, so
# rebuilding the same commit produces the same package.
source_date="${SOURCE_DATE_EPOCH:-$(cd "$repo_root" && git log -1 --pretty=%ct 2>/dev/null || date +%s)}"
changelog_date="$(date --utc --date="@${source_date}" -R)"
sed -e "s/@VERSION@/${deb_version}/" \
    -e "s/@DATE@/${changelog_date}/" \
    -e "s|@MAINTAINER@|${maintainer}|" \
    "$repo_root/packaging/debian/changelog.Debian.in" \
    > "$work/changelog.Debian"
gzip -9nc "$work/changelog.Debian" > "$stage/usr/share/doc/saat/changelog.Debian.gz"
chmod 0644 "$stage/usr/share/doc/saat/changelog.Debian.gz"

install -Dm644 "$repo_root/packaging/debian/lintian-overrides" \
    "$stage/usr/share/lintian/overrides/saat"

echo
echo "==> auditing the bundle"
python3 "$repo_root/packaging/audit-bundle.py" \
    --stage "$stage" \
    --manifest "$stage/usr/share/doc/saat/bundled-libraries.txt"
chmod 0644 "$stage/usr/share/doc/saat/bundled-libraries.txt"

echo
echo "==> DEBIAN control metadata"
install -d -m 0755 "$stage/DEBIAN"

# du -sk over the payload only: Installed-Size is in KiB and excludes the
# control area, which is not installed.
installed_size="$(du -sk --exclude=DEBIAN "$stage" | cut -f1)"
sed -e "s/@VERSION@/${deb_version}/" \
    -e "s/@INSTALLED_SIZE@/${installed_size}/" \
    "$repo_root/packaging/debian/control.in" > "$stage/DEBIAN/control"

for script in postinst prerm postrm; do
    install -m 0755 "$repo_root/packaging/debian/$script" "$stage/DEBIAN/$script"
done

# md5sums over every regular file in the payload, so `dpkg -V saat` and
# debsums can tell whether an installed copy has been altered.
( cd "$stage" && find . -path ./DEBIAN -prune -o -type f -print0 \
    | sed -z 's|^\./||' | sort -z | xargs -0 md5sum > DEBIAN/md5sums )

echo
echo "==> dpkg-deb"
mkdir -p "$output_dir"
package="$output_dir/saat_${deb_version}_amd64.deb"
# --root-owner-group rather than running under fakeroot: every file in this
# package is root:root, and there is nothing to preserve from the build
# user.
dpkg-deb --root-owner-group --build "$stage" "$package"

echo
ls -lh "$package"
dpkg-deb --info "$package"
echo "built $package"
