package io.github.sudomegas.saat.storage

import dev.eav.tomlkt.Toml
import dev.eav.tomlkt.TomlArray
import dev.eav.tomlkt.TomlTable
import org.junit.Assert.assertEquals
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File

/**
 * The Kotlin half of the executable parity checklist.
 *
 * AM2 asks for a checklist mapping every `docs/schema.md` field to its Kotlin
 * property "so an omission is visible rather than discovered in AM4". A written
 * checklist can only be true on the day it is written, so this produces one
 * MECHANICALLY, from the encoder's real output, and `android/tools/
 * parity_check.py` diffs it against `dataclasses.fields()` on the desktop's own
 * `saat/models.py`. A field that is missing, renamed or misspelled fails the
 * Android build.
 *
 * The artefacts this writes into `build/reports/parity/` are the input to the
 * verify step; the file it reads from `build/parity-in/` is the output of the
 * emit step, produced by the desktop's real writer.
 */
class DesktopParityTest {

    private val toml = Toml { ignoreUnknownKeys = true; explicitNulls = false }

    private val reports = File("build/reports/parity")
    private val desktopWritten = File("build/parity-in/desktop-full.toml")

    /**
     * Publish what the desktop side needs to check us. Written by a test rather
     * than by a Gradle task so that it is the tested code path producing them:
     * these are literally `encodeWatch`'s output, not a re-derivation of it.
     */
    @Test
    fun `publish the parity artefacts`() {
        reports.mkdirs()

        val emitted = encodeWatch(fullyPopulatedWatch())
        File(reports, "android-full.toml").writeText(emitted)
        File(reports, "android-minimal.toml").writeText(encodeWatch(minimalWatch()))
        File(reports, "kotlin-fields.json").writeText(fieldMapJson(emitted))
    }

    /**
     * The embedded fixture is what makes the parity load test runnable anywhere,
     * including on a machine with no Python. This is what stops it from becoming
     * a fossil: when CI has regenerated the fixture from the desktop's real
     * writer, the two must be byte-identical.
     *
     * Skipped rather than passed when the generated file is absent, so a local
     * run never reports a check it did not make.
     */
    @Test
    fun `the embedded desktop fixture still matches what the desktop writes`() {
        assumeTrue(
            "run `python3 android/tools/parity_check.py emit android/app/build/parity-in` first",
            desktopWritten.exists(),
        )

        assertEquals(
            "TestWatches.DESKTOP_WRITTEN_FIXTURE has drifted from what saat/storage.py " +
                "actually produces — regenerate it rather than editing the assertion",
            desktopWritten.readText(),
            DESKTOP_WRITTEN_FIXTURE,
        )
    }

    /**
     * The desktop-to-Android direction, checked here where the assertion can name
     * the watch rather than a diff of bytes. The Android-to-desktop direction is
     * the verify step's job, because only the desktop's own loader can answer it.
     */
    @Test
    fun `the file the desktop actually wrote loads with every field intact`() {
        assumeTrue(desktopWritten.exists())

        val decoded = decodeWatch(desktopWritten.readText())
        assertEquals(fullyPopulatedWatch(), decoded.watch)
        assertEquals(emptyList<String>(), decoded.warnings)
    }

    /**
     * The field map, derived from the encoder's real output: whatever keys
     * `encodeWatch` puts in a file for a watch with every field filled in.
     *
     * Grouped the way the file is rather than the way the model is — top-level
     * keys, `[table]` groups, `[[array]]` groups — because that is the shape
     * `docs/schema.md` describes and the shape the desktop's own dataclasses
     * flatten into.
     */
    private fun fieldMapJson(emitted: String): String {
        val root = toml.parseToTomlTable(emitted)

        val top = mutableListOf<String>()
        val groups = linkedMapOf<String, List<String>>()
        val listsOfTables = linkedMapOf<String, List<String>>()

        for ((key, value) in root) {
            when {
                value is TomlTable -> groups[key] = value.keys.toList()

                value is TomlArray && value.any { it is TomlTable } ->
                    listsOfTables[key] = value.filterIsInstance<TomlTable>()
                        .flatMap { it.keys }
                        .distinct()

                else -> top += key
            }
        }

        return buildString {
            appendLine("{")
            appendLine("  \"top\": ${jsonArray(top)},")
            appendLine("  \"groups\": {")
            appendLine(jsonSections(groups))
            appendLine("  },")
            appendLine("  \"lists_of_tables\": {")
            appendLine(jsonSections(listsOfTables))
            appendLine("  }")
            appendLine("}")
        }
    }

    private fun jsonSections(sections: Map<String, List<String>>) =
        sections.entries.joinToString(",\n") { (name, fields) ->
            "    \"$name\": ${jsonArray(fields)}"
        }

    // Every name here is a TOML bare key — letters, digits and underscores — so
    // there is nothing to escape and no JSON library to justify adding.
    private fun jsonArray(items: List<String>) = items.joinToString(", ", "[", "]") { "\"$it\"" }
}
