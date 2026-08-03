# Third-party licences

SAAT itself is **GPL-3.0-or-later** — the full text is in [`LICENSE`](../LICENSE) at the
repository root, and it is what actually governs. This file accounts for the other
people's work that SAAT redistributes.

It lives here rather than in the README because the README is for somebody deciding
whether to install a watch catalogue, and this is for somebody checking a licence claim.
Neither is served by mixing them. **Nothing here is optional reading if you redistribute
SAAT** — the LGPL in particular carries obligations that travel with the binary.

## Qt, via PySide6

The desktop application is built on [PySide6](https://pypi.org/project/PySide6/), which is
licensed under the **LGPL-3.0**.

Builds keep Qt as **separate shared libraries** rather than statically linking them, which
is what the LGPL's dynamic-linking terms call for: you can replace the Qt SAAT ships with
your own build of the same version, which is the freedom that clause exists to protect.

## Fonts

The bundled **Ubuntu Sans**, **Ubuntu Sans Condensed** and **Ubuntu Mono** are licensed
under the [Ubuntu Font Licence 1.0](../saat/resources/fonts/LICENCE.txt), whose text ships
alongside them.

## The grid's flow layout

`saat/ui/flow_layout.py` — the card-reflow layout behind the Grid view — is adapted from
Qt's own "Flow Layout" example, **BSD-3-Clause**. The full notice sits at the top of that
file and must stay with it.

## The Android application

`/android` shares no code with the desktop app and has its own dependency tree: **160
libraries, every one of them Apache-2.0**, verified POM by POM against the set AGP records
as actually packaged. The audit, including the one artifact that declares no licence of
its own and inherits Apache-2.0 from its parent, is in
[`../android/docs/ANDROID-DISTRIBUTION.md`](../android/docs/ANDROID-DISTRIBUTION.md).

## The Debian package

The `.deb` additionally redistributes the Qt, CPython and C libraries its bundle carries.
Every one is accounted for in
[`../packaging/debian/copyright`](../packaging/debian/copyright), and the package ships a
manifest of exactly what it contains at `/usr/share/doc/saat/bundled-libraries.txt` — so
the list can be checked on an installed system rather than only against this repository.
