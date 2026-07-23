#!/usr/bin/env bash
# Reverses exactly what install.sh did: /opt/saat, the /usr/local/bin
# symlink, the icon and the application-launcher entry. Never touches user
# data — $XDG_DATA_HOME/saat and $XDG_CONFIG_HOME/saat (or their defaults,
# ~/.local/share/saat and ~/.config/saat) are left exactly as they are.
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "uninstall.sh must be run as root (it removes files under /opt, /usr/local/bin and /usr/share). Try: sudo ./uninstall.sh" >&2
    exit 1
fi

echo "Removing /usr/local/bin/saat..."
rm -f /usr/local/bin/saat

echo "Removing application-launcher entry..."
rm -f /usr/share/applications/saat.desktop

echo "Removing icon..."
rm -f /usr/share/icons/hicolor/256x256/apps/saat.png
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi

echo "Removing /opt/saat..."
rm -rf /opt/saat

echo "Done. Your collection in \$XDG_DATA_HOME/saat (default ~/.local/share/saat)"
echo "and config in \$XDG_CONFIG_HOME/saat (default ~/.config/saat) were not touched."
