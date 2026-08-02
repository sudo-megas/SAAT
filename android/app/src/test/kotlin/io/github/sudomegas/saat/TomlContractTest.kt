package io.github.sudomegas.saat

import dev.eav.tomlkt.Toml
import dev.eav.tomlkt.TomlLocalDateSerializer
import kotlinx.serialization.KSerializer
import kotlinx.serialization.Serializable
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.time.LocalDate

/**
 * Decides which Kotlin TOML library AM2's storage layer will be built on, and
 * proves the choice against the shape the desktop actually writes.
 *
 * AM1 ships only `config.toml`, which is flat and would pass with any library.
 * The evaluation is therefore run against a WATCH-shaped fixture, because that
 * is what has to survive the ZIP bridge in AM10. The fixture lives here as a
 * Kotlin string constant and is never committed as a `.toml` resource —
 * SPEC-ANDROID hard rule 1 applies to test assets exactly as it applies to
 * shipped code.
 *
 * Gate order. A failure at 1 or 2 eliminates a library outright:
 *
 *  1. Local dates must round-trip UNQUOTED. `date = 2024-03-11`, never
 *     `date = "2024-03-11"`. A quoted date is a plain string to the desktop's
 *     tomlkit, which would silently corrupt every acquisition date and every
 *     worn day the moment a file crossed platforms.
 *  2. Arrays of tables with mixed presence must decode absent fields as null —
 *     never 0, never "". SPEC-ANDROID 4 renders absence as an em-dash, so the
 *     model has to be able to represent it.
 *  3. Semantic round-trip stability.
 *  4. Behaviour on an empty array of tables.
 *  5. Type mismatch, CHARACTERISED not asserted — the desktop loader does no
 *     coercion at all, so hand-edited files with `rating = "4"` load fine there.
 *     Silent-null here would be invisible data loss and would force AM2 to add
 *     a validation pass.
 */
class TomlContractTest {

    private object LocalDateAsToml : KSerializer<LocalDate> by TomlLocalDateSerializer()

    @Serializable
    private data class Strap(
        val material: String? = null,
        val colour: String? = null,
        val width_mm: Int? = null,
        val clasp: String? = null,
        val fitted: Boolean = false,
        val image: String? = null,
    )

    @Serializable
    private data class LogEntry(
        @Serializable(with = LocalDateAsToml::class) val date: LocalDate? = null,
        val kind: String? = null,
        val note: String? = null,
    )

    @Serializable
    private data class Movement(
        val caliber: String? = null,
        val kind: String? = null,
        val power_reserve_hours: Double? = null,
        val accuracy_min: Double? = null,
    )

    @Serializable
    private data class Case(
        val diameter_mm: Double? = null,
        val lug_width_mm: Int? = null,
        val water_resistance_m: Int? = null,
    )

    @Serializable
    private data class Acquisition(
        @Serializable(with = LocalDateAsToml::class) val date: LocalDate? = null,
        val price: Double? = null,
        val currency: String? = null,
        @Serializable(with = LocalDateAsToml::class) val warranty_until: LocalDate? = null,
    )

    @Serializable
    private data class Watch(
        val brand: String,
        val model: String,
        val rating: Int? = null,
        val tags: List<String> = emptyList(),
        val movement: Movement? = null,
        val case: Case? = null,
        val straps: List<Strap> = emptyList(),
        val log: List<LogEntry> = emptyList(),
        val worn: List<@Serializable(with = LocalDateAsToml::class) LocalDate> = emptyList(),
        val notes: String? = null,
    )

    // explicitNulls = false is not cosmetic and not optional. TOML has no null
    // literal, so tomlkt's default of emitting `notes = null` for every absent
    // optional produces a file the desktop's tomlkit cannot parse at all. Every
    // watch in a collection has absent fields, so the default would have made
    // every file written on the phone unreadable on the desktop.
    private val toml = Toml {
        ignoreUnknownKeys = true
        explicitNulls = false
    }

