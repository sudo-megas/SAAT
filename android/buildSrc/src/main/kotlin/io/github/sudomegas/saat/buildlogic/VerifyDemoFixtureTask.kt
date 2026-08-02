package io.github.sudomegas.saat.buildlogic

import org.gradle.api.DefaultTask
import org.gradle.api.GradleException
import org.gradle.api.file.Directory
import org.gradle.api.file.RegularFile
import org.gradle.api.file.RegularFileProperty
import org.gradle.api.provider.ListProperty
import org.gradle.api.provider.Property
import org.gradle.api.tasks.CacheableTask
import org.gradle.api.tasks.Input
import org.gradle.api.tasks.InputFile
import org.gradle.api.tasks.InputFiles
import org.gradle.api.tasks.Optional
import org.gradle.api.tasks.OutputFile
import org.gradle.api.tasks.PathSensitive
import org.gradle.api.tasks.PathSensitivity
import org.gradle.api.tasks.TaskAction
import java.util.zip.ZipFile

/**
 * Asserts the demo-watch fixture is present in debug builds and ABSENT from
 * release builds — SPEC-ANDROID hard rule 1's own closing clause.
 *
 * A Gradle task rather than a unit test, for the reason already recorded beside
 * the manifest guardian in app/build.gradle.kts: `testBuildType` defaults to
 * debug and AGP 9 does not create the release unit-test variant at all, so a
 * Robolectric test could only ever see debug — while release is precisely where
 * the claim needs proving.
 *
 * It inspects the variant's own compiled classes rather than the packaged APK,
 * which keeps `check` from having to assemble and sign a release build.
 *
 * REGISTERED ON BOTH VARIANTS, and that is not symmetry for its own sake. A
 * check that only ever asserts absence passes trivially the day someone renames
 * the package or the marker string, and would then stay green forever while
 * proving nothing. The debug half is the positive control: it fails if the
 * fixture stops being findable, which is the same failure that would silently
 * disarm the release half.
 */
@CacheableTask
abstract class VerifyDemoFixtureTask : DefaultTask() {

    @get:InputFiles
    @get:PathSensitive(PathSensitivity.RELATIVE)
    abstract val classDirectories: ListProperty<Directory>

    @get:InputFiles
    @get:PathSensitive(PathSensitivity.RELATIVE)
    abstract val classJars: ListProperty<RegularFile>

    /** The variant's R.txt, so the debug-only string resources are checked too. */
    @get:InputFile
    @get:Optional
    @get:PathSensitive(PathSensitivity.NONE)
    abstract val runtimeSymbolList: RegularFileProperty

    /** True for debug (the fixture must be there), false for release. */
    @get:Input
    abstract val expectPresent: Property<Boolean>

    @get:Input
    abstract val variantName: Property<String>

    @get:OutputFile
    abstract val report: RegularFileProperty

    @TaskAction
    fun verify() {
        val findings = buildList {
            classDirectories.get().forEach { directory ->
                directory.asFile.walkTopDown()
                    .filter { it.isFile && it.extension == "class" }
                    .forEach { file ->
                        val relative = file.relativeTo(directory.asFile).path
                        if (DemoFixtureScanner.isDevtoolsClass(relative)) {
                            add(DemoFixtureFinding("devtools-class", relative))
                        } else if (DemoFixtureScanner.containsMarker(file.readBytes())) {
                            add(DemoFixtureFinding("marker-string", relative))
                        }
                    }
            }

            classJars.get().forEach { jar ->
                ZipFile(jar.asFile).use { zip ->
                    zip.entries().asSequence()
                        .filter { !it.isDirectory && it.name.endsWith(".class") }
                        .forEach { entry ->
                            if (DemoFixtureScanner.isDevtoolsClass(entry.name)) {
                                add(DemoFixtureFinding("devtools-class", "${jar.asFile.name}!${entry.name}"))
                            } else if (
                                DemoFixtureScanner.containsMarker(zip.getInputStream(entry).readBytes())
                            ) {
                                add(DemoFixtureFinding("marker-string", "${jar.asFile.name}!${entry.name}"))
                            }
                        }
                }
            }

            runtimeSymbolList.orNull?.asFile
                ?.takeIf { it.exists() }
                ?.let { symbols ->
                    DemoFixtureScanner.demoResourceNames(symbols.readText())
                        .forEach { add(DemoFixtureFinding("demo-resource", it)) }
                }
        }

        val out = report.get().asFile
        out.parentFile.mkdirs()

        val present = findings.isNotEmpty()
        val expected = expectPresent.get()

        if (present == expected) {
            out.writeText(
                buildString {
                    appendLine("OK ${variantName.get()}")
                    appendLine(
                        if (expected) {
                            "demo fixture present, as a debug build requires"
                        } else {
                            "demo fixture absent, as hard rule 1 requires of a release build"
                        }
                    )
                    findings.forEach { appendLine("  - ${it.detail}   [${it.rule}]") }
                }
            )
            return
        }

        val message = buildString {
            if (expected) {
                appendLine("The demo-watch fixture is MISSING from the ${variantName.get()} variant.")
                appendLine()
                appendLine("This is the positive control for hard rule 1's release check, not a")
                appendLine("feature test. Nothing under ${DemoFixtureScanner.DEVTOOLS_PATH} was compiled,")
                appendLine("no class carried the marker \"${DemoFixtureScanner.MARKER}\", and no")
                appendLine("\"${DemoFixtureScanner.RESOURCE_TOKEN}\" string resource was declared.")
                appendLine()
                appendLine("If the fixture moved or was renamed, update DemoFixtureScanner to match.")
                appendLine("Leaving this failing would silently disarm the release check, which")
                appendLine("would then pass while proving nothing.")
            } else {
                appendLine("The demo-watch fixture LEAKED into the ${variantName.get()} variant.")
                appendLine()
                appendLine("SPEC-ANDROID hard rule 1: release APKs ship empty, always. The generator")
                appendLine("belongs in src/debug, which is not compiled into release at all.")
                appendLine()
                findings.forEach { appendLine("  - ${it.detail}   [${it.rule}]") }
                appendLine()
                appendLine("A BuildConfig.DEBUG guard is NOT a fix: isMinifyEnabled is false for")
                appendLine("release, so guarded code still ships in the DEX. Move it to src/debug.")
            }
        }

        out.writeText(message)
        throw GradleException(message)
    }
}
