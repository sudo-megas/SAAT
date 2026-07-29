; Inno Setup script for SAAT's Windows installer.
;
; Built by .github/workflows/release.yml, never by hand:
;   iscc /DAppVersion=2.1 packaging\windows\saat.iss
;
; The payload is the same PyInstaller one-folder build dist\SAAT that the
; portable .zip is made from -- one build, two artifacts, exactly as the
; Linux tarball and .deb work. Nothing here compiles anything.

#ifndef AppVersion
  #define AppVersion "0.0"
#endif

#define AppName "SAAT"
#define AppPublisher "sudo-megas"
#define AppURL "https://github.com/sudo-megas/SAAT"
#define AppExeName "SAAT.exe"

[Setup]
; A fixed AppId is what makes an upgrade an upgrade rather than a second
; parallel installation, and what Apps & Features keys the entry on. It
; must never change between releases.
AppId={{73186428-7648-4242-A385-73FA55C92EC9}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}/releases
VersionInfoVersion={#AppVersion}

; Per-user, and that is the whole point: PrivilegesRequired=lowest means
; the installer never asks for administrator rights, never shows a UAC
; prompt, and installs somewhere the user already owns. A watch cataloguer
; has no business needing an administrator, and an unsigned installer
; asking for one is exactly the shape of the thing people are right to be
; suspicious of.
;
; {localappdata}\Programs\SAAT, NOT {localappdata}\SAAT -- the latter is
; where the collection lives (paths.py's data_dir()), and the program must
; not be installed on top of the user's data. Keeping them siblings rather
; than nested is what makes "uninstall removes the program, never the
; collection" structurally true rather than a promise.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto

; Upgrade over a running instance: paths.py's per-collection single-instance
; guard keeps the previous version alive, which would leave SAAT.exe locked and
; fail the file replacement. Let Restart Manager close the running instance for
; the duration of the upgrade, scoped to SAAT.exe so nothing unrelated is
; touched, and do not relaunch it afterwards -- a silent upgrade must not pop a
; window. This changes nothing about the data-safety guarantee below.
CloseApplications=yes
CloseApplicationsFilter={#AppExeName}
RestartApplications=no

; Registers the uninstaller in Apps & Features with a real icon and
; publisher rather than an anonymous entry.
UninstallDisplayName={#AppName} {#AppVersion}
UninstallDisplayIcon={app}\{#AppExeName}

SetupIconFile=..\..\saat\resources\icon\saat.ico
LicenseFile=..\..\LICENSE
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
OutputDir=..\..\dist
OutputBaseFilename=SAAT-v{#AppVersion}-windows-x64-setup

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The whole one-folder build.
Source: "..\..\dist\SAAT\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

; SPEC.md §2 rule 2's opt-in marker. Its presence beside the executable is
; the only thing that switches SAAT from portable mode (data beside the
; binary) to installed mode (%LOCALAPPDATA%\SAAT and %APPDATA%\SAAT).
;
; Shipped as an installed file rather than written by a [Code] procedure so
; the uninstaller removes it as a matter of course -- the same reasoning as
; the .deb, which ships it rather than writing it in postinst.
;
; This one line is load-bearing. Without it, an installed SAAT falls back
; to portable mode and tries to keep the collection inside
; {localappdata}\Programs\SAAT. See docs/PLATFORM-AUDIT.md.
Source: "installed-marker"; DestDir: "{app}"; DestName: ".installed"; \
    Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; \
    Flags: nowait postinstall skipifsilent

; ============================================================================
; THERE IS DELIBERATELY NO [UninstallDelete] SECTION, AND THERE MUST NEVER BE
; ONE THAT NAMES THE USER'S DATA.
;
; Uninstalling removes what was installed: {app} and the shortcuts above.
; It does NOT remove, and must never remove:
;
;     %LOCALAPPDATA%\SAAT     the collection -- every watch, every photograph,
;                             every day of wear history, and the backups
;     %APPDATA%\SAAT          window geometry, palette, language, column choices
;
; Neither is under {app}: the program installs to
; %LOCALAPPDATA%\Programs\SAAT, so the collection is its sibling, not its
; child, and Inno's own uninstaller cannot reach it. That is structural, not
; a promise -- but it is also the reason DefaultDirName must never be
; "simplified" to {localappdata}\SAAT.
;
; Uninstalling an application is not consent to delete the data it was used
; to create. This mirrors the .deb's purge behaviour exactly, and it is
; asserted by tests/test_packaging.py rather than remembered.
; ============================================================================
