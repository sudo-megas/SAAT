import os
from pathlib import Path

from saat.atomic import write_atomic
from saat.paths import is_installed

# The launcher entry install.sh already writes, in installed mode -- fixed
# because install.sh's own heredoc writes to exactly this path. Read, never
# written, by this module: reused rather than composing a second, divergent
# .desktop file (SPEC.md milestone 18 §12).
INSTALLED_DESKTOP_PATH = Path("/usr/share/applications/saat.desktop")

DESKTOP_FILENAME = "saat.desktop"

# Appended to the reused file's own Exec= line so a launch through the
# autostart entry is distinguishable from a manual one -- see main.py's
# should_start_hidden(): "Start minimised" (SPEC.md milestone 18 §15) must
# only ever affect an autostarted launch, never a manual one.
AUTOSTART_FLAG = "--autostart"


def _autostart_dir() -> Path:
    """$XDG_CONFIG_HOME/autostart (default ~/.config/autostart) -- the XDG
    Autostart directory, shared by every app that registers one. Not this
    app's own config_dir(), which would wrongly namespace it under saat/;
    this is SPEC.md §2 rule 2's sanctioned exception, so it deliberately
    lives outside the usual data_dir()/config_dir()/resource_dir() trio
    rather than folded into paths.py alongside them."""
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart"


def autostart_path() -> Path:
    return _autostart_dir() / DESKTOP_FILENAME


def is_available() -> bool:
    """SPEC.md milestone 18 §11: a portable copy on removable media
    registering itself to start at boot is incoherent -- the medium may not
    be present. Offered only in installed mode."""
    return is_installed()


def is_enabled() -> bool:
    """Reflects reality -- whether the entry exists on disk right now, per
    SPEC.md milestone 18 §14 -- never a separately stored flag that could
    drift out of sync with it."""
    return autostart_path().exists()


def _with_autostart_flag(desktop_file_content: str) -> str:
    lines = desktop_file_content.splitlines(keepends=True)
    result = []
    for line in lines:
        if line.startswith("Exec="):
            stripped = line.rstrip("\n")
            result.append(f"{stripped} {AUTOSTART_FLAG}\n")
        else:
            result.append(line)
    return "".join(result)


def enable() -> None:
    if not INSTALLED_DESKTOP_PATH.exists():
        raise FileNotFoundError(
            f"{INSTALLED_DESKTOP_PATH} does not exist -- was install.sh run?"
        )
    content = INSTALLED_DESKTOP_PATH.read_text(encoding="utf-8")
    target = autostart_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(target, _with_autostart_flag(content))


def disable() -> None:
    autostart_path().unlink(missing_ok=True)
