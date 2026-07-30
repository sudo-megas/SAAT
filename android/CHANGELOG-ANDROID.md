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
`backups/deleted/` reads as a watch to anyone browsing the files. Where the two
trees hold different photographs under the same name, the second is numbered
rather than dropped on top of the first: that folder holds the only copy of each.

**Five ways the storage layer could have lost data, found by going looking for
them and each closed with a test that fails without the fix.**

A `watch.toml` saved as latin-1 rather than UTF-8 used to decode leniently —
`Züblin` read as `Z<?>blin`, no error, a record that looked clean. Because it then
matched what was on disk, byte preservation did not protect it either, and the
first edit wrote the damage back over the original. Not valid UTF-8 is now a load
failure that names the offending byte and its offset, which is what the desktop
already did.

A wear-date toggle skips its snapshot so a calendar gesture cannot fill the 20
shared backup slots — but it regenerates the whole file exactly like any other
save, so on a hand-written file that was one tap against its comments with no
copy kept anywhere. The skip is now a request rather than an instruction: a save
snapshots regardless whenever the file is not already what it would write, which
costs one slot per watch and nothing afterwards. The 20 slots are shared, so one
gesture across more than 20 never-yet-edited watches keeps the newest 20 of those
snapshots and prunes the rest — twenty recovered out of thirty rather than none,
which is the claim and not a word more.

A directory that cannot be listed and a directory with nothing in it are no
longer the same answer. They were, so an unreadable `watches/` read as an empty
collection — and a folder name chosen against a listing that was never taken is a
name already on disk, so the next new watch would have been written straight over
an existing one. A watch that has never been on disk is now refused outright if a
`watch.toml` is already where it would land.

An edit that fails to reach disk stays in memory on purpose. Reading the
collection again used to replace it with the older text still in the file, and
clear the failure notice with it. Nothing loads twice today; AM10's import will.

**And a sixth, in the settings file rather than the storage layer.** A
`config.toml` that would not parse loaded as defaults — correctly, so the app
still starts — and then the next theme toggle wrote those defaults straight over
it. Nothing keeps a copy of this one the way `backups/` does for a watch, so a
chosen language disappeared over a typo not yet fixed. It is moved to
`config.toml.broken` first now. A leading byte-order mark, which is something a
Windows editor adds rather than something anyone did wrong, is stripped on read
so a good config is not mistaken for a broken one.

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
