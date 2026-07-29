package io.github.sudomegas.saat

import com.akuleshov7.ktoml.Toml as Ktoml
import com.akuleshov7.ktoml.TomlInputConfig
import kotlinx.datetime.LocalDate as KxLocalDate
import kotlinx.serialization.Serializable
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import org.junit.Test
import java.io.File

/**
 * The other half of the AM1 TOML evaluation. Runs ktoml over the same two
 * decisive gates [TomlContractTest] applies to tomlkt, so the library choice
 * recorded in the AM1a commit message is a measurement rather than a preference.
 *
 * Both libraries are on the test classpath for this milestone only. The loser
 * is deleted from `libs.versions.toml` and `app/build.gradle.kts` in the same
 * commit, and the winner is promoted from `testImplementation` to
 * `implementation`.
 *
 * Nothing here asserts a pass or a fail — every outcome is written to
 * `build/reports/toml-eval/ktoml.txt` and to stdout. Deciding by reading the
 * report is the point; a red test would only tell us which library to keep by
 * making the build fail, which is a worse way to learn it.
 */
class KtomlComparisonTest {

    @Serializable
    private data class Strap(
        val material: String? = null,
        val colour: String? = null,
        val width_mm: Int? = null,
        val fitted: Boolean = false,
    )

    @Serializable
    private data class LogEntry(
        val date: KxLocalDate? = null,
        val kind: String? = null,
        val note: String? = null,
    )

    @Serializable
    private data class Acquisition(
        val date: KxLocalDate? = null,
        val currency: String? = null,
    )

    @Serializable
    private data class Watch(
        val brand: String,
        val model: String,
        val straps: List<Strap> = emptyList(),
        val log: List<LogEntry> = emptyList(),
        val worn: List<KxLocalDate> = emptyList(),
        val acquisition: Acquisition? = null,
    )

    // `worn` sits above the first table header deliberately — see the note in
    // TomlContractTest. Below `[[log]]` it would bind to that log entry.
    private val fixture = """
        brand = "Grand Seiko"
        model = "SBGA211"
        worn = [2024-03-12, 2024-03-13]

        [[straps]]
        material = "Titanium Bracelet"
        width_mm = 19
        fitted = true

        [[straps]]
        material = "Leather"
        fitted = false

        [acquisition]
        date = 2024-03-11
        currency = "TRY"

        [[log]]
        date = 2024-03-11
        kind = "Note"
        note = "Bought in İzmir"

        [[log]]
        date = 2025-01-02
        kind = "Service"
    """.trimIndent()

    @Test
    fun `characterise ktoml against the same gates`() {
        val ktoml = Ktoml(inputConfig = TomlInputConfig(ignoreUnknownNames = true))

        val findings = buildString {
            appendLine("ktoml 0.7.1 against the AM1 gates")
            appendLine("=================================")
            appendLine()

            val decoded = runCatching { ktoml.decodeFromString<Watch>(fixture) }
            appendLine("GATE 2 - decode arrays of tables with mixed presence:")
            decoded.fold(
                onSuccess = { w ->
                    appendLine("  decoded OK")
                    appendLine("  straps        = ${w.straps.size} (expected 2)")
                    appendLine("  straps[1]     = ${w.straps.getOrNull(1)}")
                    appendLine("    colour null? ${w.straps.getOrNull(1)?.colour == null}")
                    appendLine("    width null?  ${w.straps.getOrNull(1)?.width_mm == null}")
                    appendLine("  log           = ${w.log.size} (expected 2)")
                    appendLine("    log[1].note null? ${w.log.getOrNull(1)?.note == null}")
                    appendLine("  worn          = ${w.worn}")
                    appendLine("  acquisition   = ${w.acquisition}")
                },
                onFailure = { appendLine("  FAILED ${it::class.simpleName}: ${it.message?.take(300)}") },
            )

            appendLine()
            appendLine("GATE 1 - re-emit local dates unquoted:")
            decoded.mapCatching { ktoml.encodeToString(it) }.fold(
                onSuccess = { out ->
                    val quoted = Regex(""""\d{4}-\d{2}-\d{2}"""").containsMatchIn(out)
                    appendLine("  encoded OK; any quoted date? $quoted")
                    appendLine("  ---8<---")
                    out.lines().forEach { appendLine("  $it") }
                    appendLine("  --->8---")
                },
                onFailure = { appendLine("  FAILED ${it::class.simpleName}: ${it.message?.take(300)}") },
            )
        }

        File("build/reports/toml-eval").apply { mkdirs() }
            .resolve("ktoml.txt").writeText(findings)
        println(findings)
    }
}