    // NOTE ON KEY ORDER, which is a TOML rule rather than a library quirk:
    // `worn` and `notes` are top-level keys, so they must appear BEFORE the
    // first table header. After `[[log]]`, a bare key belongs to that log entry
    // — so `worn` written at the bottom silently becomes `log[1].worn` and the
    // wear history vanishes, with no error from either app, because as far as
    // both are concerned the watch simply has no recorded days.
    //
    // Neither app writes one that way: encodeWatch emits every top-level key
    // before the first table by construction, and the desktop is safe because
    // tomlkit hoists them. docs/schema.md carries the same warning for files
    // typed by hand, which are the only ones this can still bite.
    private val fixture = """
        brand = "Grand Seiko"
        model = "SBGA211"
        rating = 4
        tags = ["dress", "grail"]
        worn = [2024-03-12, 2024-03-13, 2025-01-01]
        notes = "A daily wearer."

        [movement]
        caliber = "9R65"
        kind = "Spring Drive"
        power_reserve_hours = 72.0
        accuracy_min = -1.0

        [case]
        diameter_mm = 41.0
        lug_width_mm = 19
        water_resistance_m = 100

        [[straps]]
        material = "Titanium Bracelet"
        width_mm = 19
        fitted = true

        [[straps]]
        material = "Leather"
        fitted = false

        [acquisition]
        date = 2024-03-11
        price = 4200.0
        currency = "TRY"
        warranty_until = 2027-03-11

        [[log]]
        date = 2024-03-11
        kind = "Note"
        note = "Bought in İzmir"

        [[log]]
        date = 2025-01-02
        kind = "Service"
    """.trimIndent()

    private fun report(name: String, body: String) {
        val dir = File("build/reports/toml-eval").apply { mkdirs() }
        File(dir, name).writeText(body)
    }

    // ---- Gate 1: unquoted local dates on encode -------------------------

