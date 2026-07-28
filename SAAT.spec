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
#     fonts at `resources/fonts/`, the app icon at `resources/icon/`, and
#     the ten palette TOML files at `resources/palettes/`. When frozen,
#     resource_dir() returns sys._MEIPASS, so these dest paths must match
#     exactly what theme.py / main.py join onto resource_dir().
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

#   * Platform-aware in exactly one place, at the bottom: a Windows
#     VERSIONINFO resource. Everything else here was already portable and
#     was left alone. datas uses the tuple form, so there is no ':' versus
#     ';' separator problem; console=False was already correct (a windowed
#     app must not have a console flash up behind it on Windows, and the
#     flag is a no-op on Linux); and icon= already points at the .ico,
#     which Windows uses for the executable and Linux ignores.
#
#   * --onedir on every platform. §8 forbids --onefile on Linux for
#     reasons that hold at least as strongly on Windows: it re-extracts the
#     whole Qt runtime to %TEMP% on every launch, which antivirus
#     real-time scanning makes slower still, and it puts application files
#     outside the folder portable mode keeps its data in.

import sys

# A Windows executable with no VERSIONINFO shows blank Details in its file
# properties and gives SmartScreen nothing to identify it by. It does not
# make the binary trusted -- only a code-signing certificate does that, and
# milestone 24 deliberately does not attempt one -- but an unsigned binary
# that also refuses to say what it is is worse than an unsigned binary that
# does. Generated from saat.__version__ so it cannot drift.
version_resource = None
if sys.platform == 'win32':
    import os
    sys.path.insert(0, os.path.abspath('.'))
    import saat

    parts = saat.__version__.split('.')
    while len(parts) < 4:
        parts.append('0')
    numeric = ', '.join(parts[:4])

    os.makedirs('build', exist_ok=True)
    version_resource = os.path.join('build', 'version_info.txt')
    with open(version_resource, 'w', encoding='utf-8') as handle:
        handle.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({numeric}), prodvers=({numeric}),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
    date=(0, 0)),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'sudo-megas'),
        StringStruct('FileDescription', 'SAAT - Watch Collection Manager'),
        StringStruct('FileVersion', '{saat.__version__}'),
        StringStruct('InternalName', 'SAAT'),
        StringStruct('LegalCopyright',
                     'Copyright (C) 2026 sudo-megas. GPL-3.0-or-later.'),
        StringStruct('OriginalFilename', 'SAAT.exe'),
        StringStruct('ProductName', 'SAAT'),
        StringStruct('ProductVersion', '{saat.__version__}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('saat/ui/theme.qss', 'ui'),
        ('saat/resources/fonts', 'resources/fonts'),
        ('saat/resources/icon', 'resources/icon'),
        ('saat/resources/icons', 'resources/icons'),
        # Ten fixed presets (SPEC.md §6/§9), read via tomllib at runtime from
        # resource_dir() -- a missing file here fails loudly the first time
        # theme.palettes() is touched, not silently.
        ('saat/resources/palettes', 'resources/palettes'),
        # Only .qm files are ever present here (see .gitignore) -- the .ts
        # sources this directory also holds in the working tree are the
        # lupdate-maintained originals, never read at runtime. qtbase_*.qm
        # (Qt's own dialog-chrome strings) needs no entry here: PyInstaller's
        # PySide6 hook bundles it automatically, since QtCore always pulls
        # translations=["qt", "qtbase"] in as a transitive dependency.
        ('saat/resources/i18n', 'resources/i18n'),
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
    version=version_resource,
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
