# SAAT — Watch Collection Manager

SAAT catalogues a wristwatch collection on your own computer: a photo-forward grid,
a dense spec table, a wear calendar, a detail page per watch, and side-by-side
comparison. Every watch is a plain TOML file in a folder you own — no database, no
network, no account, nothing that expires.

![SAAT's first screen: an empty collection](docs/images/empty-state-dark.png)

It ships empty on purpose. Entering the collection is the hobby; the app is the
framework, not the contents.

## Install

Everything below is on the
[releases page](https://github.com/sudo-megas/SAAT/releases/latest).

### Windows 10 and 11

Download `SAAT-v2.1-windows-x64-setup.exe` and run it.

**Windows will warn you, and you have to click past it.** The installer is not code
signed, so SmartScreen shows a blue box saying *"Windows protected your PC"* with
only a **Don't run** button visible. To continue:

1. Click **More info**
2. Click **Run anyway**

That warning means "this publisher has not paid for a certificate", not "this file
is known to be harmful". A code-signing certificate is a few hundred dollars a year
and this is a free hobby project; if that trade bothers you, the whole thing is
source-available and you can build it yourself.

The installer needs **no administrator rights** — it installs just for you, into
`%LOCALAPPDATA%\Programs\SAAT`, and adds a Start Menu entry (a desktop shortcut is
offered as an option). Uninstall from Settings → Apps in the normal way.

**Uninstalling never deletes your collection.** It lives in `%LOCALAPPDATA%\SAAT`,
which is beside the program directory rather than inside it, so the uninstaller
cannot reach it.

There is also a portable `.zip` if you would rather not install anything — extract
it and run `SAAT.exe`. In that mode your collection lives inside the extracted
folder, so you can keep the whole thing on a USB stick.

### Debian, Ubuntu, Mint and derivatives

Download `saat_<version>_amd64.deb` and install it:

```sh
sudo apt install ./saat_2.1-1_amd64.deb
```

SAAT then appears in your application menu. There is nothing else to set up.

The package carries its own Qt and Python, so it does not care which version of
either your distribution ships — the trade is size, about 230 MB installed, almost
all of it Qt. It needs glibc 2.35 or newer, which means Debian 12+, Ubuntu 22.04+
and anything more recent.

To remove it:

```sh
sudo apt remove saat        # or: sudo apt purge saat
```

**Neither touches your collection.** `~/.local/share/saat` and `~/.config/saat` are
left exactly as they are, purge included. That is asserted automatically on every
release build, not merely intended.

### Every other Linux distribution

Download the `.tar.gz`, extract it, and run it:

```sh
tar -xzf SAAT-v2.1-linux-x86_64.tar.gz
./SAAT/SAAT
```

That folder is self-contained and fully portable — it carries its own Qt and Python
runtime and needs nothing installed. Copy it to a USB stick or another machine and
your collection travels inside it, because in this mode SAAT keeps `watches/`,
`config.toml` and `backups/` **beside the executable** rather than in your home
directory.

Built on Ubuntu 22.04, so it runs on anything with glibc 2.35 or newer: Ubuntu
22.04+, Debian 12+, Fedora 36+, Mint 21+, and current Arch.

There is also an [`install.sh`](install.sh) for a system-wide install on
distributions without `apt` — see [docs/BUILDING.md](docs/BUILDING.md).

## Where your data lives

This is the part worth reading. SAAT never puts your collection anywhere you cannot
find it, and never puts it anywhere but your own machine.

| | Portable (the tarball or `.zip`) | Installed |
|---|---|---|
| watches, backups — Linux | beside the executable | `~/.local/share/saat/` |
| configuration — Linux | beside the executable | `~/.config/saat/` |
| watches, backups — Windows | beside the executable | `%LOCALAPPDATA%\SAAT\` |
| configuration — Windows | beside the executable | `%APPDATA%\SAAT\` |

Each watch is its own folder under `watches/`, holding a `watch.toml` and an
`images/` subfolder:

```
watches/<slug>/
├── watch.toml
└── images/
    ├── main.jpg
    └── strap-nato.jpg
```

`watch.toml` is a plain text file you can open in any editor.
[`watches/_template.toml`](watches/_template.toml) documents every field, and
comments you write into a watch file survive the app saving over it. Before any
destructive change the previous version is copied into `backups/` (newest 20 kept),
and deleting a watch moves its whole folder to `backups/deleted/` rather than
erasing it.

Which mode you are in is decided by a `.installed` marker file beside the
executable, which only a package or `install.sh` ever creates. A plain copy of the
portable folder is always portable — it can never silently relocate your collection
into your home directory.

`SAAT_DATA_DIR` overrides both locations at once.

Nothing is uploaded, synced or phoned home. SAAT opens no network socket at all; the
only things that ever leave it are a URL handed to your browser when you click a
link, and a PDF if you ask for one.

## What it does

- **Grid** — cards led by the watch's own photograph, reflowing to the window width.
- **Table** — dense and sortable, with column presets matching the data model:
  identity, movement, case, dial, straps, acquisition.
- **Calendar** — record what you wore, by month, week or year. The year view colours
  each day by watch, which is how you find out what you actually reach for; stats
  mode ranks rotation, coverage and streaks over a period.
- **Detail page** — the photograph at proper size, full specifications, service and
  timing history, a wear strip, and which of your other straps physically fit it.
- **Compare** — two to four watches side by side, with a to-scale drawing of their
  cases, their accuracy ranges on one axis, and bars for the numbers that differ.
- **Wishlist** — a second scope for watches you do not own yet, with target prices,
  and one click to move one into the collection when you buy it.
- **Ten palettes**, English and Türkçe, a system tray, and PDF export of whatever
  you are looking at.

## Build it yourself

See [docs/BUILDING.md](docs/BUILDING.md) — running from a clone, building the
portable folder with PyInstaller, and building the `.deb`. [`SPEC.md`](SPEC.md) is
the full design specification and is authoritative.

## Licence

SAAT is free software, licensed under the
[GNU General Public License v3.0](LICENSE) or later.

It is built on [PySide6](https://pypi.org/project/PySide6/), which is licensed under
the LGPL-3.0. Builds keep Qt as separate shared libraries rather than statically
linking them, which is what the LGPL's dynamic-linking terms call for.

The bundled Ubuntu Sans, Ubuntu Sans Condensed and Ubuntu Mono fonts are licensed
under the [Ubuntu Font Licence 1.0](saat/resources/fonts/LICENCE.txt).

The grid view's card-reflow layout (`saat/ui/flow_layout.py`) is adapted from Qt's
own "Flow Layout" example (BSD-3-Clause); the full notice is at the top of that
file.

The `.deb` additionally redistributes the Qt, CPython and C libraries its bundle
carries. Every one of them is accounted for in
[`packaging/debian/copyright`](packaging/debian/copyright), and the package ships a
manifest of exactly what it contains at
`/usr/share/doc/saat/bundled-libraries.txt`.
