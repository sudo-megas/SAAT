# SAAT for Android v1.0

SAAT runs on a phone.

It is the same application — the photo-forward grid, the spec list, the wear
calendar, the detail page, side-by-side comparison — rebuilt natively for the
device that is actually present when a watch goes on your wrist. Your collection
moves between the phone and the desktop app as a ZIP, in both directions,
without either of them owning it.

The desktop app is unchanged. Android versions are tagged and numbered
separately, so this is v1.0 rather than v2.2.

## Installing it

Download `saat-android-1.0.apk` from this release and tap it.

### Android will warn you, and you have to tap past it

Your phone will say the browser (or your file manager) is not allowed to install
apps. To continue:

1. Tap **Settings**
2. Turn on **Allow from this source**, then go back

That is a permission you grant once, to the app you downloaded with — not to
SAAT. It means "this did not come through a store", not "this is known to be
harmful".

It needs Android 8.0 or newer.

## It declares no permissions

Not "only the ones it needs". None at all — no internet, no camera, no storage.

That is possible because every job that would normally need one is done by the
system on the app's behalf: photographs come in through the system photo picker,
the camera through an intent the system fulfils and hands back, and the ZIP
through the Storage Access Framework's own file chooser. In each case the system
does the work and returns the result, so there is nothing for the app to be
granted.

**You do not have to take this on trust.** Long-press the installed app → App
info → Permissions. Every build checks the same claim twice on the way out — once
against the merged manifest and once against the finished APK — and fails rather
than shipping if either ever declares one.

There is no network code in the app at all. The one exception, which is a
hand-off rather than a request, is opening the source repository in your browser
when you tap it in Settings.

## English and Turkish

Both, chosen in Settings, and the choice is explicit: **the app never reads your
phone's language to decide its own.** It starts in English and stays there until
you say otherwise.

The vocabulary is the desktop app's own — the same words for the same parts of a
watch — so a collection read on both does not acquire two names for a lug width.

What is *stored* is always English, whichever language you read. A Turkish
dropdown shows `Otomatik` and writes `Automatic` into the file, because the file
is data that both apps and both languages have to agree on.

## Where your collection lives

In the app's private storage, which no other app on the phone can read:

```
watches/<slug>/watch.toml     the records
media/<slug>/…                the photographs
config.toml                   your settings
backups/                      timestamped copies, newest 20
```

Uninstalling the app removes all of it. **Export first if you mean to keep it.**

### What the cloud backup does and does not cover

Android's own backup carries the **records** and your settings. It does **not**
carry the photographs.

That split is deliberate rather than a limitation. The backup quota is roughly
25 MB; a collection's photographs would exhaust it and take the irreplaceable
half down with the re-takeable half. Records are small and cannot be recreated;
photographs are large and can be taken again.

Moving directly to a new phone carries everything, photographs included, because
a device-to-device transfer has no quota.

## The ZIP bridge

**Settings → Export** writes `saat-export-YYYY-MM-DD.zip` wherever you choose. It
holds exactly the `watches/` tree in the layout the desktop app uses, so
unzipping it into your desktop collection folder *is* the import on that side.
There is no conversion step and no format of ours in between.

**Settings → Import** reads one back. Zip your desktop `watches/` folder — from
above it or from inside it, either works — and watches the phone does not already
have are added. Watches it does have are **skipped, never overwritten**, so
re-importing the same archive is not destructive and cannot lose an edit you made
on the phone. You are told by name what was added and what was skipped.

Files keep their exact bytes in both directions. A comment you hand-wrote in a
`watch.toml` on the desktop is still there after a trip through the phone.

## Logging what you wore

The reason the phone version exists. Three ways in, all recording to the same
place:

- **The home-screen widget** shows today's watch, or says nothing is recorded
  yet. Tap it to pick one; tap a filled one to open that watch.
- **The launcher shortcut** — long-press the app icon → *Wore this today*.
- **The detail page button**, one tap, no dialog.

One watch per day across the collection. Recording a day that already belongs to
another watch moves it, quietly, exactly as the desktop calendar behaves. Past
and future days are equally editable; future days are how you plan.

## Known limits

- **Comparison is two watches, not four.** The desktop compares up to four
  because it has the width for it. A phone held upright does not.
- **A hand-written file's comments survive until its first edit on the phone.**
  The desktop preserves them through an edit; this does not, and saying so is
  better than implying otherwise.
- **No emulator smoke test in the release pipeline.** The APK is checked with
  `apkanalyzer` instead — manifest, permissions, launchability, size — and
  installed by hand on a real phone before release.

## Licence

GPL-3.0, the same as the desktop app.
