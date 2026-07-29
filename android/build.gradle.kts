// AGP 9 ships built-in Kotlin support, so `org.jetbrains.kotlin.android` must
// NOT be applied — the two are incompatible and the failure is an obscure
// ClassCastException on the android extension. Pinning the Kotlin version is
// done here, on the buildscript classpath, rather than in a plugins block.
buildscript {
    dependencies {
        classpath(libs.kotlin.gradle.plugin)
    }
}

plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.compose.compiler) apply false
    alias(libs.plugins.kotlin.serialization) apply false
}
