import com.android.build.api.artifact.ScopedArtifact
import com.android.build.api.artifact.SingleArtifact
import com.android.build.api.variant.ScopedArtifacts
import io.github.sudomegas.saat.buildlogic.VerifyDemoFixtureTask
import io.github.sudomegas.saat.buildlogic.VerifyManifestPolicyTask

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.compose.compiler)
    alias(libs.plugins.kotlin.serialization)
}

android {
    namespace = "io.github.sudomegas.saat"
    compileSdk = 37

    defaultConfig {
        applicationId = "io.github.sudomegas.saat"
        minSdk = 26
        targetSdk = 37
        // versionCode is bumped on every TAGGED release — SPEC-ANDROID 8 — and
        // v1.0 is the first one. It stayed at 1 through AM1..AM10 because none
        // of those milestones was tagged; every future release increments it,
        // monotonically, because it is what Android compares to decide whether
        // an APK is an update. VersionGuardTest holds versionName to the newest
        // CHANGELOG-ANDROID.md heading.
        versionCode = 2
        versionName = "1.0"
    }

    /**
     * Release signing — AM11b, SPEC-ANDROID 8.
     *
     * NOTHING SECRET IS IN THIS REPOSITORY, and nothing ever may be. The
     * keystore reaches a build through the environment or through Gradle
     * properties, both of which live outside the tree; `.gitignore` has carried
     * `*.keystore`, `*.jks` and `keystore.properties` since AM1, before any
     * keystore existed to be careless with.
     *
     * CONFIGURED ONLY WHEN THE MATERIAL IS ACTUALLY THERE. `assembleDebug`, the
     * unit tests and `check` must all keep working on a machine that has never
     * seen the keystore — which is every contributor's machine and every CI run
     * that is not a release. An always-present signing config would fail
     * configuration for all of them, so the block below is conditional and its
     * absence produces an unsigned release APK rather than an error. The release
     * WORKFLOW asserts the config exists; the build does not.
     */
    val keystore = releaseKeystore(project)
    if (keystore != null) {
        signingConfigs {
            create("release") {
                storeFile = keystore.file
                storePassword = keystore.storePassword
                keyAlias = keystore.keyAlias
                keyPassword = keystore.keyPassword
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
            // Null when no keystore was supplied, which AGP reads as "do not
            // sign" rather than as an error — see above.
            signingConfig = signingConfigs.findByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
    }

    testOptions {
        unitTests {
            isReturnDefaultValues = true
        }
    }
}

/**
 * The desktop parity artefacts are a real output of the unit tests, and Gradle
 * has to be told so.
 *
 * `DesktopParityTest` writes `build/reports/parity/`, and CI then hands those
 * files to the desktop's own loader (`android/tools/parity_check.py verify`).
 * With caching on — it is, in gradle.properties — a rerun with no test-source
 * change restores the test task FROM-CACHE and re-executes nothing, so an
 * undeclared directory would simply not exist on a fresh checkout and the verify
 * step would fail on the second push rather than on a real problem.
 *
 * The fixture the desktop writes for us is declared as an input for the mirror
 * reason: regenerating it must invalidate the tests that read it. A file tree
 * over a directory that does not exist is empty rather than an error, which is
 * what makes this safe to declare unconditionally.
 */
tasks.withType<Test>().configureEach {
    outputs.dir(layout.buildDirectory.dir("reports/parity"))
        .withPropertyName("desktopParityArtefacts")

    // AM10's half of the same bargain: the exported archive is a real output of
    // the tests, and CI hands it to `parity_check.py zip`. Undeclared, a cached
    // test task would restore no file on a fresh checkout and the release gate
    // would fail for a reason that is not a bug.
    outputs.dir(layout.buildDirectory.dir("reports/zip-bridge"))
        .withPropertyName("zipBridgeArtefacts")

    inputs.files(fileTree(layout.buildDirectory.dir("parity-in")))
        .withPropertyName("desktopWrittenFixture")
        .withPathSensitivity(PathSensitivity.RELATIVE)
        .optional()
}

/**
 * The guardian of SPEC-ANDROID hard rule 2, registered once per variant.
 *
 * This is a Gradle task rather than a unit test for a structural reason:
 * `testBuildType` defaults to debug, and AGP 9 makes it explicit — the release
 * unit-test variant is not even created. A Robolectric test could therefore
 * only ever see the debug manifest, forever, while release is exactly where a
 * dependency-injected permission would actually ship. Such a guardian could
 * stay green for twelve milestones while the released APK differed.
 *
 * `onVariants` with no selector fires for debug AND release, and reading
 * MERGED_MANIFEST carries the task dependency automatically — so `./gradlew
 * check` verifies the release manifest without assembling a release APK.
 */
androidComponents {
    onVariants { variant ->
        val capitalised = variant.name.replaceFirstChar { it.uppercase() }
        val verify = tasks.register<VerifyManifestPolicyTask>(
            "verify${capitalised}ManifestPolicy"
        ) {
            group = "verification"
            description = "Asserts the merged ${variant.name} manifest declares no permissions."

            // A read, not a transform: this observes the merger's output and
            // can never alter it. The only way it affects the build is by
            // failing.
            mergedManifest.set(variant.artifacts.get(SingleArtifact.MERGED_MANIFEST))
            variantName.set(variant.name)
            mergerReport.set(
                layout.buildDirectory.file(
                    "outputs/logs/manifest-merger-${variant.name}-report.txt"
                )
            )
            report.set(
                layout.buildDirectory.file("reports/manifest-policy/${variant.name}.txt")
            )
        }
        tasks.named("check") { dependsOn(verify) }

        // The guardian of hard rule 1's closing clause: "a test asserts the
        // mechanism is absent from release builds". Registered on BOTH variants
        // on purpose — the debug run is the positive control, without which the
        // release assertion would pass trivially the day the fixture is renamed.
        //
        // Reads the variant's own compiled classes rather than the packaged APK,
        // so `check` never has to assemble or sign a release build.
        val verifyDemoFixture = tasks.register<VerifyDemoFixtureTask>(
            "verify${capitalised}DemoFixturePolicy"
        ) {
            group = "verification"
            description =
                "Asserts the demo-watch fixture is ${
                    if (variant.name == "debug") "present in" else "absent from"
                } the ${variant.name} variant."

            expectPresent.set(variant.name == "debug")
            variantName.set(variant.name)
            runtimeSymbolList.set(variant.artifacts.get(SingleArtifact.RUNTIME_SYMBOL_LIST))
            report.set(
                layout.buildDirectory.file("reports/demo-fixture/${variant.name}.txt")
            )
        }

        // PROJECT scope, not ALL: the question is whether OUR code carries the
        // fixture. Dependencies cannot, and scanning every library's classes on
        // each build would cost seconds to prove something impossible.
        variant.artifacts
            .forScope(ScopedArtifacts.Scope.PROJECT)
            .use(verifyDemoFixture)
            .toGet(
                ScopedArtifact.CLASSES,
                VerifyDemoFixtureTask::classJars,
                VerifyDemoFixtureTask::classDirectories,
            )

        tasks.named("check") { dependsOn(verifyDemoFixture) }
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)

    // Not in SPEC-ANDROID 2.1 as originally written; added in AM1 with the
    // justification recorded in the commit message. Hard rule 7 ("the app never
    // reads the system locale") is not a default on Android — Android resource
    // resolution follows the system locale the moment values-tr/ exists, so the
    // English default has to be asserted. The supported API for that below 33
    // is AppCompatDelegate.setApplicationLocales, which needs this library, and
    // it determines the Activity base class and XML theme parent — both
    // expensive to change once every screen exists.
    implementation(libs.androidx.appcompat)

    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.navigation.compose)

    val composeBom = platform(libs.compose.bom)
    implementation(composeBom)
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.graphics)
    implementation(libs.compose.material3)
    debugImplementation(libs.compose.ui.tooling)
    implementation(libs.compose.ui.tooling.preview)

    // TOML. Chosen in AM1 rather than AM2 so the storage layer inherits a
    // library already proven against a watch-shaped fixture — and so that if it
    // turns out to be wrong, switching costs one file instead of the whole
    // storage layer. TomlContractTest holds the gates that decided it, and goes
    // on holding them. The measurements, and the comparison against the
    // candidate that lost, are in the AM1a commit message; that candidate left
    // the test classpath when AM1 merged, as its own comment promised.
    implementation(libs.tomlkt)

    // Images. SPEC-ANDROID 2.1 approved Coil from the start; AM3 is the first
    // milestone that shows a photograph. coil-compose ONLY — its POM pulls just
    // coil, coil-compose-core and the Kotlin stdlib. The coil-network-* modules
    // bring an HTTP client whose manifest declares INTERNET, which hard rule 2
    // forbids outright and verifyReleaseManifestPolicy would fail the build
    // over. Nothing here ever loads a URL: every model is a local File.
    implementation(libs.coil.compose)

    // NO GLANCE, and AM8 is where that was settled — against SPEC-ANDROID 2.1,
    // which approves it. Every published Glance version declares
    // androidx.work:work-runtime, and GlanceAppWidget's CONSTRUCTOR resolves
    // androidx.work.CoroutineWorker: it is not an optional path that could be
    // excluded, it is the class itself. Measured, not assumed — with the
    // dependency excluded the widget crashed on a real phone with
    // NoClassDefFoundError before it drew a pixel.
    //
    // Keeping WorkManager means shipping WAKE_LOCK, ACCESS_NETWORK_STATE,
    // RECEIVE_BOOT_COMPLETED and FOREGROUND_SERVICE — hard rule 2 forbids every
    // one, and verifyReleaseManifestPolicy found all four — plus androidx.sqlite,
    // which hard rule 4 forbids by name. The hard rules are "non-negotiable, do
    // not improve past them"; §2.1's approved list is a budget written before
    // anyone checked what Glance drags in. So the widget is plain RemoteViews,
    // which needs no dependency at all. See the note in TodayWidgetProvider.

    testImplementation(libs.junit)
}

