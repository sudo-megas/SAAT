# Changelog — SAAT for Android

Versioning is independent of the desktop app. Android releases are tagged
`android-vX.Y`; the desktop's own tags and changelog are separate history.

## [1.0] - 2026-08-03

The first public release. Turkish, signing, a tag-triggered workflow, and a
README written for somebody who will sideload an APK and deserves to know
exactly what it does and does not do.

**Turkish is not a translation layer bolted on at the end.** It cost so little
here because AM1 forbade a literal in a composable and AM5 built `EnumChoice`
with the stored value and the shown label as separate fields — so a Turkish
dropdown writes the same English `watch.toml` the desktop reads, and always
would have. The vocabulary is the desktop's own: all 99 enum labels and 129 of
the interface strings come verbatim from `saat_tr.ts`, so a collector reading
the two apps sees one vocabulary rather than two opinions about what a lug is
called.

**A file written under one language loads identically under the other, and now
a test says so under a real Turkish locale.** This is the case worth having:
`"I".lowercase()` in Turkish gives `ı`, and `String.format` writes `3,5` for
three and a half — which is not valid TOML. A phone set to Turkish could have
written files the desktop could not read, and the failure would have looked
like corruption rather than like a locale bug.

**Enum values translate on the detail page too, resolved per field.** The same
English word is a different thing in different fields — "Other" is a group and
a style, "None" a bezel and an indices — so a flat value-to-label map would pick
whichever it met first and produce quietly wrong Turkish for the other. Free
text keeps no label and reaches the screen as typed, because what the owner
typed is their word rather than the app's vocabulary.

**Nothing secret is in this repository and nothing can be.** The signing config
reads four values from the environment or from Gradle properties; `.gitignore`
has excluded keystores since AM1, before there was one to be careless with; and
a test now checks what `.gitignore` cannot — a file added with `git add -f`, or
a password pasted into the build script. Every other mistake in this project is
recoverable. A signing key that reaches a public repository is not, and Android
does not allow rotating one.

**The release build stays buildable without the keystore.** An unconditional
signing config fails at configuration time on every machine that does not have
it, which is every contributor's. So its absence produces an *unsigned* release
APK — and the workflow verifies the signature with `apksigner` afterwards,
because "the build succeeded" is then not evidence that anything was signed.

**The dry run is the point of the workflow's second trigger.** It builds, signs
and verifies exactly as a tag does, and publishes nothing. A tag is public and
awkward to retract; the desktop learned that first.

**No emulator smoke test, said plainly.** Booting an AVD is several minutes and
the flakiest thing a release pipeline can hold — a release that fails because an
emulator did not come up teaches nobody anything. `apkanalyzer` answers the
questions that matter about the artefact from the artefact itself, including
re-asserting the zero-permission claim against the built APK rather than only
against the merged manifest.

## [0.10] - 2026-08-03

The release gate. The ZIP is not a backup feature — it is the contract that the
phone and the desktop hold the same collection, and the proof that the owner's
data is never trapped in either.

**The re-root is the whole job.** On the phone photographs live in a sibling
`media/<slug>/` tree, because Android's Auto Backup rules match `path` as a
literal prefix with no wildcards at all and "back up the records, never the
photographs" is not otherwise expressible. The archive puts them back at
`watches/<slug>/images/`, which is the desktop's exact layout. The phone's
internal split is an implementation detail; the archive is the contract.

**Bytes are copied, never re-serialised — in both directions.** A `watch.toml`
enters the archive exactly as it sits on disk, and an imported one lands exactly
as it arrived: parsed only to decide whether to accept it, with the decoded
value thrown away. Byte preservation would be pointless if the one operation
that moves data between machines rewrote every file on the way. A hand-written
comment survives the whole journey, and a test asserts it by looking for the
comment rather than by comparing fields.

**Import validates in a separate pass, before touching disk.** `ZipInputStream`
cannot seek, so the archive is opened twice: pass one surveys every entry name,
refuses the whole file if any is unsafe, and reads the small `watch.toml`s so a
malformed one is found before a byte is written; pass two streams the
photographs. A per-entry check made while extracting could only promise to stop
halfway — the test for this puts a traversal entry beside a perfectly good watch
and asserts the good watch did not land either.

