# Android verification — AM9, AM10, AM11

The things CI cannot check, because they need a phone in a hand. Nobody has
done any of these yet.

**When you have the phone: paste this whole file back to me with the results
block at the bottom filled in.** `PASS`, `FAIL` or `SKIP` on each line, plus
whatever you saw. One word is fine; a screenshot of anything odd is better.

The APK is the `saat-debug-apk-<sha>` artifact on the latest **Android CI** run
for this branch:
<https://github.com/sudo-megas/SAAT/actions?query=branch%3Aworktree-am9-am11>

Download it, unzip, sideload the `.apk` inside. Takes about twenty minutes to
work through, and the demo fixture does most of the setup for you.

**Set-up, once:** Settings → scroll to the bottom → **Add demo watches**. That
generates the mechanical one (straps, log, worn days, timing readings) and the
quartz one (almost nothing) in code. Nothing is written to the repository and
nothing is bundled; it is the sanctioned fixture from hard rule 1.

---

## AM9 — compare, timing, maintenance, strap fit

### 1. Selection mode and the contextual bar

Long-press a grid card.

- Pass: the card takes an accent border, the top bar is replaced by one reading
  **1 selected** with **Clear selection** and a greyed-out **Compare**.
- Pass: tapping a second card enables Compare; tapping a third drops the first
  rather than doing nothing.
- Pass: the system back gesture leaves selection mode instead of leaving the
  screen.
- Fail: a tap during selection opens the watch instead of toggling it.

### 2. Compare reads at a glance — **the one I most want checked**

Select the two demo watches, tap Compare.

- Pass: two columns under a header that **does not scroll away**, so you can
  always tell which watch is which.
- Pass: rows where the two agree are visibly dimmer than rows where they differ.
  The point is that you can find the differences by scanning down without
  reading anything.
- Pass: **Power Reserve and Battery Life are two separate rows**, adjacent, each
  filled on one side and em-dashed on the other. This is the thing most likely
  to be subtly wrong; if the two figures share a row, that is a FAIL and an
  important one.
- Pass: rows neither watch has are absent entirely, not shown as two dashes.

Check it in **both light and dark** — the dimming has to survive both.

### 3. Timing sparkline

Open the mechanical demo watch, scroll to Timing.

- Pass: a small chart above the readings, with a horizontal rule (zero) and a
  line crossing or sitting above/below it.
- Pass: the quartz watch shows **no chart at all** (it has fewer than three
  readings) — the section is either absent or shows readings only.
- Fail: the chart is a flat line pinned to an edge, or clipped.

### 4. Maintenance line and the accent dot

The demo mechanical watch may or may not be due, depending on the dates it
generates.

- Pass: **if** a service or battery is due within 90 days, one line at the top
  of the detail page says so with a date, and the grid card carries a small
  accent dot.
- Pass: **if nothing is due, there is no line and no dot at all.** Silence is
  the specified behaviour and is the thing worth confirming — a watch with no
  service interval must never nag.

### 5. Strap compatibility

Both demo watches need the same lug width for this to show anything; if it does
not appear, edit one watch's `lug_width_mm` to match the other and add a strap.

- Pass: a **Straps that fit** section listing the other watch's strap, naming
  which watch it is on.
- Pass: tapping it opens that watch, and back returns to where you were.

---

## AM10 — the ZIP bridge

**This is the release gate. If anything here fails, v1.0 does not ship.**

### 6. Export

Settings → Data → **Export ZIP**. Save it somewhere you can find (Downloads).

- Pass: it completes and names the file and the counts — how many watches, how
  many photographs.
- Pass: the filename is `saat-export-<today's date>.zip`.

### 7. The archive opens on the desktop — the actual contract

Copy the ZIP to the computer and unzip it into a **scratch copy** of your
desktop collection folder (not the real one, first time).

- Pass: the tree is `watches/<slug>/watch.toml` and `watches/<slug>/images/…`.
- Pass: **the desktop app opens that folder and shows the watches**, with fields
  and photographs intact.

CI already proves this against the desktop's own loader on every build. What
CI cannot prove is that it works with the real app on your machine.

### 8. Import, from the desktop

Zip your desktop `watches/` folder and put it on the phone.

- Pass: Settings → Import → pick it → it reports **n added, n skipped**, both
  named.
- Pass: watches already on the phone are listed as skipped and are **not**
  changed — open one you had edited on the phone and confirm your edit survived.
- Pass: importing the **same file twice** adds nothing the second time.

