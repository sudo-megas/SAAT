import com.android.build.api.artifact.SingleArtifact
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
        versionCode = 1
        versionName = "0.1"
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
    // storage layer. TomlContractTest holds the gates; KtomlComparisonTest runs
    // the alternative over the same fixture. The measurements are in the AM1a
    // commit message.
    implementation(libs.tomlkt)

    // The losing candidate, kept on the TEST classpath only for the duration of
    // AM1 so the comparison is reproducible from the repository rather than
    // taken on trust. Removed once AM1 is merged.
    testImplementation(libs.ktoml.core)

    testImplementation(libs.junit)
}