**On symlinks, honestly.** The brief asks for them to be rejected and the
platform's zip API gives no way to see one — the bit lives in the central
directory's external attributes, which `java.util.zip.ZipEntry` does not expose,
and a library that does would cost a dependency. What is done instead makes it
moot: every entry is written through a path this code builds itself, so a
symlink entry extracts as an ordinary file containing the text of its target and
creates no link at all. That is asserted rather than claimed.

**Both archive roots are accepted, decided per entry.** Desktop users zip from
above `watches/` and from inside it. Deciding the shape once for the whole
archive would need a tie-break for a mixed one; per entry needs none, and a
watch legitimately slugged `watches` survives it.

**An existing slug is skipped whole** — the owner's decision. Not merged, not
overwritten, not renamed to `-2`: anything else puts the archive's opinion of a
watch above the one being edited here. All four outcomes are named rather than
counted, because "already here" and "would not parse" are not the same news.

**The round-trip test is the release gate and says so at the top of the file.**
A desktop-shaped fixture with full schema coverage — straps, log, worn, timing,
a Turkish dotted İ, a non-ASCII brand and a hand-written comment — imports,
exports, and comes back byte-identical file for file. Byte-identity of the
FILES, not of the archive: entry order and timestamps are properties of the
container rather than of the collection.

**And it is checked against the desktop app itself, not only against us.** An
export both written and read by this codebase would round-trip perfectly even if
its layout were something the desktop had never heard of. So CI now opens the
exported archive with `saat.storage.load_collection` — the desktop's real code —
and the desktop's own writer produces an archive that the import path here has
to accept. Both directions were run on a development machine before this landed.

**The backup rules were already right; now they are guarded.** Nothing at
runtime reads them, so nothing at runtime could notice them going wrong — and
the failure only surfaces when an owner restores a phone. The include-only rule,
the records-only cloud list and the photographs-included device transfer each
have an assertion now.

## [0.9] - 2026-08-03

Feature-completeness for v1: the screen for deciding what to wear, and the three
small intelligences that make the catalogue smarter than a spreadsheet.

**Compare pairs rows by label, never by index.** The detail page's movement rows
are conditional — a mechanical watch gets `power_reserve_hours` and a quartz
gets `battery_life_years` — so the two lists differ in length and position N is
not the same attribute on both sides. Zipping them would have put a 72-hour
power reserve opposite a 2-year battery life, classified the pair as differing,
and been confidently wrong on both rows. A two-pointer merge keyed on the label
puts each figure on its own row and lands a one-sided row where its own side
puts it, so an automatic against a quartz reads `… power reserve, battery life,
accuracy …` rather than stranding the battery figure at the foot of the group.

**Compare calls the detail page's row builders rather than restating them.** The
brief is explicit that this screen "must not become a second implementation of
value display", so a formatting fix made for one arrives at the other for free.
Only two builders are new, and both exist because compare needs what a header
line cannot give: identity as labelled rows, and the *fitted* strap rather than
the whole list — comparing "3 straps" against "1 strap" tells the owner nothing.

**Zero is always folded into the timing sparkline's range.** Ported from the
desktop rather than reinvented, and this is the decision a fresh implementation
gets wrong: without it the reference line leaves the chart whenever a watch
never crosses zero, and a line wiggling inside an auto-scaled box looks the same
whether it is ±0.5 sec/day or ±30. It costs vertical detail on a consistently
fast watch and buys the only comparison the chart is for. The x axis is the
reading's index rather than its date for the mirror reason — readings come three
in a week after a service and then not for a year, and true spacing would crush
that cluster into a smear.

**The maintenance line's silence is the feature.** Nothing when there is no
Service entry to project from, nothing when the interval is blank, nothing when
the date is comfortably ahead. Most watches will never carry an interval and a
catalogue that nagged about them is one the owner stops opening. A test asserts
that a watch serviced in 1998 with no interval recorded says nothing at all.

