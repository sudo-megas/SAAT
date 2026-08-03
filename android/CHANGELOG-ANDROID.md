# Changelog — SAAT for Android

Versioning is independent of the desktop app. Android releases are tagged
`android-vX.Y`; the desktop's own tags and changelog are separate history.

## [0.4] - 2026-08-03

Where the owner actually spends time, and the first thing in the app that
writes.

**The detail page is a pure function before it is a screen.** `detailPage()`
turns a record and its media directory into a `DetailPage` — no Context, no
Compose, no clock — so SPEC-ANDROID 5.6's rules are assertions rather than
something to eyeball. "An absent field renders as a muted em-dash inside a shown
group, a wholly empty group is hidden" is a claim about which groups exist and
which rows carry null. A watch with only brand and model produces no spec groups
at all, and that is a test, not a hope.

**Values the owner typed never pass through the resource table.** A string that
needs translating travels as a resource id plus its arguments; a brand, a dial
colour or a note travels as itself. That split is the UI half of hard rule 7 —
storage stays canonical English, and AM11 translates at display time without
touching a single byte on disk.

**Four formatters, every one naming `Locale.ROOT`.** Hard rule 7 is written
about the UI language, but a number formatter that inherits the default locale
breaks the same promise sideways: this owner's Turkish phone would show `41,5
mm` and `1.234,50 TRY` while `watch.toml` still said `41.5`. Every formatting
assertion runs twice, once with the default locale flipped to tr-TR.

**One wear-logging path, and it is in the repository.** `assignWorn(slug,
dates)` is what AM4's button, AM7's calendar, AM8's widget and AM8's shortcut
will all call. It takes a *collection* of dates so a drag-selected range is one
critical section rather than N, and it takes the day as a parameter so nothing
reads a clock where a test cannot see it.

**One watch per day, enforced there and nowhere else.** A day already belonging
to another watch moves, silently, no prompt — the desktop's rule, ported with
its shape intact: days are stripped from their previous owner *before* the
target is written, so no instant on disk has two watches claiming one day. A
non-Owned watch gives up a day it holds too, matching `_strip_dates`, so a sold
watch's stale entry cannot shadow the new one.

**The mutex is not reentrant, and that shaped the code.** A single wear
assignment can touch two watches, so `update()` was split into a locking wrapper
over an unlocked core. A locked method calling the public `update()` would
deadlock the coroutine outright — no exception, no timeout, just a button that
never returns.

**A second tap the same day is a *visible* no-op.** The repository returns what
it did — recorded, already recorded, or moved from a named watch — rather than a
boolean, because those are three different things to tell someone. The file is
not rewritten on a repeat tap, so an idle thumb cannot churn the disk or spend a
backup slot.

**"Worn today", not "0 days ago".** A deliberate divergence from the desktop:
it is the reply to a button the owner has just pressed, and a zero is not what
anyone means by it. A day recorded ahead of today drops the interval from the
line rather than counting backwards.

**Month names are twelve string resources, not `Month.getDisplayName`.** That
call needs a `Locale`, and both available answers are wrong — the default is the
system locale hard rule 7 forbids reading, and `Locale.ENGLISH` would survive
AM11's Turkish sweep untranslated because no entry would exist to translate.

**The back chevron is drawn, not imported.** Material 3 1.4 no longer brings the
icon artifacts in transitively and they are not on the approved dependency list,
so an arrow would have cost a new dependency under hard rule 5 for one glyph.
Six lines of `Canvas`, mirrored under RTL.

**A photo-less watch gets a short tile, not the full 4:5 crop.** Measured on the
phone: a 4:5 box holding two lines of text took three fifths of the first screen
and pushed the brand, the model and every spec below the fold. The grid keeps
4:5 because a mosaic has to stay even; a page does not.

Deferred by the milestone brief, each to AM9: the timing sparkline, the
maintenance-due line, strap compatibility. Timing renders as a plain list and
maintenance shows its raw fields.

## [0.3] - 2026-08-02

The first screen worth looking at. AM2 finished the storage layer and nothing
read it; this is the wire between the two, and the first build worth carrying on
a phone.

**The grid.** Two columns portrait, three landscape, with no upper clamp so a
tablet in landscape is not capped at two. Cards are image-forward — brand as
overline, model as title, style and movement kind beneath — and every card in a
row is the same height *by construction* rather than by luck: a fixed 4:5 image
crop and three text slots whose `minLines` equals their `maxLines`. A one-word
model and a five-word model produce identical cards at any system font scale.

**A watch with no photograph is not an empty grey box.** It gets its diameter
and lug width set in the middle of the tile, and a watch with neither — which is
everything a brand-and-model-only entry can be — renders two muted em-dashes and
still looks deliberate.

**Photographs are read from `media/<slug>/`, not `watches/<slug>/images/`.** The
milestone brief said the latter and was stale: SPEC-ANDROID 3 splits the two
trees on purpose, because Android's Auto Backup rules match paths as literal
prefixes with no wildcards, so "records backed up, photographs not" is only
expressible as two top-level includes. `watches/<slug>/images/` is the shape of
the exported ZIP and nothing else. The brief has been corrected.

**Coil, and only `coil-compose`.** The `coil-network-*` modules carry an HTTP
client whose manifest declares INTERNET; hard rule 2 forbids it and the manifest
guardian would fail the build over it. Nothing here loads a URL. The disk cache
names `cacheDir` explicitly — that is where Coil would have put it anyway, but
hard rule 8 is not a thing to satisfy by inheriting a library default.

**Malformed files are named above the grid, dismissibly.** AM2 already kept a
broken watch in the collection carrying its error instead of quietly dropping
it; this is the part that says so out loud. Dismissal is keyed by file *and*
message, so a reload keeps a dismissed error dismissed while a new error on the
same file appears again. The record standing for an unreadable `watches/`
directory is identified by comparing directories rather than by testing its slug
against the string `watches`, which a real watch could legitimately be called.

**Sort and fuzzy search**, both built in the repository layer rather than in the
composable, because AM6's Specs list reuses them and one implementation is the
point. Search is a subsequence match across brand, model, reference, caliber and
tags, matched *per field* — a concatenated search would let "sksk" borrow
letters from "Seiko" and "SKX007" and return a hit nobody can explain. It case-
folds with the locale-independent `lowercase()`, so a search for `iwc` still
finds `IWC` on the Turkish phone this app is built for. Sort offers Brand,
Model, Acquired (newest first, unknown dates last) and Least worn, and the
choice persists to `config.toml`.

**"Least worn" means longest since last worn**, which is what the phrase already
means in the desktop app — the same sentinel, ported. Every order breaks ties on
the slug so it is total, and the grid cannot twitch between emissions.

**One owner for `config.toml`.** The sort choice made a second writer, and since
a save writes the whole file from one snapshot, two holders would silently
overwrite each other's keys — change the sort, then the theme, and the sort
reverts with nothing thrown. A shared state with a mutex fixes it, the same
shape as the fix the watch repository already carries.

**The demo fixture, and why absence beats a flag.** Hard rule 1 permits exactly
one exception to "no demo watches": a debug-only developer action generating two
watches in code at tap time. It lives in `src/debug`, not behind
`BuildConfig.DEBUG`, because `isMinifyEnabled` is false for release and
flag-guarded code would still ship in the release DEX — a test could then only
ever prove "present but disabled", which is not the claim the rule asks anyone
to make. A Gradle task asserts the fixture is absent from the release variant's
compiled classes and string resources, and is registered on the debug variant
too as a positive control, without which it would pass trivially the day the
fixture is renamed. Both halves were deliberately broken once to confirm they go
red.

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
