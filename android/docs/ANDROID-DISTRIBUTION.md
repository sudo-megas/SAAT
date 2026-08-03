# Distributing SAAT for Android — AM12

Where the app goes after the GitHub release, what each channel demands, and what
has actually been verified rather than assumed.

`docs/ANDROID-RELEASING.md` covers the keystore, the secrets and cutting the
release itself. This document starts where that one ends.

## Status, as of this commit

**Neither channel is submitted, and the app is not yet released anywhere.** Said
plainly because the alternative is a document that reads as though it were.

| Channel | Status |
|---|---|
| GitHub Releases | Not cut — no `android-v1.0` tag exists |
| IzzyOnDroid | Not submitted — blocked on the release |
| F-Droid | Not submitted — recipe drafted, blocked on the release |

SPEC-ANDROID 9 puts these in a deliberate order, and it is a dependency chain
rather than a preference:

```
keystore  →  GitHub secrets  →  merge to master  →  tag  →  GitHub release
                                                              ↓
                                            IzzyOnDroid (takes the built APK)
                                                              ↓
                                            F-Droid (builds from source itself)
```

Five things stand between here and the first submission. Four are the owner's
and cannot be delegated:

1. **Generate the release keystore.** `docs/ANDROID-RELEASING.md` has the
   command. Deliberately not generated for you — losing it means never being
   able to update the app for anyone who installed it.
2. **Add the three GitHub secrets.**
3. **Take the screenshots.** Hard rule 1; `android/fastlane/README.md` names the
   exact set and how to take them.
4. **Merge to `master` and tag `android-v1.0`.** AM11's own rule forbids tagging
   before AM10's round-trip test is green on `master`.
5. Then the release workflow runs and produces the signed APK, which is what
   both channels need.

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

Every one of those is satisfied by the table above **except the screenshots**,
which is the only outstanding item on their side.

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
its reasoning in comments. Two fields cannot be finished yet:

- `commit:` currently names the tag `android-v1.0`. Their reference asks for the
  full 40-character hash, which does not exist until the tag is cut.
- `subdir: android/app` is the field most likely to be wrong on the first build.
  **This repository's gradle root is `android/`, not the repository root**,
  because the desktop application owns the top level — so `gradlew` and
  `settings.gradle.kts` sit one level above the module. If their builder cannot
  find them, `android` is the fallback to try.

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

There is a debt here already, and it predates this milestone: README.md tells
people to download `saat-android-1.0.apk` from the releases page and says the
Android builds are tagged `android-v1.0`. **No such tag and no such release
exist.** It is true only in the future tense. Cutting the release makes it true,
which is the cheapest fix and the one the chain above already leads to — but
until then the README claims a channel that is not there, which is the exact
thing this milestone forbids.