**`battery_due` gets the same treatment, so the notice is a list.** The brief
says "a single line", which is about not building a banner; a watch that
legitimately has both a service and a battery due would otherwise have one of
them suppressed — the page knowing something it does not say. The accent dot
fires on either clock, and overdue and due-soon look identical on the card on
purpose: a grid that graded its warnings would be a grid that nags.

**Strap compatibility is the desktop's rules, all four of them.** Both sides
must be Owned — swapping only makes sense between watches physically on hand —
and a strap with no width of its own matches on its owner's lug width, which is
what makes the feature find anything at all in a real collection where most
straps never get a figure typed in. Nothing is deduplicated: two identical 20 mm
leather straps on two watches are two straps to reach for, and collapsing them
would hide where the second one is.

**No charting dependency.** The sparkline is a `Canvas`, a `Path` and nine lines.

## [0.8] - 2026-08-03

From this build, logging today never requires opening the app.

**The widget is plain RemoteViews, not Glance — and that is this milestone's
real finding.** SPEC-ANDROID 2.1 approves Glance for exactly this, so Glance is
what was built first. It cannot be used: every published version declares
`androidx.work:work-runtime`, and `GlanceAppWidget`'s *constructor* resolves
`androidx.work.CoroutineWorker`. Excluding the dependency and running it on a
real phone gave `NoClassDefFoundError` before a pixel was drawn.

Keeping WorkManager costs two hard rules at once — WAKE_LOCK,
ACCESS_NETWORK_STATE, RECEIVE_BOOT_COMPLETED and FOREGROUND_SERVICE (rule 2,
caught by the manifest guardian the moment Glance went in) and `androidx.sqlite`
(rule 4, by name). The hard rules are non-negotiable; §2.1 is a budget written
before anyone checked what Glance drags in. **SPEC-ANDROID 2.1 should be
corrected**, the way AM3 corrected the media path.

**RemoteViews costs no dependency at all,** and the APK still declares zero
permissions — verified on the installed build, not just in the merged manifest.
Dark mode and Android 12+ dynamic colour come from `values-night/` and
`values-v31/` resources, which is the only way a layout inflated in the
launcher's process can reach a theme.

**Midnight is one inexact alarm, not a heartbeat.** `setExact` needs
SCHEDULE_EXACT_ALARM from API 31, and a widget that turns over a few minutes
into the new day is a fair price for a permission list anyone can verify is
empty. It re-arms on every draw, so a reboot repairs itself with no boot
receiver, and DATE_CHANGED / TIME_SET / TIMEZONE_CHANGED cover the cases an
alarm cannot see.

**Update-on-change is observed once, in the Application** — one collection, one
place that outlives every screen.

**Tapping opens the picker, not the app shell.** A lightweight activity hosting
AM7's own picker sheet; dropping the owner on the grid to navigate to a calendar
would give back the whole point at the last step. The click handler sits on the
*root* view, which the phone taught: a photo-less watch hides the ImageView, and
tapping the blank half fell straight through to the launcher.

**Two static shortcuts,** static so they work on a cold start — the launcher
reads them from XML and no app code has to have run first.

**Exactly one implementation of one-watch-per-day, and a test that says so.**
There are now four ways to record a day — detail button, calendar picker, widget
and shortcut — and all four reach `WatchRepository.assignWorn`. A second copy
would not fail anything; it would simply drift.


## [0.7] - 2026-08-03

The most satisfying screen in the app, and the one whose desktop interaction
grammar translates least.

**The index is built in memory, at load, from each watch's own `worn` list.** No
central log — the brief forbids centralising it "for efficiency", and the reason
is that a watch folder stays a complete record: deleting a watch takes its days
with it for free, the ZIP needs no second file, and a hand-edited `watch.toml`
cannot disagree with an index nobody can see.

**Monday-first, and not from the locale.** Deriving the first day of the week
from the system locale would be reading the system locale to decide the
interface — hard rule 7, arriving through a door nobody thought to close.