    @Test
    fun `tomlkt emits local dates unquoted`() {
        val decoded = toml.decodeFromString<Watch>(fixture)
        val emitted = toml.encodeToString(decoded)
        report("emitted.toml", emitted)

        assertTrue(
            "acquisition.date must emit unquoted; got:\n$emitted",
            Regex("""^\s*date\s*=\s*2024-03-11\s*$""", RegexOption.MULTILINE).containsMatchIn(emitted),
        )
        assertTrue(
            "worn must emit as unquoted dates; got:\n$emitted",
            emitted.contains("2024-03-12") && !emitted.contains("\"2024-03-12\""),
        )
        assertTrue(
            "no date may be quoted; got:\n$emitted",
            !Regex(""""\d{4}-\d{2}-\d{2}"""").containsMatchIn(emitted),
        )
    }

    /**
     * TOML has no null literal. An emitted `notes = null` is not merely ugly —
     * it is a syntax error to every conformant parser, including the desktop's
     * tomlkit and including tomlkt itself on the way back in.
     *
     * This is a real defect that the evaluation caught: tomlkt's default is
     * `explicitNulls = true`, and because every watch in a real collection has
     * absent fields, the default would have made every file the phone wrote
     * unreadable on the desktop — the exact failure the ZIP bridge exists to
     * prevent, shipped from AM2 and not discovered until AM10.
     */
    @Test
    fun `tomlkt never emits a null literal`() {
        val emitted = toml.encodeToString(toml.decodeFromString<Watch>(fixture))
        assertTrue(
            "TOML has no null; absent fields must be omitted. Got:\n$emitted",
            !Regex("""=\s*null\b""").containsMatchIn(emitted),
        )

        val minimal = toml.encodeToString(
            toml.decodeFromString<Watch>("brand = \"Casio\"\nmodel = \"F-91W\"")
        )
        assertTrue(
            "a watch with only brand and model must emit no nulls either. Got:\n$minimal",
            !Regex("""=\s*null\b""").containsMatchIn(minimal),
        )
    }

    /** What the phone writes must be readable by the desktop, and by itself. */
    @Test
    fun `tomlkt output is re-readable and keeps every worn date`() {
        val decoded = toml.decodeFromString<Watch>(fixture)
        val emitted = toml.encodeToString(decoded)
        val reread = toml.decodeFromString<Watch>(emitted)

        assertEquals(
            "worn dates must survive a write-read cycle",
            listOf(
                LocalDate.of(2024, 3, 12),
                LocalDate.of(2024, 3, 13),
                LocalDate.of(2025, 1, 1),
            ),
            reread.worn,
        )
        assertEquals(decoded, reread)
    }

    // ---- Gate 2: arrays of tables with mixed presence -------------------

    @Test
    fun `tomlkt decodes arrays of tables with absent fields as null`() {
        val w = toml.decodeFromString<Watch>(fixture)

        assertEquals(2, w.straps.size)
        assertEquals("Titanium Bracelet", w.straps[0].material)
        assertEquals(19, w.straps[0].width_mm)
        assertTrue(w.straps[0].fitted)

        // Second strap omits colour, width_mm, clasp and image entirely.
        assertEquals("Leather", w.straps[1].material)
        assertNull("absent colour must be null, not empty string", w.straps[1].colour)
        assertNull("absent width_mm must be null, not 0", w.straps[1].width_mm)
        assertNull("absent clasp must be null", w.straps[1].clasp)
        assertNull("absent image must be null", w.straps[1].image)

        assertEquals(2, w.log.size)
        assertEquals("Bought in İzmir", w.log[0].note)
        assertNull("absent log note must be null, not empty string", w.log[1].note)
        assertEquals(LocalDate.of(2025, 1, 2), w.log[1].date)

        assertEquals(3, w.worn.size)
        assertEquals(LocalDate.of(2024, 3, 12), w.worn[0])
        assertEquals(LocalDate.of(2025, 1, 1), w.worn[2])
    }

    // ---- Gate 3: semantic round-trip ------------------------------------

    @Test
    fun `tomlkt round-trips semantically`() {
        val once = toml.decodeFromString<Watch>(fixture)
        val twice = toml.decodeFromString<Watch>(toml.encodeToString(once))
        assertEquals(once, twice)
    }

    // ---- Gate 4: empty array of tables ----------------------------------

    @Test
    fun `tomlkt handles a watch with no straps log or worn days`() {
        val minimal = """
            brand = "Casio"
            model = "F-91W"
        """.trimIndent()

        val w = toml.decodeFromString<Watch>(minimal)
        assertEquals("Casio", w.brand)
        assertEquals(emptyList<Strap>(), w.straps)
        assertEquals(emptyList<LogEntry>(), w.log)
        assertEquals(emptyList<LocalDate>(), w.worn)
        assertNull(w.movement)

        val emitted = toml.encodeToString(w)
        report("emitted-minimal.toml", emitted)
        // Re-decoding is the contract that matters; how empties are spelled is
        // recorded rather than asserted.
        assertEquals(w, toml.decodeFromString<Watch>(emitted))
    }

    // ---- Gate 5: type mismatch, characterised ---------------------------

    @Test
    fun `characterise tomlkt behaviour on type mismatches`() {
        val cases = mapOf(
            "rating as string" to """brand="A"
model="B"
rating = "4"""",
            "diameter as int where double expected" to """brand="A"
model="B"
[case]
diameter_mm = 41""",
            "fitted as string" to """brand="A"
model="B"
[[straps]]
fitted = "true"""",
        )

        val findings = buildString {
            appendLine("tomlkt ${'$'}0.6.1 behaviour on type mismatch")
            appendLine("(the desktop loader does no coercion, so these files exist)")
            appendLine()
            cases.forEach { (name, src) ->
                val outcome = runCatching { toml.decodeFromString<Watch>(src) }.fold(
                    onSuccess = { "ACCEPTED -> $it" },
                    onFailure = { "${it::class.simpleName}: ${it.message?.take(160)}" },
                )
                appendLine("$name:")
                appendLine("  $outcome")
            }
        }
        report("type-mismatch.txt", findings)
        println(findings)

        // Nothing is asserted here except that characterisation ran — the
        // finding goes into the commit message and drives AM2's validation
        // decision. A throw is the GOOD outcome; a silent null is the dangerous
        // one because it is invisible data loss.
        assertTrue(findings.isNotEmpty())
    }

    // ---- Gate 6-8: unknown keys, comments, unicode ----------------------

    @Test
    fun `tomlkt tolerates unknown keys comments and unicode`() {
        val withExtras = """
            # A hand-written comment above the brand.
            brand = "Züblin"          # trailing comment
            model = "Ébauche İzmir"
            future_field_from_a_later_desktop_version = "surprise"

            [movement]
            caliber = "Cal. 42"
            unknown_nested = 1
        """.trimIndent()

        val w = toml.decodeFromString<Watch>(withExtras)
        assertEquals("Züblin", w.brand)
        assertEquals("Ébauche İzmir", w.model)
        assertEquals("Cal. 42", w.movement?.caliber)

        val emitted = toml.encodeToString(w)
        assertTrue("unicode must survive as UTF-8, not \\u escapes", emitted.contains("Züblin"))
        assertTrue(emitted.contains("İzmir"))
    }
}
