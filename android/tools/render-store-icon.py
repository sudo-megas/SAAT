#!/usr/bin/env python3
"""Render the store icon from the app's own adaptive launcher icon -- AM12.

IzzyOnDroid's inclusion policy wants an icon in the fastlane metadata, and this
repository has no raster to give it: `mipmap-anydpi-v26/ic_launcher.xml` is an
adaptive icon over two VectorDrawables and there are no PNG mipmaps anywhere, on
purpose. So the icon is rendered from those two drawables rather than drawn, and
this script is the only thing that should ever write
`fastlane/metadata/android/en-US/images/icon.png`.

WHY NOT THE DESKTOP'S saat.png. It is a different composition: the Android
foreground is the desktop mark scaled 0.60x about the centre, because Android
crops launcher icons to a device-chosen mask that would otherwise take the ring,
all four markers and the crown. Shipping the desktop raster as the phone app's
icon would show a listing that does not match what installs.

THE CONVERSION IS AN ATTRIBUTE RENAME. VectorDrawable's `pathData` is already
SVG path syntax; `fillColor`, `strokeColor`, `strokeWidth` and `strokeLineCap`
are the SVG attributes under different names. Nothing is reinterpreted, so what
comes out is what the launcher draws.

The one trap, and it is not cosmetic: VectorDrawable defaults an unset fill to
NONE, SVG defaults it to BLACK. Left implicit, every stroke-only path here --
the case ring and both hands -- renders as a filled black blob. Both defaults
are therefore written out explicitly below.

Needs `rsvg-convert` (librsvg). Run from the `android/` directory:

    tools/render-store-icon.py
"""
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ANDROID = "{http://schemas.android.com/apk/res/android}"

RES = Path("app/src/main/res/drawable")
LAYERS = (RES / "ic_launcher_background.xml", RES / "ic_launcher_foreground.xml")
DEST = Path("fastlane/metadata/android/en-US/images/icon.png")

# 512 is what both repositories list, and the 108x108dp viewport scales to it
# by a clean factor rather than resampling anything.
SIZE = 512


def svg_paths(vector: Path) -> list[str]:
    """Every <path> in one VectorDrawable, as SVG."""
    out = []
    for path in ET.parse(vector).getroot().iter("path"):
        data = path.get(f"{ANDROID}pathData")
        if not data:
            continue
        # fill and stroke are written even when absent -- see the module docstring.
        attrs = [
            f'd="{data}"',
            f'fill="{path.get(f"{ANDROID}fillColor", "none")}"',
            f'stroke="{path.get(f"{ANDROID}strokeColor", "none")}"',
        ]
        for android_name, svg_name in (
            ("strokeWidth", "stroke-width"),
            ("strokeLineCap", "stroke-linecap"),
        ):
            if value := path.get(f"{ANDROID}{android_name}"):
                attrs.append(f'{svg_name}="{value}"')
        out.append("  <path " + " ".join(attrs) + " />")
    return out


def main() -> int:
    missing = [str(p) for p in LAYERS if not p.is_file()]
    if missing:
        print(f"not found: {', '.join(missing)} -- run this from android/", file=sys.stderr)
        return 1

    # Background first, then foreground: the platform's own layer order.
    body = "\n".join(p for layer in LAYERS for p in svg_paths(layer))
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'width="108" height="108" viewBox="0 0 108 108">\n'
        f"{body}\n</svg>\n"
    )

    DEST.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["rsvg-convert", "-w", str(SIZE), "-h", str(SIZE), "-o", str(DEST)],
            input=svg.encode(),
            check=True,
        )
    except FileNotFoundError:
        print("rsvg-convert not found -- install librsvg", file=sys.stderr)
        return 1

    print(f"{DEST}: {SIZE}x{SIZE}, from {' + '.join(p.name for p in LAYERS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