/**
 * Where the release signing material comes from — AM11b.
 *
 * Two sources, checked in order, and NEITHER is the repository:
 *
 *  1. Environment variables, which is how CI supplies them. The workflow
 *     decodes the base64 keystore secret to a file outside the tree and exports
 *     the three passwords.
 *  2. Gradle properties, which is how the owner signs a build by hand without
 *     exporting anything into their shell — `~/.gradle/gradle.properties` is
 *     outside the repository and is not backed up into it.
 *
 * Returns null when the material is absent or the file it names does not exist,
 * so an ordinary build on an ordinary machine simply produces an unsigned
 * release APK. A missing keystore is not an error here; shipping one that is
 * not signed is, and that is the release workflow's job to catch.
 *
 * See docs/ANDROID-RELEASING.md for how the keystore is generated and which
 * GitHub secrets hold it.
 */
data class ReleaseKeystore(
    val file: File,
    val storePassword: String,
    val keyAlias: String,
    val keyPassword: String,
)

fun releaseKeystore(project: Project): ReleaseKeystore? {
    fun value(name: String): String? =
        (System.getenv(name) ?: project.findProperty(name)?.toString())
            ?.takeIf { it.isNotBlank() }

    val path = value("SAAT_KEYSTORE_FILE") ?: return null
    val file = File(path)
    if (!file.isFile) {
        project.logger.lifecycle(
            "SAAT_KEYSTORE_FILE is set to $path but no file is there — " +
                "building the release variant UNSIGNED."
        )
        return null
    }

    return ReleaseKeystore(
        file = file,
        storePassword = value("SAAT_KEYSTORE_PASSWORD") ?: return null,
        keyAlias = value("SAAT_KEY_ALIAS") ?: return null,
        keyPassword = value("SAAT_KEY_PASSWORD") ?: return null,
    )
}
