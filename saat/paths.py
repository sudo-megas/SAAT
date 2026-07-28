import os
import sys
from pathlib import Path

INSTALLED_MARKER = ".installed"

_WINDOWS = os.name == "nt"


def _installed_mode() -> bool:
    """Opt-in only: frozen AND the marker beside the executable, written by
    install.sh, shipped inside the .deb, or written by the Windows
    installer. Never inferred from XDG variables or %APPDATA% alone — a
    missing marker must stay portable, not silently relocate a portable
    user's collection."""
    if not getattr(sys, "frozen", False):
        return False
    return (Path(sys.executable).resolve().parent / INSTALLED_MARKER).exists()


def _portable_dir() -> Path:
    """The directory the app and its data live in, in portable mode. Never a
    temp dir.

    Identical on every platform, deliberately: portable means beside the
    executable, and that is the whole of the rule. A portable copy on a USB
    stick behaves the same whichever machine it is plugged into."""
    if os.environ.get("APPIMAGE"):            # AppImage: the .AppImage file's folder
        return Path(os.environ["APPIMAGE"]).resolve().parent
    if getattr(sys, "frozen", False):          # PyInstaller: the executable's folder
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent  # source checkout: project root


def _installed_dir(
    xdg_env: str,
    xdg_default_subpath: tuple[str, ...],
    windows_env: str,
    windows_default_subpath: tuple[str, ...],
) -> Path:
    """Where an installed copy keeps this kind of file, per the conventions
    of the platform it is running on.

    Windows has no XDG variables and no single per-user root. Its
    convention splits along the same line this app already splits on:
    %LOCALAPPDATA% for data belonging to this machine — which a watch
    collection with its photographs is — and %APPDATA% for settings that
    follow the user's profile between machines. The directory is named
    `SAAT` there rather than `saat`, matching how applications under those
    roots are conventionally named.

    Both are read from the environment, with a fallback derived from
    Path.home() rather than a hardcoded C:\\Users: a profile is not always
    on C:, and a domain or redirected profile is routinely somewhere else
    entirely."""
    if _WINDOWS:
        base = os.environ.get(windows_env)
        if not base:
            base = str(Path.home().joinpath(*windows_default_subpath))
        return Path(base) / "SAAT"
    base = os.environ.get(xdg_env) or str(Path.home().joinpath(*xdg_default_subpath))
    return Path(base) / "saat"


def _resolve(
    xdg_env: str,
    xdg_default_subpath: tuple[str, ...],
    windows_env: str,
    windows_default_subpath: tuple[str, ...],
) -> Path:
    # Precedence, unchanged and platform-independent:
    # SAAT_DATA_DIR > installed mode > portable.
    if "SAAT_DATA_DIR" in os.environ:
        path = Path(os.environ["SAAT_DATA_DIR"])
    elif _installed_mode():
        path = _installed_dir(
            xdg_env, xdg_default_subpath, windows_env, windows_default_subpath
        )
    else:
        path = _portable_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    """Writable: watches/, backups/, sellers.toml.

    Portable mode: beside the executable, on every platform.
    Installed mode: XDG_DATA_HOME/saat (default ~/.local/share/saat) on
    Linux, %LOCALAPPDATA%\\SAAT on Windows."""
    return _resolve(
        "XDG_DATA_HOME", (".local", "share"), "LOCALAPPDATA", ("AppData", "Local")
    )


def config_dir() -> Path:
    """Writable: config.toml.

    Portable mode: beside the executable, on every platform.
    Installed mode: XDG_CONFIG_HOME/saat (default ~/.config/saat) on Linux,
    %APPDATA%\\SAAT on Windows."""
    return _resolve(
        "XDG_CONFIG_HOME", (".config",), "APPDATA", ("AppData", "Roaming")
    )


def is_installed() -> bool:
    """Public check for installed vs portable mode, for anything that
    behaves differently between the two -- e.g. autostart.py, offered only
    in installed mode (SPEC.md §2 rule 2's amendment)."""
    return _installed_mode()


def resource_dir() -> Path:
    """Bundled read-only resources: theme, fonts, icons. Never the writable
    data/config dirs. Unaffected by portable vs installed mode, and by
    platform."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent     # the saat/ package directory
