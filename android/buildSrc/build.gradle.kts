plugins {
    `kotlin-dsl`
}

repositories {
    mavenCentral()
    google()
}

dependencies {
    testImplementation("junit:junit:4.13.2")
}

// Deliberately no AGP dependency here. buildSrc holds the two pieces that do
// not need one — the scanner, which is a pure function over a string, and the
// task type, which takes a file. The variant wiring that does need AGP lives in
// app/build.gradle.kts, where AGP is already on the classpath.
//
// The alternative was `implementation("com.android.tools.build:gradle")` plus a
// Plugin class. That works, but it puts the whole of AGP on the build-script
// classpath, couples buildSrc to an AGP version in a second place, and slows
// every configuration phase — all to move six lines of wiring out of the file
// they apply to. (compileOnly is not an option: the class would compile and
// then fail at plugin-instantiation time with NoClassDefFoundError, which is
// exactly how this was found.)

tasks.test {
    testLogging {
        events("failed")
    }
}

// Make the jar depend on the tests, so they actually run.
//
// The reason buildSrc was chosen over an included build was that Gradle builds
// it before evaluating the root project, so the guardian's own tests would run
// on every invocation with no CI wiring anyone could delete. That belief is
// out of date: modern Gradle builds only what it needs from buildSrc, which is
// `jar` — not `build`, and not `test`. Measured, not assumed: the first green
// `./gradlew check` reported 27 app tests and *zero* buildSrc tests, so the
// eleven tests guarding the zero-permission scanner were dead code.
//
// Gradle must produce this jar before it can evaluate app/build.gradle.kts, so
// hanging the tests off it restores the original intent and makes it true. The
// cost is a few hundred milliseconds; the scanner tests are pure string
// parsing with no Android, no Gradle and no I/O.
//
// finalizedBy rather than dependsOn: the `kotlin-dsl` plugin puts this jar on
// the test COMPILE classpath, so `jar dependsOn test` is a circular dependency
// (compileTestKotlin -> jar -> test -> compileTestKotlin). Finalizing runs the
// tests immediately after the jar instead of before it, and a failing finalizer
// still fails the build — which is the property that matters.
tasks.named("jar") {
    finalizedBy(tasks.test)
}
