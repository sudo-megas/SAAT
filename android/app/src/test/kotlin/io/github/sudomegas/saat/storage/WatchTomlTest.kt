package io.github.sudomegas.saat.storage

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

/**
 * The mapping between `watch.toml` and [Watch], in both directions.
 *
 * The question this file asks is never "does it work" but "does it read and
 * write what the desktop reads and writes" — AM2's stated acceptance criterion.
 * So the central fixture is not invented: [DESKTOP_WRITTEN_FIXTURE] is the exact
 * bytes the desktop's `saat/storage.py` produced for [fullyPopulatedWatch], and
 * the first test simply demands that every one of those fields arrives intact.
 */
class WatchTomlTest {

    // ---- the parity load -------------------------------------------------

    @Test
    fun `a watch the desktop wrote loads with every field intact`() {
        val decoded = decodeWatch(DESKTOP_WRITTEN_FIXTURE)

        assertEquals(
            "a desktop-written file must produce exactly the same watch",
            fullyPopulatedWatch(),
            decoded.watch,
        )
        assertEquals(
            "a well-formed desktop file must need no forgiving: ${decoded.warnings}",
            emptyList<String>(),
            decoded.warnings,
        )
    }

    @Test
    fun `dates arrive as dates, not as strings`() {
        val w = decodeWatch(DESKTOP_WRITTEN_FIXTURE).watch

        assertEquals(LocalDate.of(2024, 3, 11), w.acquisition.date)
        assertEquals(LocalDate.of(2027, 3, 11), w.acquisition.warrantyUntil)
        assertEquals(LocalDate.of(2027, 1, 1), w.maintenance.batteryDue)
        assertEquals(
            listOf(LocalDate.of(2024, 3, 12), LocalDate.of(2024, 3, 13), LocalDate.of(2025, 1, 1)),
            w.worn,
        )
    }

    @Test
    fun `absent fields are null rather than zero or empty`() {
        val w = decodeWatch(
            """
            brand = "Casio"
            model = "F-91W"

            [case]
            diameter_mm = 38.2

            [[straps]]
            material = "Resin"
            """.trimIndent()
        ).watch

        assertNull("an unmeasured lug width is not 0", w.case.lugWidthMm)
        assertNull("an unrecorded material is not \"\"", w.case.material)
        assertNull("an unknown caliber is not \"\"", w.movement.caliber)
        assertNull(w.rating)
        assertNull(w.notes)
        assertNull("a strap with no width of its own is not 0", w.straps[0].widthMm)
        assertEquals(emptyList<String>(), w.tags)
        assertEquals(emptyList<LocalDate>(), w.worn)
        assertEquals(emptyList<TimingEntry>(), w.timing)
        assertFalse("a strap that does not claim to be fitted is not fitted", w.straps[0].fitted)
    }

    @Test
    fun `an absent status reads as Owned, matching the desktop`() {
        assertEquals(
            Watch.STATUS_OWNED,
            decodeWatch("brand = \"Casio\"\nmodel = \"F-91W\"").watch.status,
        )
        assertEquals(
            "Wishlist",
            decodeWatch("brand = \"A\"\nmodel = \"B\"\nstatus = \"Wishlist\"").watch.status,
        )
    }

    // ---- the round trip --------------------------------------------------

    @Test
    fun `every field survives a write and a read`() {
        val original = fullyPopulatedWatch()
        assertEquals(original, decodeWatch(encodeWatch(original)).watch)
    }

    @Test
    fun `writing twice produces identical bytes`() {
        val once = encodeWatch(fullyPopulatedWatch())
        val twice = encodeWatch(decodeWatch(once).watch)
        assertEquals("a save that changes nothing must change no bytes", once, twice)
    }

    @Test
    fun `a watch with only a brand and a model saves and loads`() {
        // SPEC-ANDROID 5.7: saving with only these two filled in must succeed.
        val emitted = encodeWatch(minimalWatch())

        assertEquals(minimalWatch(), decodeWatch(emitted).watch)
        assertFalse("no empty group headers: $emitted", emitted.contains("["))
        assertEquals(
            "brand, model and status, and nothing else",
            3,
            emitted.trim().lines().size,
        )
    }

