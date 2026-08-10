# Distributing SAAT for Android — AM12

Where the app goes after the GitHub release, what each channel demands, and what
has actually been verified rather than assumed.

`docs/ANDROID-RELEASING.md` covers the keystore, the secrets and cutting the
release itself. This document starts where that one ends.

## Status, as of this commit

**v1.1 is released on GitHub. Screenshots are taken. Neither store channel is
submitted yet — that step needs the owner's own accounts on Codeberg and
GitLab, which nothing in this repository can act on.**

| Channel | Status |
|---|---|
| GitHub Releases | **Live** — [`android-v1.1`][rel], `saat-android-1.1.apk`, 9.89 MiB |
| IzzyOnDroid | Not submitted — nothing outstanding on our side; filing the issue is the owner's action |
| F-Droid | Not submitted — recipe has both versions' real commit hashes; filing the RFP and opening the merge request are the owner's action |

Screenshots exist for both `en-US` and `tr-TR` at
`android/fastlane/metadata/android/<locale>/images/phoneScreenshots/`, taken
from the owner's real collection per hard rule 1 — a real HONOR ELP-NX9, dark
mode, native resolution, `adb exec-out screencap`.

[rel]: https://github.com/sudo-megas/SAAT/releases/tag/android-v1.1

The release was cut from `0c68a6e` on 2026-08-03 by the tag-triggered workflow,
after a `workflow_dispatch` dry run proved the signing path — which earned its
keep immediately by failing on an empty `ANDROID_KEYSTORE_BASE64` before a tag
had been spent on it.

Verified against the published artifact after download, not against the build
that produced it:

- `apksigner verify` passes. One signer, `CN=sudo-megas, O=SAAT`, RSA, APK
  Signature Scheme v2, certificate SHA-256 `e32594ad7a0d3191…`.
- `apkanalyzer manifest permissions` returns nothing, and the binary manifest
  contains no `uses-permission`, no `debuggable` and no `testOnly`.

**Both remaining blockers are now IzzyOnDroid's and F-Droid's own preconditions
rather than ours.** The screenshots are still the owner's to take (hard rule 1),
and the F-Droid recipe's `commit:` can now be filled with the real hash, since
the tag it names finally exists.

SPEC-ANDROID 9 puts these in a deliberate order, and it is a dependency chain
rather than a preference:

```
keystore  →  GitHub secrets  →  merge to master  →  tag  →  GitHub release
                                                              ↓
                                            IzzyOnDroid (takes the built APK)
                                                              ↓
                                            F-Droid (builds from source itself)
```

Everything up to and including the GitHub release is done:

1. ~~Generate the release keystore.~~ Done. It lives outside this repository and
   always must — **back up the `.jks` and its password offline if that has not
   happened yet. Losing them means never being able to ship an update to anyone
   who installed the app**, because Android refuses an update signed by a
   different key.
2. ~~Add the three GitHub secrets.~~ Done.
3. ~~Take the screenshots.~~ Done for both `en-US` and `tr-TR`, hard rule 1
   satisfied — the owner's real collection, on a real phone. **Filing the
   actual submissions is what remains**, and it stays the owner's action; see
   the per-channel sections below for exactly what to send.
4. ~~Merge to `master` and tag `android-v1.0`, then `android-v1.1`.~~ Done, in
   that order, each time.
5. ~~The release workflow produces the signed APK.~~ Done for both — and both
   are published.

### `versionCode 2` is spent, and nothing enforces the next one

Android decides whether an APK is an update by comparing `versionCode` as an
integer, and nothing else — `versionName` is a label it never reads for this.
v1.0 shipped as `versionCode 2` (v1.1 shipped as `3`, correctly bumped), so
**the next release must set 4 or higher or
it will not install over v1.0 for anybody.**

`VersionGuardTest` does not catch this. It asserts that `versionCode` is a
positive integer and that `versionName` matches the newest
`CHANGELOG-ANDROID.md` heading — both of which stay true when the integer is
never touched. A release that bumps `versionName` to 1.1, writes the changelog
entry and forgets the code therefore passes every gate in this project and then
fails silently on the phone, which is the same shape of failure the guard was
written to prevent. Bump both.

## What was actually verified

Measured against the release build at this commit, not recalled:

| Claim | How it was checked | Result |
|---|---|---|
| APK size within IzzyOnDroid's limit | `app-release-unsigned.apk` on disk | **9.9 MiB** (10,337,215 bytes) against a 30 MB rule of thumb |
| No permissions requested | `verifyReleaseManifestPolicy` on the merged manifest, plus an independent scan of the APK's own binary manifest | No `uses-permission` element; no `INTERNET` |
| Not debuggable, not testOnly | String-pool scan of the APK's `AndroidManifest.xml` | Both absent |
| No proprietary dependencies | The POM of every one of the 160 libraries AGP records as packaged | All Apache-2.0 (below) |
| No proprietary blobs | `unzip -l` over the APK | One native library, `libandroidx.graphics.path.so`, from AndroidX — Apache-2.0 |
| License is `GPL-3.0-or-later` | Source headers say "either version 3 … or (at your option) any later version" | Not `GPL-3.0-only`; the SPDX field must carry the suffix |

### The dependency set, enumerated rather than summarised

The declared dependencies in `libs.versions.toml` are eight lines long, and that
number is worth ignoring: what ships is the **transitive closure**, which is
**160 libraries across 59 group IDs**. Auditing the eight would have checked
about five percent of what a reviewer downloads.

The list comes from `app/build/outputs/sdk-dependencies/release/sdkDependencies.txt`,
which is AGP's own record of what it packaged — not a resolution done separately
and hoped to match. Every one of the 160 had its POM read from the local Maven
cache; all 160 were found, so nothing is unaccounted for.

| Namespace | Libraries | License |
|---|---|---|
| `androidx.*` (42 group IDs) | 116 | Apache-2.0 |
| `org.jetbrains.*` (11 group IDs) — kotlin stdlib, kotlinx coroutines and serialization, Compose Multiplatform, JetBrains lifecycle/savedstate | 29 | Apache-2.0 |
| `io.coil-kt.coil3:*` | 8 | Apache-2.0 |
| `dev.eav.tomlkt:*` | 2 | Apache-2.0 |
| `com.squareup.okio:okio`, `okio-jvm` | 2 | Apache-2.0 |
| `com.google.accompanist:accompanist-drawablepainter` | 1 | Apache-2.0 |
| `org.jspecify:jspecify` | 1 | Apache-2.0 |
| `com.google.guava:listenablefuture:1.0` | 1 | Apache-2.0, inherited — see below |

`junit` is EPL-1.0 and does not appear above because it is a test dependency and
is not packaged. The list confirms that: it is not in the 160.

**The one artifact with no licence of its own.** `com.google.guava:listenablefuture:1.0`
declares no `<licenses>` block. It is not an oversight and not a risk: the POM
inherits from `com.google.guava:guava-parent:26.0-android`, which is Apache-2.0,
and the artifact contains exactly one 358-byte interface —
`com.google.common.util.concurrent.ListenableFuture` — carved out of Guava so
that a project needing only that type does not pull all of Guava. Named here
because a reviewer running a licence scanner will get a hit on it and deserves
the answer without having to ask.

**Two absences worth stating, since both were once present.** `androidx.glance`
and everything AM8 rejected it for — `androidx.work`, `androidx.sqlite` — are
not in the packaged set, nor are `room`, `datastore`, Firebase, Google Mobile
Services or Crashlytics. Hard rule 4 forbids sqlite by name and F-Droid's
inclusion policy forbids Firebase and GMS by name, so both were checked against
the packaged list rather than against the dependency block, which is where a
transitive one would hide.

And `okio` ships while `okhttp` does not. Coil pulls Okio for its file I/O; the
`coil-network-*` modules that would bring an HTTP client are deliberately not
depended on, which is what keeps `INTERNET` out of the manifest. Square's name
appearing in the list is not the network library arriving.

### The one thing that looks like a permission and is not

An APK scan finds the string `android.permission.DUMP`, and anyone checking the
zero-permission claim the hard way will find it. **The app does not request it.**

It appears as `android:permission="android.permission.DUMP"` on AndroidX's
`ProfileInstallReceiver`, which AGP adds along with the baseline profile. That
attribute *guards* a receiver — it says only a caller holding DUMP (the shell,
the system) may broadcast to it. Requesting a permission is `<uses-permission>`,
a different element, and the merged release manifest has none.

Worth knowing because the README invites people to verify the claim themselves,
and this is the one string that could make an honest checker think it was false.

## Anti-features — verified, none apply

F-Droid's labels are not disqualifying, but claiming none apply is a claim, so
each was checked rather than dismissed as a set:

| Anti-feature | Applies? | Why |
|---|---|---|
| Ads | No | Nothing in the dependency tree serves any |
| Tracking | No | The app has no network access at all |
| Non-Free Network Services | No | It depends on no service |
| Tethered Network Services | No | Same |
| Non-Free Dependencies | No | Every shipped dependency is Apache-2.0 |
| Non-Free Addons | No | It promotes nothing |
| Non-Free Assets | No | The icon is this project's own vector work; text uses system fonts |
| Disabled Algorithm | No | The keystore is RSA-4096 in PKCS12 — `ANDROID-RELEASING.md` |
| Known Vulnerability | No | Nothing flagged; their scanners have final say |
| No Source Since | No | Source is the repository the recipe points at |

## IzzyOnDroid

Takes the APK straight from GitHub Releases and follows new tags within about a
day, which makes it the low-friction channel and the one to do first.

Their [inclusion policy][izzy-policy] asks for: a FOSS licence with public
source, no proprietary components, an APK signed with a release key and carrying
neither `debuggable` nor `testOnly`, roughly 30 MB or less, and fastlane
metadata in the app's own repository with at least a short description, full
description, icon and screenshots.

Every one of those is now satisfied — the table above, plus real screenshots at
`android/fastlane/metadata/android/en-US/images/phoneScreenshots/`.

**The submission is the owner's action.** Once the release exists:

1. Confirm the release page shows a **signed** APK. An unsigned one is an
   automatic rejection, and this build produces an unsigned release APK silently
   when the keystore is absent — by design, so ordinary builds work, which also
   means a missing secret fails quietly here rather than loudly.
2. Open an issue on their maintenance repository:
   **<https://codeberg.org/IzzyOnDroid/repodata/issues>**
3. Give them: the package name `io.github.sudomegas.saat`, the source URL
   <https://github.com/sudo-megas/SAAT>, the releases URL, and the licence.
   Mention that fastlane metadata is at `android/fastlane/metadata/android/` —
   **not** at the repository root, because the desktop application owns the top
   level. That is the one thing about this repository that will not match their
   default expectation.

[izzy-policy]: https://izzyondroid.org/docs/general/AppInclusionPolicy/

## F-Droid

Builds from source on their own servers and signs with their own key, so
inclusion is a stronger statement than IzzyOnDroid's and costs more to get.

The recipe is drafted at **`android/fdroid/io.github.sudomegas.saat.yml`**, with
its reasoning in comments, and now carries a `Builds:` entry per tagged release
— `1.0` and `1.1` — each with its real 40-character commit hash, since both
tags exist. Both entries share the field most likely to be wrong on the first
build:

- `subdir: android/app`. **This repository's gradle root is `android/`, not the
  repository root**, because the desktop application owns the top level — so
  `gradlew` and `settings.gradle.kts` sit one level above the module. If their
  builder cannot find them, `android` is the fallback to try.

Two properties of this project happen to suit them well, neither by accident:

- **The release build does not need the keystore.** `app/build.gradle.kts`
  configures signing only when the material is present and produces an unsigned
  APK otherwise, which is exactly what a build server that signs with its own key
  requires. No `prebuild` step is needed to strip a signing block.
- **Nothing is prebuilt.** `buildSrc` is Kotlin source in-tree, there are no
  committed JARs or AARs, and the launcher icon is vector — so there is no
  binary for them to object to.

**Submitting is the owner's action**, and F-Droid wants both halves:

1. File an RFP at **<https://gitlab.com/fdroid/rfp/issues>**, stating the
   package name, source URL, licence, and that you are the author and want it
   included.
2. Fork [`fdroiddata`][fdroiddata], copy the drafted YAML to
   `metadata/io.github.sudomegas.saat.yml` with the two fields above filled in,
   let their CI build it, and open a merge request labelled **New App**. The
   merge request is what actually moves it; the RFP alone sits in a queue.

**Honestly: their queue takes as long as it takes** — weeks to months is normal
and there is nothing to do about it but wait. Because they compile from source
rather than trusting the APK, any build problem surfaces at this step and not
before. If their recipe needs gradle changes, those become AM12 fix commits, and
if any of them is user-visible, an `android-v1.0.1`.

[fdroiddata]: https://gitlab.com/fdroid/fdroiddata

## The README rule

**The README's Android section gains an install channel only once that channel
is actually live** — not when submitted, not when accepted-in-principle. AM12
says so and the desktop project's standing rule says so.

There was a debt here, and cutting the release paid it rather than any edit
doing so. README.md told people to download `saat-android-1.0.apk` from the
releases page and said the Android builds are tagged `android-v1.0`, at a point
when neither the tag nor the release existed — true only in the future tense,
and the exact thing this milestone forbids. Both now exist, and the asset is
named `saat-android-1.0.apk` exactly as the README says, so the sentence is
true as written and needs no change.

IzzyOnDroid and F-Droid still get no mention there, and must not until each is
actually live.
