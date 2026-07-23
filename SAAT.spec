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
#   * datas ships the read-only resources theme.py and main.py resolve
#     through resource_dir(): the QSS theme at `ui/`, the vendored Ubuntu
#     fonts at `resources/fonts/`, and the app icon at `resources/icon/`.
#     When frozen, resource_dir() returns sys._MEIPASS, so these dest paths
#     must match exactly what theme.py / main.py join onto resource_dir().
#   * icon= on EXE sets the executable's own icon — meaningful on
#     Windows/macOS, a no-op on Linux (where the running window's icon comes
#     from setWindowIcon() reading resources/icon/saat.png at runtime, not
#     from the binary itself). Harmless to set now, saves a step later.
#   * watches/, config.toml and backups/ are deliberately NOT bundled: they
#     are writable user data that data_dir()/config_dir() resolve beside the
#     executable in portable mode (never sys._MEIPASS) — or under the OS's
#     standard per-user locations in installed mode; see SPEC.md §8.
#   * exclude_binaries=True on EXE + a COLLECT block is what makes this
#     one-folder rather than one-file. §8 forbids --onefile (slow Qt
#     extraction on every launch, and it scatters files outside data_dir()).
#   * upx=False: UPX-compressing Qt's shared libraries is a known cause of
#     load-time crashes, and leaving it on would make the build depend on
#     whether UPX is installed. Off is deterministic and safe.

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('saat/ui/theme.qss', 'ui'),
        ('saat/resources/fonts', 'resources/fonts'),
        ('saat/resources/icon', 'resources/icon'),
    ],
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
    icon='saat/resources/icon/saat.ico',
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