    // ---- what the emitted file must never contain ------------------------

    @Test
    fun `no date is ever quoted`() {
        val emitted = encodeWatch(fullyPopulatedWatch())

        assertTrue(
            "acquisition.date must be a bare TOML date; got:\n$emitted",
            Regex("""^\s*date\s*=\s*2024-03-11\s*$""", RegexOption.MULTILINE).containsMatchIn(emitted),
        )
        assertFalse(
            "a quoted date is a plain string to the desktop's tomlkit; got:\n$emitted",
            Regex(""""\d{4}-\d{2}-\d{2}"""").containsMatchIn(emitted),
        )
    }

    @Test
    fun `no null literal is ever written`() {
        // TOML has no null. An emitted `notes = null` is a syntax error to every
        // conformant parser, the desktop's included — and every real watch has
        // absent fields, so this would have made every file the phone wrote
        // unreadable on the desktop.
        for (emitted in listOf(encodeWatch(fullyPopulatedWatch()), encodeWatch(minimalWatch()))) {
            assertFalse(
                "absent fields must be omitted, not written as null; got:\n$emitted",
                Regex("""=\s*null\b""").containsMatchIn(emitted),
            )
        }
    }

    @Test
    fun `every bare key is written before the first table header`() {
        // The trap this guards: after `[[log]]`, a bare `worn = [...]` belongs to
        // that log entry, so a top-level key written below a table silently
        // becomes log[1].worn and the whole wear history disappears. Asserted on
        // the real output rather than trusted to the emitter's ordering.
        val emitted = encodeWatch(fullyPopulatedWatch())
        val lines = emitted.lines()
        val firstHeader = lines.indexOfFirst { it.trimStart().startsWith("[") }

        assertTrue("the fixture is supposed to have tables", firstHeader > 0)
        val head = lines.take(firstHeader).joinToString("\n")

        for (key in TOP_LEVEL_KEYS) {
            assertTrue(
                "`$key` must appear before the first table header; got:\n$emitted",
                Regex("""^$key\s*=""", RegexOption.MULTILINE).containsMatchIn(head),
            )
        }
    }

    @Test
    fun `an empty group produces no header at all`() {
        val emitted = encodeWatch(
            Watch(brand = "Casio", model = "F-91W", movement = Movement(kind = "Quartz"))
        )

        assertTrue(emitted.contains("[movement]"))
        assertFalse("nothing in the case group was filled in", emitted.contains("[case]"))
        assertFalse(emitted.contains("[dial]"))
        assertFalse(emitted.contains("[acquisition]"))
        assertFalse(emitted.contains("[maintenance]"))
        assertFalse(emitted.contains("[[straps]]"))
    }

    @Test
    fun `unicode survives as text rather than as escapes`() {
        val emitted = encodeWatch(fullyPopulatedWatch())

        assertTrue("Turkish must survive as UTF-8; got:\n$emitted", emitted.contains("İzmir"))
        assertTrue(emitted.contains("Saat Dünyası"))
        assertFalse("no \\u escaping", emitted.contains("\\u0130"))
    }

    @Test
    fun `a multi-line note survives the round trip`() {
        val w = minimalWatch().copy(notes = "Line one.\nLine two.\n\nLine four with \" a quote.")
        assertEquals(w.notes, decodeWatch(encodeWatch(w)).watch.notes)
    }

    // ---- tolerance: coerced in silence -----------------------------------

    @Test
    fun `a quoted number reads as a number`() {
        val decoded = decodeWatch(
            """
            brand = "A"
            model = "B"
            rating = "4"

            [case]
            lug_width_mm = "20"
            weight_g = "100.5"
            """.trimIndent()
        )

        assertEquals(4, decoded.watch.rating)
        assertEquals(20, decoded.watch.case.lugWidthMm)
        assertEquals(100.5, decoded.watch.case.weightG!!, 1e-9)
        assertEquals("an unambiguous coercion is not worth a warning", emptyList<String>(), decoded.warnings)
    }

    @Test
    fun `a whole number where a decimal belongs reads as a decimal`() {
        // The single most likely hand-edit in the whole schema.
        val decoded = decodeWatch(
            """
            brand = "A"
            model = "B"

            [case]
            diameter_mm = 41
            thickness_mm = 12
            """.trimIndent()
        )

        assertEquals(41.0, decoded.watch.case.diameterMm!!, 1e-9)
        assertEquals(12.0, decoded.watch.case.thicknessMm!!, 1e-9)
        assertEquals(emptyList<String>(), decoded.warnings)
    }

    @Test
    fun `a decimal with no fraction reads as a whole number`() {
        val decoded = decodeWatch("brand = \"A\"\nmodel = \"B\"\nrating = 4.0")
        assertEquals(4, decoded.watch.rating)
        assertEquals(emptyList<String>(), decoded.warnings)
    }

    @Test
    fun `one and zero read as true and false`() {
        val decoded = decodeWatch(
            """
            brand = "A"
            model = "B"

            [movement]
            hacking = 1
            handwinding = 0
            """.trimIndent()
        )

        assertEquals(true, decoded.watch.movement.hacking)
        assertEquals(false, decoded.watch.movement.handwinding)
        assertEquals(emptyList<String>(), decoded.warnings)
    }

    @Test
    fun `a lone value where a list belongs reads as a one-item list`() {
        val decoded = decodeWatch("brand = \"A\"\nmodel = \"B\"\ntags = \"diver\"")
        assertEquals(listOf("diver"), decoded.watch.tags)
        assertEquals(emptyList<String>(), decoded.warnings)
    }

    @Test
    fun `a single strap table reads as a list of one`() {
        // `[straps]` where `[[straps]]` was meant — one missing bracket.
        val decoded = decodeWatch(
            """
            brand = "A"
            model = "B"

            [straps]
            material = "NATO"
            fitted = true
            """.trimIndent()
        )

        assertEquals(1, decoded.watch.straps.size)
        assertEquals("NATO", decoded.watch.straps[0].material)
        assertTrue(decoded.watch.straps[0].fitted)
    }

    @Test
    fun `a timestamp where a plain day belongs keeps the day`() {
        val decoded = decodeWatch(
            """
            brand = "A"
            model = "B"
            worn = [2024-03-12T09:30:00]

            [acquisition]
            date = "2024-03-11"
            """.trimIndent()
        )

        assertEquals(listOf(LocalDate.of(2024, 3, 12)), decoded.watch.worn)
        assertEquals(LocalDate.of(2024, 3, 11), decoded.watch.acquisition.date)
    }

    // ---- tolerance: warned about and left absent -------------------------

    @Test
    fun `a value that cannot be a number costs its own field and nothing else`() {
        val decoded = decodeWatch(
            """
            brand = "Seiko"
            model = "SKX007"
            rating = "high"

            [case]
            diameter_mm = 42.5
            """.trimIndent()
        )

        assertNull("the field it could not read", decoded.watch.rating)
        assertEquals("everything else must still load", "Seiko", decoded.watch.brand)
        assertEquals(42.5, decoded.watch.case.diameterMm!!, 1e-9)

        assertEquals(1, decoded.warnings.size)
        assertTrue(
            "the warning must name the field and quote the value: ${decoded.warnings}",
            decoded.warnings.single().startsWith("rating:") &&
                decoded.warnings.single().contains("\"high\""),
        )
    }

    @Test
    fun `a warning names the exact path inside a list`() {
        val decoded = decodeWatch(
            """
            brand = "A"
            model = "B"

            [[straps]]
            material = "NATO"

            [[straps]]
            material = "Leather"
            width_mm = "wide"
            """.trimIndent()
        )

        assertNull(decoded.watch.straps[1].widthMm)
        assertEquals("Leather", decoded.watch.straps[1].material)
        assertTrue(
            "expected straps[1].width_mm in ${decoded.warnings}",
            decoded.warnings.single().startsWith("straps[1].width_mm:"),
        )
    }

    @Test
    fun `an unreadable date in the worn list costs one day, not the list`() {
        val decoded = decodeWatch(
            """
            brand = "A"
            model = "B"
            worn = [2024-03-12, "not a date", 2024-03-14]
            """.trimIndent()
        )

        assertEquals(
            listOf(LocalDate.of(2024, 3, 12), LocalDate.of(2024, 3, 14)),
            decoded.watch.worn,
        )
        assertTrue(
            "expected worn[1] in ${decoded.warnings}",
            decoded.warnings.single().startsWith("worn[1]:"),
        )
    }

    @Test
    fun `a group where a single value belongs is reported rather than crashing`() {
        val decoded = decodeWatch(
            """
            brand = "A"
            model = "B"

            [notes]
            text = "oops"
            """.trimIndent()
        )

        assertNull(decoded.watch.notes)
        assertTrue(decoded.warnings.single().startsWith("notes:"))
    }

    @Test
    fun `two fitted straps are reported, not silently corrected`() {
        val decoded = decodeWatch(
            """
            brand = "A"
            model = "B"

            [[straps]]
            material = "Bracelet"
            fitted = true

            [[straps]]
            material = "Leather"
            fitted = true
            """.trimIndent()
        )

        assertEquals("the file says what it says", 2, decoded.watch.straps.fittedCount())
        assertTrue(
            "expected a straps warning in ${decoded.warnings}",
            decoded.warnings.single().startsWith("straps:"),
        )
        // The correction is available, but it is the form's to apply.
        assertEquals(1, decoded.watch.straps.withSingleFitted().fittedCount())
    }

    @Test
    fun `unknown keys from a future version are ignored, not fatal`() {
        val decoded = decodeWatch(
            """
            brand = "A"
            model = "B"
            future_field_from_a_later_version = "surprise"

            [movement]
            caliber = "Cal. 42"
            unknown_nested = 1

            [a_whole_future_section]
            whatever = true
            """.trimIndent()
        )

        assertEquals("Cal. 42", decoded.watch.movement.caliber)
        assertEquals(emptyList<String>(), decoded.warnings)
    }

    @Test
    fun `comments and odd spacing do not trouble the reader`() {
        val decoded = decodeWatch(
            """
            # A hand-written comment.
            brand   =    "Züblin"     # trailing comment
            model="Ébauche"

            [movement]   # another
            caliber = "Cal. 42"
            """.trimIndent()
        )

        assertEquals("Züblin", decoded.watch.brand)
        assertEquals("Ébauche", decoded.watch.model)
        assertEquals("Cal. 42", decoded.watch.movement.caliber)
    }

    // ---- the two fatal cases ---------------------------------------------

    @Test
    fun `TOML that will not parse is fatal`() {
        val e = runCatching { decodeWatch("this is not = = valid toml [[[") }.exceptionOrNull()
        assertTrue("expected a WatchFormatException, got $e", e is WatchFormatException)
    }

    @Test
    fun `a missing brand or model is fatal`() {
        for (source in listOf(
            "model = \"F-91W\"",
            "brand = \"Casio\"",
            "brand = \"\"\nmodel = \"F-91W\"",
            "brand = \"   \"\nmodel = \"F-91W\"",
            "",
        )) {
            val e = runCatching { decodeWatch(source) }.exceptionOrNull()
            assertTrue("expected a fatal error for:\n$source\ngot $e", e is WatchFormatException)
            assertTrue(
                "the message must name the missing field: ${e?.message}",
                e?.message.orEmpty().contains("brand") || e?.message.orEmpty().contains("model"),
            )
        }
    }

    @Test
    fun `nothing else in the schema is fatal`() {
        // Every field of the wrong type at once. The watch still loads, and
        // every mistake is reported.
        val decoded = decodeWatch(
            """
            brand = "A"
            model = "B"
            rating = "no"
            tags = { not = "a list" }

            [movement]
            bph = "fast"
            hacking = "maybe"

            [case]
            diameter_mm = "wide"

            [acquisition]
            date = "sometime"
            """.trimIndent()
        )

        assertEquals("A", decoded.watch.brand)
        assertEquals(6, decoded.warnings.size)
    }

    private companion object {
        /** The keys that live at the top level of the file, per docs/schema.md. */
        val TOP_LEVEL_KEYS = listOf(
            "brand", "model", "reference", "nickname", "serial", "group", "style",
            "status", "storage", "rating", "tags", "worn", "notes", "images",
        )
    }
}
