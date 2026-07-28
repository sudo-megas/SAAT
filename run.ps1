# The Windows counterpart of run.sh: create .venv if absent, install the
# pinned runtime dependencies into it, launch main.py.
#
#   .\run.ps1
#
# If PowerShell refuses to run it, Windows is blocking unsigned local
# scripts. Either run it once as
#   powershell -ExecutionPolicy Bypass -File .\run.ps1
# or allow local scripts for your own user permanently with
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
#
# One deliberate difference from run.sh, and the reason this is a separate
# file rather than something clever: run.sh exports
# QT_QPA_PLATFORM=wayland, and this does not set QT_QPA_PLATFORM at all.
# That hint exists because the target Linux desktop is Wayland and Qt would
# otherwise sometimes pick the X11 backend. On Windows there is one
# platform plugin, Qt selects it correctly, and forcing anything is at best
# redundant and at worst breaks the app outright. Nothing in saat/ reads
# this variable -- it is a launcher concern on both platforms.
$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

if (-not (Test-Path '.venv')) {
    python -m venv .venv
}

# requirements.txt is the only place the runtime dependencies are named --
# run.sh and both CI workflows install from it too, so a developer's venv
# and a release build get identical versions.
& .\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
& .\.venv\Scripts\python.exe -m pip install --quiet -r requirements.txt

& .\.venv\Scripts\python.exe main.py
exit $LASTEXITCODE
