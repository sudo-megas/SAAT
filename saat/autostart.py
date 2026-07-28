import os
import subprocess
import sys
from pathlib import Path

from saat.atomic import write_atomic
from saat.paths import is_installed

_WINDOWS = os.name == "nt"

# The launcher entry install.sh already writes, in installed mode -- fixed
# because install.sh (and, since milestone 23, the shared
# packaging/saat.desktop both it and the .deb install) writes to exactly
# this path. Read, never written, by this module: reused rather than
# composing a second, divergent .desktop file (SPEC.md milestone 18 §12).
INSTALLED_DESKTOP_PATH = Path("/usr/share/applications/saat.desktop")

DESKTOP_FILENAME = "saat.desktop"

# Windows' equivalent: a shortcut in the per-user Startup folder. Chosen
# over an HKCU\...\Run registry value deliberately (SPEC.md milestone 24
# §8). The folder is somewhere a user can open, see and delete; a registry
# value is not, and a GPL hobby application should not look like it is
# installing itself into places people cannot inspect. It also keeps
# is_enabled() honest for free -- "is there a file there" is the same
# question on both platforms.
SHORTCUT_FILENAME = "SAAT.lnk"

# Appended to the reused file's own Exec= line, or to the shortcut's
# arguments, so a launch through the autostart entry is distinguishable
# from a manual one -- see main.py's should_start_hidden(): "Start
# minimised" (SPEC.md milestone 18 §15) must only ever affect an
# autostarted launch, never a manual one.
AUTOSTART_FLAG = "--autostart"


def _autostart_dir() -> Path:
    """The shared directory this platform's session reads at login.

    On Linux, $XDG_CONFIG_HOME/autostart (default ~/.config/autostart) --
    the XDG Autostart directory every app that registers one writes into.
    Not this app's own config_dir(), which would wrongly namespace it under
    saat/; this is SPEC.md §2 rule 2's sanctioned exception, so it
    deliberately lives outside the usual data_dir()/config_dir()/
    resource_dir() trio rather than folded into paths.py alongside them.

    On Windows, the per-user Startup folder under %APPDATA%. Exactly the
    same character of location: shared with every other app that starts at
    login, not namespaced per-app, and nowhere near the two directories
    that hold the user's collection."""
    if _WINDOWS:
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return (
            Path(base)
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "Startup"
        )
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart"


def autostart_path() -> Path:
    return _autostart_dir() / (SHORTCUT_FILENAME if _WINDOWS else DESKTOP_FILENAME)


def is_available() -> bool:
    """SPEC.md milestone 18 §11: a portable copy on removable media
    registering itself to start at boot is incoherent -- the medium may not
    be present. Offered only in installed mode, on every platform."""
    return is_installed()


def is_enabled() -> bool:
    """Reflects reality -- whether the entry exists on disk right now, per
    SPEC.md milestone 18 §14 -- never a separately stored flag that could
    drift out of sync with it. A user who deletes the shortcut out of their
    Startup folder by hand has disabled autostart, and the menu says so.

    Deliberately a stat() on both platforms and nothing more: the tray menu
    re-reads this every time it opens, so it must never be the expensive
    half of the feature."""
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


def _enable_xdg() -> None:
    if not INSTALLED_DESKTOP_PATH.exists():
        raise FileNotFoundError(
            f"{INSTALLED_DESKTOP_PATH} does not exist -- was install.sh run?"
        )
    content = INSTALLED_DESKTOP_PATH.read_text(encoding="utf-8")
    target = autostart_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(target, _with_autostart_flag(content))


# Creating a .lnk means the Shell Link binary format, which in practice
# means COM. pywin32 would do it in three lines and is the obvious answer
# in any other project -- but SPEC.md §2 rule 5 caps this application at
# three runtime dependencies and asks for written justification for a
# fourth. There is none worth writing here: PowerShell ships with every
# supported Windows, and this runs once, only when the user explicitly
# toggles the menu item, never at startup and never on any hot path.
#
# Every path goes in through the environment rather than being interpolated
# into the script text. The user's own name is inside %APPDATA%, and a path
# containing a quote, a backtick or a $ would otherwise either break the
# command or be interpreted by it.
_CREATE_SHORTCUT_PS1 = (
    "$ErrorActionPreference = 'Stop'; "
    "$shell = New-Object -ComObject WScript.Shell; "
    "$link = $shell.CreateShortcut($env:SAAT_LNK_PATH); "
    "$link.TargetPath = $env:SAAT_LNK_TARGET; "
    "$link.Arguments = $env:SAAT_LNK_ARGS; "
    "$link.WorkingDirectory = $env:SAAT_LNK_WORKDIR; "
    "$link.IconLocation = $env:SAAT_LNK_TARGET; "
    "$link.Description = 'SAAT - Watch Collection Manager'; "
    "$link.Save()"
)


def _enable_windows() -> None:
    executable = Path(sys.executable).resolve()
    shortcut = autostart_path()
    shortcut.parent.mkdir(parents=True, exist_ok=True)

    environment = dict(os.environ)
    environment.update(
        SAAT_LNK_PATH=str(shortcut),
        SAAT_LNK_TARGET=str(executable),
        SAAT_LNK_ARGS=AUTOSTART_FLAG,
        SAAT_LNK_WORKDIR=str(executable.parent),
    )

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy", "Bypass",
            "-Command", _CREATE_SHORTCUT_PS1,
        ],
        env=environment,
        capture_output=True,
        text=True,
        # No console window flashing up behind the app for the fraction of
        # a second this takes. The flag does not exist on non-Windows
        # Pythons, hence the getattr.
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    # SPEC.md §2 rule 7: surfaced with the message intact, never swallowed.
    # MainWindow._on_start_at_login_toggled shows this in a dialog, and the
    # menu item's checked state re-reads is_enabled() from disk the next
    # time the menu opens -- so a failure leaves the checkbox telling the
    # truth, with no separate revert needed here.
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise OSError(
            f"could not create the Startup shortcut at {shortcut}: {detail}"
        )
    if not shortcut.exists():
        raise OSError(
            f"PowerShell reported success but no shortcut exists at {shortcut}"
        )


def enable() -> None:
    if _WINDOWS:
        _enable_windows()
    else:
        _enable_xdg()


def disable() -> None:
    """Identical on both platforms: delete the entry. There is nothing else
    to undo -- this module has only ever created one file."""
    autostart_path().unlink(missing_ok=True)
