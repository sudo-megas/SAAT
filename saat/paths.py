import os
import sys
from pathlib import Path

INSTALLED_MARKER = ".installed"


def _installed_mode() -> bool:
    """Opt-in only: frozen AND the marker install.sh writes is present beside
    the executable. Never infer from XDG vars alone — a missing marker must
    stay portable, not silently relocate a portable user's collection."""
    if not getattr(sys, "frozen", False):
        return False
    return (Path(sys.executable).resolve().parent / INSTALLED_MARKER).exists()


def _portable_dir() -> Path:
    """The directory the app and its data live in, in portable mode. Never a
    temp dir."""
    if os.environ.get("APPIMAGE"):            # AppImage: the .AppImage file's folder
        return Path(os.environ["APPIMAGE"]).resolve().parent
    if getattr(sys, "frozen", False):          # PyInstaller: the executable's folder
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent  # source checkout: project root


def _resolve(xdg_env: str, xdg_default_subpath: tuple[str, ...]) -> Path:
    if "SAAT_DATA_DIR" in os.environ:
        path = Path(os.environ["SAAT_DATA_DIR"])
    elif _installed_mode():
        base = os.environ.get(xdg_env) or str(Path.home().joinpath(*xdg_default_subpath))
        path = Path(base) / "saat"
    else:
        path = _portable_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    """Writable: watches/, backups/. Portable mode: beside the executable.
    Installed mode: XDG_DATA_HOME/saat (default ~/.local/share/saat)."""
    return _resolve("XDG_DATA_HOME", (".local", "share"))


def config_dir() -> Path:
    """Writable: config.toml. Portable mode: beside the executable. Installed
    mode: XDG_CONFIG_HOME/saat (default ~/.config/saat)."""
    return _resolve("XDG_CONFIG_HOME", (".config",))


def resource_dir() -> Path:
    """Bundled read-only resources: theme, fonts, icons. Never the writable
    data/config dirs. Unaffected by portable vs installed mode."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent     # the saat/ package directory
