# Fastlane metadata — AM12

The listing text for the two repositories SAAT is submitted to. Both read this
structure directly out of the git tree: [IzzyOnDroid][izzy] requires it, and
F-Droid picks it up from the same layout.

```
metadata/android/<locale>/
├── title.txt              ≤ 30 characters
├── short_description.txt  ≤ 80 characters
├── full_description.txt   ≤ 4000 characters
├── changelogs/<versionCode>.txt
└── images/
    ├── icon.png           512×512
    └── phoneScreenshots/  ← the one thing not in this commit
```

`en-US` and `tr-TR`, because those are the app's two languages and nothing here
should claim a third. The changelog file is named for the **versionCode**, not
the versionName — `2.txt` is v1.0, and the next release writes `3.txt`.

## The icon is rendered from the app's own vectors

`images/icon.png` is `ic_launcher_background.xml` composited under
`ic_launcher_foreground.xml` at 512×512 — the same two drawables the launcher
gets, not the desktop app's `saat.png`, which is a different composition at a
different scale. `tools/render-store-icon.py` regenerates it, and that script
is the only thing that should ever write it.

This is the repository's one raster file, and it does not weaken the rule that
put the comment in `mipmap-anydpi-v26/ic_launcher.xml`. That rule protects
`app/src/main/res/`, which stays raster-free; metadata images are never a build
input, so F-Droid still compiles the app from source with nothing prebuilt.

## Screenshots are the owner's to take — hard rule 1

**Not in this commit, and not obtainable by anyone but the owner.** Hard rule 1
of `SPEC-ANDROID.md` reserves them: *"Screenshots come from the owner's real
collection, taken by the owner — never fabricated."* Generating them, mocking a
collection for them, or reusing `docs/images/polish/*` (those are the desktop
app, and reusing them is the borrow case the rule also forbids) are all out.

Drop the files into `en-US/images/phoneScreenshots/`, named so they sort into
the order they should be read in:

| File | Screen |
|---|---|
| `01_grid.png` | The grid, showing enough watches to fill it |
| `02_detail.png` | A detail page, on a watch with photographs and a filled spec block |
| `03_calendar.png` | The wear calendar on a month with days actually logged |
| `04_compare.png` | Two-up compare, on two watches worth comparing |

Four is the minimum the milestone names. The specs list and the home-screen
widget are both worth adding if you want them; keep the numbering contiguous.

**How to take them.** From the phone, at its native resolution, with no
scaling, cropping or device frame — PNG, and between 320px and 3840px on every
side, which any modern phone satisfies without help. Dark mode, since that is
what the icon and the app's own plate colour are built around. `adb exec-out
screencap -p > 01_grid.png` takes them losslessly over USB and avoids the
screenshot-key overlay animation.

For `tr-TR/images/phoneScreenshots/`, the same four with the app set to
Turkish. If you would rather not take a second set, delete that directory
entirely rather than symlinking or copying the English ones — a locale with no
screenshots falls back to `en-US`, which is correct, whereas English
screenshots labelled Turkish are a small lie.

[izzy]: https://izzyondroid.org/docs/general/AppInclusionPolicy/