### 9. A photograph survives the whole trip

- Pass: a watch with a photo, exported and unzipped on the desktop, still has
  its photo there and it opens.

---

## AM11 — Turkish, and the release build

### 10. Turkish, every screen

Settings → Dil/Language → **Türkçe**.

- Pass: the interface changes immediately, without restarting the app.
- Pass: walk **every** screen — grid, specs, calendar, detail, compare, the
  add/edit form, settings, the filter sheet — and nothing is left in English.
- **Report any string that overflows or gets cut off with "…".** Turkish runs
  longer than English and the buttons and top-bar titles are where it will show
  first. This is the check the milestone specifically asks for.
- Pass: enum values read Turkish too — a movement kind should say **Otomatik**,
  not Automatic, on the detail page as well as in the form dropdown.

### 11. Turkish does not change what is stored

With the app in Turkish, edit a watch and set its movement kind from the
dropdown, then save. Export, and open the `watch.toml` in a text editor.

- Pass: the file says `kind = "Automatic"` **in English**, even though the
  dropdown showed Turkish.
- Fail: anything Turkish in the file. That would mean the desktop and the phone
  no longer agree about what a collection says, and it is the most serious
  possible failure in this milestone.

### 12. The language does not follow the phone

- Pass: set the phone's own system language to Turkish while the app is set to
  English. The app **stays English**. That is hard rule 7 and it is deliberate.

**Do this on Android 13 or newer, and the check is not the screen alone.** This
failed the first time it was ever run, and it could only fail there: below API 33
the per-app locale is an AppCompat static that works from anywhere, while on 33+
it belongs to the framework and the app has to hand it over. An older phone
passes this check trivially while a newer one is broken, so a PASS from a
pre-33 device proves nothing about the devices anyone is using.

Confirm the framework agrees, not just the screen:

```
adb shell cmd locale get-app-locales io.github.sudomegas.saat
```

- Pass: `[en]` — the app asserted its language and the system recorded it.
- Fail: `[]` while `config.toml` says `en`. That is the bug this check exists
  for, and the interface will be in the phone's language.

### 13. Widget and shortcut still work

These are AM8's and should be unaffected, but the wear path was touched.

- Pass: the widget shows today's watch or "Nothing recorded today".
- Pass: the launcher long-press shortcut **Wore this today** records, and the
  calendar shows it.

**Check the widget's language separately from the app's, with the app set to
English.** It is not covered by item 12 and was wrong when 12 was fixed: a
widget's layout is inflated in the LAUNCHER'S process, so any string it draws
from `@string/` is resolved against the DEVICE's language and this app is never
asked. Clear today's watch from the picker to make the empty state appear —
that is the only string the widget owns.

- Pass: it reads "Nothing recorded today" while the phone is in Turkish and the
  app is in English.
- Fail: "Bugün için kayıt yok" beside an English app.

---

## Results

Run on 2026-08-03, driven over adb against the debug APK built from this branch.

```
 1. selection mode                    : PASS
 2. compare, both themes              : PASS
    power reserve / battery separate  : PASS
 3. timing sparkline                  : PASS
 4. maintenance line + dot (or silent): PASS  (both branches)
 5. strap compatibility               : PASS
 6. export completes                  : PASS
 7. archive opens on the desktop      : PASS  (desktop loader, not the GUI)
 8. import, skip-existing             : PASS
 9. photograph survives the trip      : PASS
10. Turkish, every screen             : FAIL -> FIXED, retested PASS
    strings that overflow             : SKIP  (needs eyes — see below)
11. storage still English             : PASS
12. app ignores the phone's language  : FAIL -> FIXED, retested PASS
13. widget and shortcut               : FAIL -> FIXED, retested PASS

phone model / Android version         : HONOR ELP-NX9 / Android 16 (API 36)
anything that looked wrong            : eight defects, all fixed — below
```

**The phone's own language is Turkish**, which is why item 12 was a live test
rather than a setup step, and why so much of this was visible at all.

### What each line means

**1, 3, 5, 6, 9 — passed as written.** Compare is disabled at one selection and
enabled at two; a third pick drops the first (confirmed by opening compare and
seeing which two arrived); a tap during selection toggles instead of opening; the
system back leaves selection mode without leaving the grid. The mechanical demo
draws a sparkline matching its three readings and the quartz one has no Timing
section at all. `Straps that fit` names the watch the strap is on and opens it.
Export names the file and the counts, and a photograph came back with an
identical md5 under `watches/<slug>/images/`.

