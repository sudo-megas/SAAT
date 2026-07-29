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
