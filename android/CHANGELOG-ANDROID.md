# Changelog — SAAT for Android

Versioning is independent of the desktop app. Android releases are tagged
`android-vX.Y`; the desktop's own tags and changelog are separate history.

## [0.1] - 2026-07-29

The scaffold. Nothing visible beyond an empty four-tab shell, which is the
point — the decisions that hurt to revisit are made first, while the diff is
still small enough to read.

The application id is `io.github.sudomegas.saat`, fixed permanently. Kotlin,
Jetpack Compose and Material 3 on `minSdk 26`, targeting API 37.

**The app declares no permissions, and something enforces that.** A Gradle task
parses the merged manifest for both the debug and the release variant on every
`check`, and fails the build if any permission appears — merged rather than
hand-written, so a dependency cannot smuggle one in. It caught one immediately:
androidx.core injects a self-defined signature permission that would otherwise
have shipped. Verified on the built APK itself, where `aapt dump permissions`
prints the package name and nothing else.

**Cloud backup covers the records and never the photographs.** Android's backup
rules cannot express "everything in `watches/` except each watch's images" —
the format has no wildcards — so photographs live in their own `media/` tree and
the rule becomes two static lines that cannot fall out of step with the schema.
The on-disk layout changed; the ZIP bridge to the desktop app did not. A useful
side effect: phone-to-phone transfer has no quota, so it carries the
photographs too, while a cloud restore carries the records.

The theme ports the desktop's palette rather than inventing an Android one —
the same seven roles, the same contrast thresholds measured by the same WCAG
implementation, including the one shortfall the desktop accepted deliberately.
Dynamic colour follows the wallpaper on Android 12 and later, with a switch in
Settings to turn it off and get the SAAT palette back. Light and dark both work.

Settings persists to `config.toml` beside the collection, in the same plain
TOML the watches themselves use. A file that cannot be read falls back to
defaults and says so on screen rather than failing quietly.

The launcher icon is the desktop's mark, redrawn to survive Android's icon
masking, with a monochrome version for themed icons on Android 13 and later.
