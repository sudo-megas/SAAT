#!/usr/bin/env bash
# Reverses exactly what install.sh did: /opt/saat, the /usr/local/bin
# symlink, the icon, the application-launcher entry, and (milestone 18) the
# autostart entry a user may have enabled from the tray menu. Never touches
# user data — $XDG_DATA_HOME/saat and $XDG_CONFIG_HOME/saat (or their
# defaults, ~/.local/share/saat and ~/.config/saat) are left exactly as they
# are. The autostart entry is a deliberate, narrow exception to that
# promise: it is not user data, it's the one OS-integration artifact this
# install caused (SPEC.md §2 rule 2's amendment), so reversing everything
# install.sh did means removing it too.
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "uninstall.sh must be run as root (it removes files under /opt, /usr/local/bin and /usr/share). Try: sudo ./uninstall.sh" >&2
    exit 1
fi

echo "Removing /usr/local/bin/saat..."
rm -f /usr/local/bin/saat

echo "Removing application-launcher entry..."
rm -f /usr/share/applications/saat.desktop

echo "Removing autostart entry..."
# Running as root under sudo means $HOME here is root's, not the invoking
# user's -- the autostart entry lives in the real user's home, so it has to
# be resolved explicitly rather than trusting $HOME or a bare ~/.config.
target_user="${SUDO_USER:-$USER}"
target_home="$(getent passwd "$target_user" | cut -d: -f6)"
if [ -n "$target_home" ]; then
    # Honours a preserved XDG_CONFIG_HOME (e.g. sudo -E) the same way the
    # app itself does, falling back to the resolved user's default
    # otherwise; ":-" also treats a set-but-empty value as unset, matching
    # the XDG spec the app's own paths.py already follows.
    xdg_config_home="${XDG_CONFIG_HOME:-$target_home/.config}"
    rm -f "$xdg_config_home/autostart/saat.desktop"
else
    echo "warning: could not resolve a home directory for '$target_user' -- skipping autostart entry removal" >&2
fi

echo "Removing icon..."
rm -f /usr/share/icons/hicolor/256x256/apps/saat.png
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi

echo "Removing /opt/saat..."
rm -rf /opt/saat

echo "Done. Your collection in \$XDG_DATA_HOME/saat (default ~/.local/share/saat)"
echo "and config in \$XDG_CONFIG_HOME/saat (default ~/.config/saat) were not touched."
