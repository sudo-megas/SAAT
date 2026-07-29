# Changelog — SAAT for Android

Versioning is independent of the desktop app. Android releases are tagged
`android-vX.Y`; the desktop's own tags and changelog are separate history.

## [0.2] - 2026-07-29

The storage layer. No user-visible change — the app still shows four empty
tabs — but everything above this point is furniture and this is the floor.

**A watch.toml the desktop app wrote loads here with every field intact, and a
file written here loads there.** That is not a claim, it is a build step. The
desktop's storage layer has no GUI dependency, so CI installs one package and
runs the desktop's *actual* loader and writer against what Android produces, in
both directions, on every push. It also reads the desktop's dataclasses by
reflection and diffs them against the field map the Android encoder really
emits, so a schema field that is missing, renamed or misspelled fails the
Android build rather than surfacing as an empty row three milestones later. It
currently reports 66 fields mapping in both directions. Both halves of the check
were deliberately broken once to confirm they go red.

**Absence is a value.** Every optional field is nullable and none default to 0
or "", because an absent field renders as a muted em-dash and the UI can only do
that if the model can tell "not measured" from "measured as zero".

**A file you hand-edit is not rewritten until you edit that watch in the app**,
so comments in a hand-written file survive until then — and are lost at that
point, because a Kotlin TOML writer regenerates a file rather than editing it in
place the way the desktop's does. That limit is written down rather than papered
over.

**One bad field costs one field.** A `watch.toml` you edited by hand is expected,
so `rating = "4"` reads as 4 and `diameter_mm = 41` reads as 41.0, while a value
nothing can make sense of leaves that field absent and reports itself by name.
Only two things stop a watch loading at all: TOML that will not parse, and a
missing brand or model. A file that fails still appears in the collection
carrying its error instead of quietly disappearing.

Slugs are ported from the desktop clause by clause rather than redesigned, since
a slug generated differently on each platform is a watch that duplicates itself
the first time a collection moves. That includes the Turkish dotless-i trap,
which is the live case here rather than the theoretical one: a locale-sensitive
lowercase turns `Seiko` into `seko` on a Turkish phone and nowhere else. Three
expectations in that test were wrong when written and were corrected against
measured desktop output, not the other way round.

Deleting moves a watch instead of erasing it, and rejoins its record and its
photographs into one folder shaped exactly like a desktop watch — so what is in
`backups/deleted/` reads as a watch to anyone browsing the files.

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
