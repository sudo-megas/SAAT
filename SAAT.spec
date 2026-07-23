# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller one-folder (--onedir) build. See SPEC.md §8.
#
# Build:  pyinstaller SAAT.spec   (from the repo root, in a venv that has
#         PySide6 + tomlkit + Pillow + pyinstaller installed)
# Output: dist/SAAT/ — the portable folder. Copy it anywhere; watches/,
#         config.toml and backups/ are created beside the executable at
#         runtime, never inside _internal/.
#
# Why this shape:
#   * datas ships exactly one read-only resource — saat/ui/theme.qss — to
#     `ui/` inside the bundle. When frozen, resource_dir() returns
#     sys._MEIPASS and theme.py reads `_MEIPASS/ui/theme.qss`, so the dest
#     MUST be "ui". Fonts are system-with-fallback (resolve_fonts()) and
#     there are no icons, so this is the whole resource surface.
#   * watches/, config.toml and backups/ are deliberately NOT bundled: they
#     are writable user data that app_dir() resolves beside the executable
#     (never sys._MEIPASS). Bundling them would put user data inside the
#     read-only _internal/ tree — exactly what §8 forbids.
#   * exclude_binaries=True on EXE + a COLLECT block is what makes this
#     one-folder rather than one-file. §8 forbids --onefile (slow Qt
#     extraction on every launch, and it scatters files outside app_dir()).
#   * upx=False: UPX-compressing Qt's shared libraries is a known cause of
#     load-time crashes, and leaving it on would make the build depend on
#     whether UPX is installed. Off is deterministic and safe.

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('saat/ui/theme.qss', 'ui')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SAAT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SAAT',
)