**Blanks are blanks.** A grid showing the 31st of last month above the 1st
invites tapping it, and every tap would silently edit a month you are not
looking at.

**A watch with no photograph fills its cell with its own hue.** Found by
sideloading: the demo pair carries no photographs by design, which made every
worn day indistinguishable from an empty one. The derivation is the desktop's
exactly — crc32 of the slug's UTF-8 bytes, modulo 360 — because `hashCode()` is
a *different* function and a collection opened on both platforms would colour
the same watch two different ways.

**Range mode replaces click-drag rather than imitating it.** A drag across a
calendar competes with the scroll, and a drag starting on a cell competes with
the tap. Long-press anchors a span, each tap extends it, and a bar shows the day
count with Cancel and Pick watch — because a long press with no visible
consequence reads as a missed tap.

**One sheet for every case,** because tapping an empty day, tapping a filled day
and finishing a span are the same question: which watch was on the wrist.
Picking is one tap with no confirm, and the one-per-day rule moves the day off
another watch *silently* — the brief forbids prompting, and a calendar you have
to argue with never gets a year of backlog entered.

**The rule itself is not reimplemented.** Assigning goes straight through AM4b's
`assignWorn`; the whole of the reuse is one call.

**The footer names the watches you did not wear.** Days recorded and distinct
watches are both visible by looking at the grid — the brief is candid that the
third figure is the only one that tells the owner something new, so it lists
them rather than counting them. No streaks, no badges, no goals.

**The year view is twelve compact grids of colour chips,** the same hue a watch
gets anywhere else. At that size a photograph would be four pixels of brown; a
hue is legible, and recognising "that green one again" across twelve months is
the only thing the view is for. Tapping a month opens it.


## [0.6] - 2026-08-03

The desktop's table and its filter sidebar, rethought for a hand.

**The Specs list is a preset switcher, not a table.** A chip row — Identity,
Movement, Case, Dial, Straps, Acquisition — and one row per watch beneath. The
desktop's columns could not survive a six-inch portrait screen, but the point of
them could: studying the whole collection against one family of attributes at a
time.

**Every cell is built by AM4's own row builders.** A preset is a *selection*
from `movementRows`, `caseRows`, `dialRows` and `acquisitionRows`, not a second
set of field definitions — so the em-dash, the metres-with-bar water resistance,
the derived hertz and the Quartz/Solar swap all behave here because they are the
same code. Sort and search are AM3's, unchanged, for the same reason.

**One cell per column, always.** The fully-populated fixture proved this is not
free: `movementRows` emits both a power reserve and a battery life when a watch
records both, which made one row a cell wider than its neighbour. A column that
changes width by row is exactly the misalignment a preset exists to prevent.

**Labels reserve two lines whether they need them or not.** Measured on the
phone in two passes: at one line "Lug-to-Lug" and "Water Resistance" truncate;
at "up to two" they wrap, but then "Diameter" takes one line and its figure sits
a line above its neighbour's. `minLines == maxLines` is the same trick the grid
card uses to keep cards the same height — alignment by construction rather than
by luck of the vocabulary.

**One filter, shared by every screen that narrows the collection.** Owned by the
Application, not by a ViewModel, so a facet picked on the Grid is already picked
on Specs and AM7's calendar picker joins by reading it rather than growing its
own. Not persisted — the same judgement AM3 made about the search query: a sort
is a preference, a filter is a question you are asking right now.

**A facet's counts ignore its own selection.** Having picked Diver, the Style
facet still says how many Field watches are one tap away, while the other facets
narrow as you go. Counting against the fully-filtered set would show 0 beside
everything you had not picked, and a zero that only means "you did not pick
this" teaches nothing. Values stay visible at zero rather than vanishing, so the
sheet never appears to lose options.

**Facets with no values are hidden entirely,** so an empty collection shows only
the summary footer — and a collection where nobody recorded a case material is
not offered a Case material heading with nothing under it.

