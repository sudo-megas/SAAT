import os
import sys
from pathlib import Path


def app_dir() -> Path:
    """The directory the app and its data live in. Never a temp dir."""
    if os.environ.get("APPIMAGE"):            # AppImage: the .AppImage file's folder
        return Path(os.environ["APPIMAGE"]).resolve().parent
    if getattr(sys, "frozen", False):          # PyInstaller: the executable's folder
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent  # source checkout: project root


def resource_dir() -> Path:
    """Bundled read-only resources: theme, fonts, icons. Never the writable data dir."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent     # the saat/ package directory
