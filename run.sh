#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d .venv ]; then
    python3 -m venv .venv
fi

.venv/bin/pip install --quiet --upgrade pip
# requirements.txt is the only place the runtime dependencies are named --
# both CI workflows install from it too, so a developer's venv and a
# release build get identical versions.
.venv/bin/pip install --quiet -r requirements.txt

# Linux-only, and deliberately not mirrored into run.ps1: Qt would
# otherwise sometimes pick the X11 backend on the Wayland session this app
# targets. Windows has one platform plugin, Qt selects it correctly, and
# forcing anything there is wrong -- see run.ps1. Nothing in saat/ reads
# this variable; it is a launcher concern on both platforms.
export QT_QPA_PLATFORM=wayland
exec .venv/bin/python main.py