**Active filters are chips under the top bar.** A collection quietly showing
three of eleven watches, with nothing on screen saying why, is a collection that
appears to have lost eight.

**The collection summary is plain figures.** Watch count, split by movement
kind, total acquisition value by currency — computed over the *filtered*
collection, because it is the footer of the sheet doing the filtering. A price
with no currency is counted under no currency rather than folded into TRY, which
would invent a fact about what was paid.

## [0.5] - 2026-08-03

The app stops being read-only. From this build the phone is a full SAAT.

**One scrolling form, not tabs.** SPEC-ANDROID 5.7 gives the reason rather than
leaving it to taste: tabs on a phone hide what is unfilled, and a scroll shows
the whole shape of the record. Collapsible group headers in spec order, all open
to begin with. The same screen serves add and edit.

**Every numeric field is a string, and the rest follows.** A number being typed
passes through states that are not numbers — `4`, `4.`, `4.5`, a lone minus on
the way to `-5`. A model holding `Double?` would either refuse those keystrokes
or put something else back in the field mid-type, and both are what people mean
when they say a form fights them. Parsing happens once, at save.

**Saving with only brand and model succeeds, and nothing else can block.** That
is the whole of validation, it is one line, and it is tested. A diameter of
"abc" and a rating of 900 still save — the first is absent afterwards, the
second written as given. The collection is always partly incomplete; a form that
argued about it would not get used.

**The unsaved-changes prompt compares state, not signals.** The desktop sets a
dirty flag from widget signals, so typing a character and deleting it still
prompts — and a prompt that fires when nothing changed is one people learn to
dismiss without reading. Comparing *built watches* would fail the other way and
let someone walk away from text that will never parse. Structural inequality
against the opening state is right in both directions.

**Ninety-nine enum\* values, generated from one table** into both the Kotlin
lists and `strings.xml`, because that is exactly the size at which two
hand-maintained copies drift — invisibly, in English. The value and its label
are different things: the canonical English string reaches `watch.toml`, the
resource is what AM11 translates. Every list is editable and also offers what
the collection already uses, because the spec says the owner will buy something
it did not anticipate.

**Those strings are data, so CI now diffs them against the desktop's own
source.** A value respelled on one side fails nothing — not the field map, not a
round trip, not a unit test. It just means the two apps offer different
vocabularies for one field and a collection edited on both grows two spellings
of everything. All 99 match.

**Photographs are copied, never referenced.** A `content://` URI is a temporary
grant to someone else's file; it dies with the process and dies for good when
the owner clears the gallery app's data. A collection whose photographs are
borrowed empties itself over a year.

**Bytes are copied verbatim — no decode, no re-encode.** That *is* how EXIF
orientation is honoured: the tag stays in the file and Coil applies it at
decode, exactly as the desktop's Pillow does. Baking rotation in would be lossy
and would change a file the desktop also reads. The test builds a real JPEG in
code, with a real orientation tag, and asserts both byte-identity and the tag's
survival — no new dependency needed for the stronger claim.

**Still zero permissions, verified on the installed APK.** The Photo Picker and
`ACTION_IMAGE_CAPTURE` both need none, and the FileProvider is scoped to one
directory inside `cacheDir`: a camera app handed a URI from here can reach
nothing else. `watches/` is outside the provider's world entirely — there is no
URI that names it.

**Photographs stage in `cacheDir` until the watch is saved.** A new watch has no
slug until it has been written once, and backing out of the form must leave the
collection exactly as it was. An abandoned capture costs nothing.

**Delete moves, it does not destroy.** Both folders — record and photographs —
go to `backups/deleted/`, rejoined into the shape the desktop and the exported
ZIP both use. The wear history goes with them for free, because `worn` lives in
the watch's own file and nowhere else; that is the payoff for never having
centralised a date index. The guard is an exact typed model name, matching the
desktop, with autocorrect and autocapitalisation turned off so the keyboard
cannot quietly retype it.

**The debug two-watch fixture stays** for the rest of the development cycle, as
the brief asks, and its release-absence check still passes now that a real form
exists.

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
