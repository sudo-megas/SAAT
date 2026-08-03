package io.github.sudomegas.saat.storage

import io.github.sudomegas.saat.ui.form.CASE_MATERIALS
import io.github.sudomegas.saat.ui.form.CLASPS
import io.github.sudomegas.saat.ui.form.CONDITIONS
import io.github.sudomegas.saat.ui.form.EnumChoice
import io.github.sudomegas.saat.ui.form.GROUPS
import io.github.sudomegas.saat.ui.form.LOG_KINDS
import io.github.sudomegas.saat.ui.form.MOVEMENT_KINDS
import io.github.sudomegas.saat.ui.form.STATUSES
import io.github.sudomegas.saat.ui.form.STRAP_MATERIALS
import io.github.sudomegas.saat.ui.form.STYLES
import io.github.sudomegas.saat.ui.form.TIMING_POSITIONS
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File
import java.util.Locale

/**
 * STORAGE IS CANONICAL ENGLISH — SPEC-ANDROID hard rule 7, and AM11a's own
 * acceptance test: "a file written under one UI language loads identically
 * under the other".
 *
 * The rule has two halves and they fail in different ways:
 *
 *  1. **The vocabulary is data.** `Automatic` is what lands in `watch.toml`
 *     whatever the interface says, so the two apps and the two languages all
 *     read one collection. The form already keeps value and label apart
 *     (`EnumChoice`), and this asserts that no label ever leaked into the value
 *     side of that pair.
 *  2. **The encoder must not be locale-sensitive.** This is the subtle one, and
 *     Turkish is precisely the locale that exposes it: `"I".lowercase()` in a
 *     Turkish locale gives `ı`, not `i`, and `String.format` with a Turkish
 *     default locale writes `3,5` for three and a half rather than `3.5` —
 *     which is not valid TOML for a float. A file written on a phone set to
 *     Turkish would then be unreadable by the desktop, and the failure would
 *     look like corruption rather than like a locale bug.
 *
 * The second half is checked by actually swapping `Locale.getDefault()` to
 * Turkish and writing the file, rather than by reading the encoder and
 * reasoning about it.
 */
class LanguageIndependenceTest {

    private lateinit var original: Locale

    @Before
    fun setUp() {
        original = Locale.getDefault()
    }

    @After
    fun tearDown() {
        Locale.setDefault(original)
    }

    private val turkish = Locale.forLanguageTag("tr-TR")

    // --- the vocabulary is data -----------------------------------------------

    /**
     * Every stored value is ASCII English. A Turkish label that had leaked into
     * the value side would show up here as a non-ASCII character — `ı`, `ş`, `ğ`
     * — long before it reached a file the desktop had to read.
     */
    @Test
    fun `every enum value the form can write is canonical English`() {
        val lists: List<List<EnumChoice>> = listOf(
            GROUPS, STYLES, STATUSES, MOVEMENT_KINDS, CASE_MATERIALS,
            STRAP_MATERIALS, CLASPS, CONDITIONS, LOG_KINDS, TIMING_POSITIONS,
        )

        val nonAscii = lists.flatten()
            .map { it.value }
            .filter { value -> value.any { it.code > 127 } }

        assertTrue(
            "these values are not canonical English — a label has leaked into " +
                "the value side of EnumChoice: $nonAscii",
            nonAscii.isEmpty(),
        )
    }

    @Test
    fun `the status the model defaults to is the English one the desktop writes`() {
        assertEquals("Owned", Watch.STATUS_OWNED)
        assertTrue(STATUSES.any { it.value == Watch.STATUS_OWNED })
    }

    // --- the encoder is not locale-sensitive ----------------------------------

    /**
     * THE TEST AM11a ASKS FOR. The same watch, encoded under an English default
     * locale and under a Turkish one, must produce the same bytes — and each
     * must load back to the same watch.
     */
    @Test
    fun `a watch written under Turkish is byte-identical to one written under English`() {
        Locale.setDefault(Locale.ENGLISH)
        val underEnglish = encodeWatch(fullyPopulatedWatch())

        Locale.setDefault(turkish)
        val underTurkish = encodeWatch(fullyPopulatedWatch())

        assertEquals(
            "the encoder is locale-sensitive — under a Turkish default locale " +
                "String.format writes 3,5 for 3.5, which is not valid TOML",
            underEnglish,
            underTurkish,
        )
    }

    @Test
    fun `a file written under Turkish loads identically under English`() {
        Locale.setDefault(turkish)
        val written = encodeWatch(fullyPopulatedWatch())

        Locale.setDefault(Locale.ENGLISH)
        val readBack = decodeWatch(written).watch

        assertEquals(fullyPopulatedWatch(), readBack)
    }

    @Test
    fun `and the other way round`() {
        Locale.setDefault(Locale.ENGLISH)
        val written = encodeWatch(fullyPopulatedWatch())

        Locale.setDefault(turkish)
        val readBack = decodeWatch(written).watch

        assertEquals(fullyPopulatedWatch(), readBack)
    }

    /**
     * The dotless-i trap, at the layer that would actually meet it. Slugs are
     * lowercased, and `"I".lowercase()` under a Turkish locale gives `ı` — a
     * character that is not ASCII and would produce a different folder name for
     * the same watch depending on what language the phone was set to.
     */
    @Test
    fun `a slug is the same under both locales`() {
        Locale.setDefault(Locale.ENGLISH)
        val underEnglish = slugify("İzmir Watch Co", "INDEX I")

        Locale.setDefault(turkish)
        val underTurkish = slugify("İzmir Watch Co", "INDEX I")

        assertEquals(underEnglish, underTurkish)
    }

    // --- the whole storage layer, under Turkish -------------------------------

    /**
     * The round trip through real files, with the phone set to Turkish
     * throughout: written, listed, read back, and equal.
     */
    @Test
    fun `the storage layer round-trips under a Turkish default locale`() {
        Locale.setDefault(turkish)

        val root = File.createTempFile("saat-tr", "").let {
            it.delete()
            it.mkdirs()
            it
        }
        try {
            val paths = SaatPaths(root)
            val store = WatchStore(paths)
            val created = store.create(fullyPopulatedWatch())

            val loaded = store.loadCollection().single()
            assertEquals(created.slug, loaded.slug)
            assertEquals(fullyPopulatedWatch(), loaded.watch)
        } finally {
            root.deleteRecursively()
        }
    }
}
