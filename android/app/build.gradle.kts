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
        // versionCode is bumped on every TAGGED release and AM5 is not one —
        // SPEC-ANDROID 8. The name follows the milestone table.
        versionCode = 1
        versionName = "0.5"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
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

    testImplementation(libs.junit)
}
