#!/usr/bin/env bash
# Installs the portable build at dist/SAAT as a system-wide application:
# /opt/saat, a /usr/local/bin symlink, and an application-launcher entry.
# Writing the .installed marker is what switches the app from portable mode
# (data beside the executable) to installed mode (data under the OS's
# standard per-user locations) — see SPEC.md §2 and §8.
#
# This is the reference a future .deb's postinst script will follow: build
# first (`pyinstaller SAAT.spec`), then install. The two are kept separate
# on purpose, same as a .deb never compiles anything in postinst.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ "$EUID" -ne 0 ]; then
    echo "install.sh must be run as root (it writes to /opt, /usr/local/bin and /usr/share). Try: sudo ./install.sh" >&2
    exit 1
fi

if [ ! -d dist/SAAT ]; then
    echo "dist/SAAT not found. Build it first — see the README's 'Build a portable version':" >&2
    echo "  .venv/bin/pip install pyinstaller && .venv/bin/pyinstaller SAAT.spec" >&2
    exit 1
fi

echo "Installing to /opt/saat..."
rm -rf /opt/saat
cp -r dist/SAAT /opt/saat
touch /opt/saat/.installed

echo "Linking /usr/local/bin/saat..."
ln -sf /opt/saat/SAAT /usr/local/bin/saat

echo "Installing icon..."
install -Dm644 /opt/saat/_internal/resources/icon/saat.png \
    /usr/share/icons/hicolor/256x256/apps/saat.png
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi

echo "Installing application-launcher entry..."
install -Dm644 /dev/stdin /usr/share/applications/saat.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=SAAT
Comment=Catalogue a mechanical-watch collection
Exec=/usr/local/bin/saat
Icon=saat
Terminal=false
Categories=Utility;
EOF

echo "Done. Your collection will live in \$XDG_DATA_HOME/saat (default ~/.local/share/saat)"
echo "and config in \$XDG_CONFIG_HOME/saat (default ~/.config/saat) — never in /opt."
