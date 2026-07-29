package io.github.sudomegas.saat.buildlogic

import org.gradle.api.DefaultTask
import org.gradle.api.GradleException
import org.gradle.api.file.RegularFileProperty
import org.gradle.api.provider.Property
import org.gradle.api.tasks.CacheableTask
import org.gradle.api.tasks.InputFile
import org.gradle.api.tasks.Input
import org.gradle.api.tasks.Optional
import org.gradle.api.tasks.OutputFile
import org.gradle.api.tasks.PathSensitive
import org.gradle.api.tasks.PathSensitivity
import org.gradle.api.tasks.TaskAction

/**
 * Fails the build if a variant's MERGED manifest breaks SPEC-ANDROID's rules.
 *
 * Merged, not source: a permission smuggled in by a dependency's manifest is
 * exactly the case rule 2 exists to catch, and it is invisible in the manifest
 * we hand-write.
 */
@CacheableTask
abstract class VerifyManifestPolicyTask : DefaultTask() {

    @get:InputFile
    @get:PathSensitive(PathSensitivity.NONE)
    abstract val mergedManifest: RegularFileProperty

    /** AGP's blame report, when it exists — names which AAR injected what. */
    @get:InputFile
    @get:Optional
    @get:PathSensitive(PathSensitivity.NONE)
    abstract val mergerReport: RegularFileProperty

    @get:Input
    abstract val variantName: Property<String>

    @get:OutputFile
    abstract val report: RegularFileProperty

    @TaskAction
    fun verify() {
        val manifest = mergedManifest.get().asFile
        val violations = ManifestPolicyScanner.scan(manifest.readText())

        val out = report.get().asFile
        out.parentFile.mkdirs()

        if (violations.isEmpty()) {
            out.writeText(
                "OK ${variantName.get()}\n" +
                    "no permissions declared, rotation not suppressed, backup rules present\n" +
                    "source: ${manifest.absolutePath}\n"
            )
            return
        }

        val blame = mergerReport.orNull?.asFile
            ?.takeIf { it.exists() }
            ?.readLines()
            ?.filter { line -> violations.any { v -> line.contains(v.detail.substringAfter("declares ").trim()) } }
            ?.take(12)
            .orEmpty()

        val message = buildString {
            appendLine("Manifest policy violated in the ${variantName.get()} variant.")
            appendLine()
            violations.forEach { appendLine("  - ${it.detail}   [${it.rule}]") }
            appendLine()
            appendLine("Merged manifest: ${manifest.absolutePath}")
            if (blame.isNotEmpty()) {
                appendLine()
                appendLine("From the manifest-merger blame report:")
                blame.forEach { appendLine("  $it") }
            }
            appendLine()
            appendLine("If a dependency introduced this, the fix is to remove the dependency or")
            appendLine("add a tools:node=\"remove\" override - never to relax this check.")
        }

        out.writeText(message)
        throw GradleException(message)
    }
}