**2 — passed, and measured rather than eyeballed.** Power Reserve and Battery
Life are two separate adjacent rows, each filled on one side and em-dashed on
the other. The demo fixture could not show this on its own — the quartz watch
carries no battery life — so one was added to exercise it. "Agreeing rows are
dimmer" was measured off the screenshots instead of judged: agreeing rows render
their glyphs at luminance 70 against 28 for differing rows in light, and 198
against 226 in dark. Consistent to the value, in both themes.

**4 — passed on both branches, which needed arranging.** With nothing due there
is no line and no dot, and silence is easy to mistake for a broken feature, so a
battery due date inside the 90-day window was added: the line appears with its
date and the accent dot appears on that card only.

**7 — passed against the desktop's real loader.** The archive was unzipped and
read with `saat.storage.load_collection`, which is the contract this check names.
Every field arrived WITH ITS TYPE — `battery_due` as a date rather than a string,
which is the failure that would otherwise have waited for a real transfer. The
desktop GUI itself was not launched; that part is still worth a minute of your
own time.

**8 — passed, including the part that matters.** An archive was built holding
both demo watches and a new one, with the colliding watch's model deliberately
changed. It reported `1 watch added, 2 skipped`, both named; the phone's copy
kept its own model; and importing the same file again added nothing.

**10 — failed, fixed, retested.** Every screen was walked in Turkish: grid,
specs, calendar, detail, compare, the add/edit form, settings and the filter
sheet. The chrome was already complete. The VALUES were not — the grid card, the
specs list, the detail header and the filter sheet all printed schema enum
values in English while the compare screen translated the same fields. Now
consistent everywhere.

**The overflow question is the one thing here still owed to a person.** Nothing
was observed truncated, but "observed" means a script read the text, and a label
that is clipped or ellipsised still reports its full string to an accessibility
dump. The Turkish screenshots are attached to the session; the honest answer is
that this needs your eyes, particularly on the top-bar titles and the form's
buttons.

**11 — passed, and re-verified after the display changes.** With the interface
fully Turkish an export writes `kind = "Automatic"`, `status = "Owned"`, `style =
"Field"`, `material = "Leather"`, `clasp = "Pin Buckle"` — no Turkish anywhere in
any `watch.toml` — and the desktop read all three watches back without error.

**12 — failed outright, and this is the one worth knowing about.** With
`config.toml` saying `en`, on a Turkish phone, every screen came up Turkish.
`AppCompatDelegate.setApplicationLocales` is called from `Application.onCreate`
exactly as intended, but on API 33+ it finds the framework's LocaleManager by
walking its live AppCompat Activities — and in `onCreate` there are none, so it
returns having done nothing at all. No exception, no log. Hard rule 7 had been
broken on every Android 13+ device for the whole life of this release, with 557
unit tests green, because the test guarding it is a source scan and the call it
looks for was present and was being made. Now `[en]` is asserted through the
framework and the interface stays English.

**13 — the shortcut passed; the widget did not, for a third reason.** `Wore this
today` opens the picker without opening the app, records the day, moves it off
the watch that previously held it, and the calendar and detail page both follow.
The widget shows today's watch, updates the moment the assignment changes, and
falls back to its empty state — but it said `Bugün için kayıt yok` beside an
English app, because a widget's layout is inflated in the LAUNCHER'S process and
resolves `@string/` against the device's language. Fixed and retested.

### State the phone was left in

The demo watches were cleared and regenerated so they carry the corrected
spellings, the imported test watch and the test archives were removed, and
Settings were put back as found — English, System theme, dynamic colour on, sort
by brand, Identity preset. **One thing was added and left there: the today
widget is now on the home screen**, since check 13 required pinning it. Remove it
if you would rather not have it.

---

## Still needed from you, separately from the phone

1. **Generate the release keystore.** The exact `keytool` command is in
   `docs/ANDROID-RELEASING.md`. I have deliberately not generated one — it is
   yours to make and to keep, and losing it means never being able to update the
   app for anyone who installed it.
2. **Add the three GitHub secrets** once the keystore exists:
   `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_PASSWORD`.
3. **Screenshots**, from your real collection — grid, detail, calendar, compare,
   dark mode, native resolution. Hard rule 1 reserves these for you; the README
   has a comment marking where they go.
4. **The tag itself.** `android-v1.0` is not cut and no release exists. AM11's
   own rule forbids tagging before AM10 is green on `master`, and this work is
   on a branch. Merge first, then dry-run the release workflow manually, then
   tag.
