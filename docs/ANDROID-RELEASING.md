# Releasing SAAT for Android

How a signed APK gets built and published. The desktop's own release process is
in `DEVELOPMENT.md` and is entirely separate — different tags, different
workflow, different versioning.

---

## The keystore

Android requires every APK to be signed, and it requires **every update to be
signed by the same key as the install it replaces**. That single fact is what
makes the paragraph below the most important one in this file.

> ## LOSING THIS KEYSTORE MEANS NEVER UPDATING THE APP FOR EXISTING USERS.
>
> Not "means a difficult migration". There is no recovery, no appeal and no
> support channel that can help: an APK signed by a different key is a different
> application as far as every Android device is concerned. Everyone who installed
> SAAT would have to uninstall it — losing nothing, since the data is in
> `filesDir` and would go with it unless they exported first — and install the
> new one by hand.
>
> **Keep copies in at least two offline places.** Not two folders on one
> machine, and not a cloud drive that is one password reset away from somebody
> else. Two physical things, in two locations, that do not fail together.

### Generating it — the owner's action, done once

This is deliberately not automated and is not run by CI. Run it locally, on the
machine that will hold the original:

```sh
keytool -genkeypair -v \
  -keystore saat-release.jks \
  -alias saat \
  -keyalg RSA \
  -keysize 4096 \
  -validity 10950 \
  -storetype PKCS12
```

- `-validity 10950` is thirty years. Android will refuse an update signed by an
  expired certificate, so the validity has to outlive the app; a key that
  expires in five years is a deadline nobody remembers setting.
- `-keysize 4096` rather than the 2048 the tool suggests. It costs nothing and
  the key has to stay adequate for as long as it is valid.
- `-storetype PKCS12` because JKS is the obsolete format and `keytool` warns
  about it on every use.

`keytool` will ask for a store password, then for the details on the
certificate, then for a key password. Recording the same value for both
passwords is normal and is what the workflow below assumes. **Write both down
with the offline copies** — a keystore whose password is lost is a keystore that
is lost.

Verify what you produced before trusting it:

```sh
keytool -list -v -keystore saat-release.jks -alias saat
```

Check the `Valid from … until …` line reads about thirty years, and that the
signature algorithm is SHA384withRSA or better.

### Where it must never go

`.gitignore` has carried `*.keystore`, `*.jks` and `keystore.properties` since
AM1 — before there was a keystore to be careless with. Do not add an exception,
do not commit a base64 copy "temporarily", and do not paste a password into a
commit message, an issue or a pull request. A secret that has been in a public
repository for one minute is a secret that has been published; rotating an app
signing key is the one rotation Android does not allow.

---

## Building a signed APK by hand

The build reads four values, from the environment or from Gradle properties,
and neither source is inside this repository:

| Name | What |
|---|---|
| `SAAT_KEYSTORE_FILE` | absolute path to the `.jks` |
| `SAAT_KEYSTORE_PASSWORD` | the store password |
| `SAAT_KEY_ALIAS` | `saat`, unless you chose otherwise |
| `SAAT_KEY_PASSWORD` | the key password |

Set none of them and the release variant still builds — **unsigned**. That is
deliberate: `assembleDebug`, the unit tests and `check` must all work on a
machine that has never seen the keystore, which is every contributor's machine
and every CI run that is not a release.

For a local signed build, put them in `~/.gradle/gradle.properties` — outside
the repository, and not backed up into it:

```properties
SAAT_KEYSTORE_FILE=/home/you/keys/saat-release.jks
SAAT_KEYSTORE_PASSWORD=…
SAAT_KEY_ALIAS=saat
SAAT_KEY_PASSWORD=…
```

then:

```sh
cd android && ./gradlew assembleRelease
```

Confirm what came out is actually signed, rather than assuming:

```sh
"$ANDROID_HOME"/build-tools/*/apksigner verify --verbose --print-certs \
  android/app/build/outputs/apk/release/app-release.apk
```

It must report `Verified using v2 scheme` (and v3 on a modern build-tools), and
the certificate it prints must be yours.

---

## The GitHub secrets

Three secrets on the repository, under **Settings → Secrets and variables →
Actions**. The keystore travels base64-encoded because a secret is a string:

```sh
base64 -w0 saat-release.jks
```

| Secret | Value |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | the output of the command above |
| `ANDROID_KEYSTORE_PASSWORD` | the store password |
| `ANDROID_KEY_PASSWORD` | the key password |

The alias is not a secret and is set in the workflow.

`base64 -w0` on GNU coreutils; on macOS it is `base64 -i saat-release.jks`.
Watch for a trailing newline — a wrapped or newline-terminated value decodes to
a corrupt keystore and fails at signing time with a message about the file
format rather than about the secret.

---

## Cutting a release

The workflow is `.github/workflows/android-release.yml` and it triggers on
`android-v*` tags. There is no manual upload step; if the workflow does not
produce the release, fix the workflow rather than building by hand.

1. **AM10's round-trip test must be green on `master`.** This is a rule, not a
   preference: an app that cannot export its data does not get released, and the
   ZIP bridge is what makes the phone and the desktop one collection rather than
   two.
2. Bump `versionName` in `android/app/build.gradle.kts` and **`versionCode`**,
   which is a monotonic integer and must increase on every release Android will
   ever see. Add the `CHANGELOG-ANDROID.md` entry. `VersionGuardTest` asserts
   the two agree, so a forgotten changelog fails the build rather than shipping.
3. **Dry-run before spending a tag.** Run the release workflow manually
   (`workflow_dispatch`); it builds and signs exactly as the tag path does and
   publishes nothing. The desktop's `DEVELOPMENT.md` learned this the hard way —
   a tag is public and awkward to retract, and the failures worth catching here
   are a missing secret, a mistyped path or a stale version guard.
4. Tag and push:

   ```sh
   git tag -a android-v1.0 -m "SAAT Android v1.0"
   git push origin android-v1.0
   ```

5. Watch the Actions run. It runs the full test suite — round-trip test
   included — builds the signed APK, verifies the signature with `apksigner`,
   and attaches the APK to a GitHub Release created for the tag.

### If a release goes out wrong

Assets upload with `--clobber`, so re-running the workflow on the same tag
replaces the binary. What cannot be replaced is the signing key, which is the
only irreversible thing in this document.
