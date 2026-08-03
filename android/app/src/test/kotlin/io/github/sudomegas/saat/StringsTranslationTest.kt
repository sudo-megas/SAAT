package io.github.sudomegas.saat

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory
import org.w3c.dom.Element

/**
 * Turkish covers everything English does — AM11a.
 *
 * `StringsConventionTest` guards that no literal escapes into a composable.
 * This guards the other half: that every resource which exists has a Turkish
 * translation, and that the two agree about format arguments.
 *
 * BOTH FAILURES ARE INVISIBLE WITHOUT A TEST, and they fail differently.
 * A missing translation is silent — Android falls back to `values/` and the
 * screen simply comes up in English, which nobody notices until a Turkish
 * speaker uses that one screen. A MISMATCHED FORMAT ARGUMENT is not silent at
 * all: `stringResource(id, a, b)` against a Turkish string that expects three
 * arguments throws at draw time, in Turkish only, on a screen the English
 * developer never sees fail.
 *
 * A string added in a later milestone therefore cannot quietly ship
 * untranslated, which is the state AM11 exists to leave behind.
 */
class StringsTranslationTest {

    private data class Resources(
        val strings: Map<String, String>,
        val plurals: Map<String, Map<String, String>>,
    )

    private fun read(path: String): Resources {
        val file = File(path)
        check(file.exists()) { "missing ${file.absolutePath}" }
        val doc = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(file)

        val strings = mutableMapOf<String, String>()
        val plurals = mutableMapOf<String, Map<String, String>>()

        val stringNodes = doc.getElementsByTagName("string")
        for (i in 0 until stringNodes.length) {
            val element = stringNodes.item(i) as Element
            // translatable="false" is a declaration that this string is NOT
            // vocabulary — a URL, a brand, a format. Requiring a translation for
            // one would be requiring a second copy of a constant.
            if (element.getAttribute("translatable") == "false") continue
            strings[element.getAttribute("name")] = element.textContent
        }

        val pluralNodes = doc.getElementsByTagName("plurals")
        for (i in 0 until pluralNodes.length) {
            val element = pluralNodes.item(i) as Element
            val items = element.getElementsByTagName("item")
            plurals[element.getAttribute("name")] = (0 until items.length).associate {
                val item = items.item(it) as Element
                item.getAttribute("quantity") to item.textContent
            }
        }
        return Resources(strings, plurals)
    }

    private val english = read(ENGLISH)
    private val turkish = read(TURKISH)

    /** `%1$s`, `%2$d` … as a set, which is what has to match across languages. */
    private fun arguments(text: String): Set<String> =
        Regex("""%(\d+)\$[sd]""").findAll(text).map { it.groupValues[1] }.toSet()

    @Test
    fun `every English string has a Turkish translation`() {
        val untranslated = english.strings.keys - turkish.strings.keys

        assertTrue(
            "no Turkish for: ${untranslated.sorted()}\n" +
                "Android falls back to values/ silently, so these would ship in " +
                "English and nobody would see a failure.",
            untranslated.isEmpty(),
        )
    }

    @Test
    fun `every English plural has a Turkish translation`() {
        assertEquals(english.plurals.keys.sorted(), turkish.plurals.keys.sorted())
    }

    /** A key only Turkish has is a rename half-done, or a typo nothing reads. */
    @Test
    fun `Turkish adds no keys of its own`() {
        assertEquals(emptySet<String>(), turkish.strings.keys - english.strings.keys)
    }

    /**
     * The one that crashes rather than degrading. A Turkish string expecting an
     * argument the call site does not pass throws at draw time — in Turkish
     * only, on a screen nobody testing in English will ever see fail.
     */
    @Test
    fun `format arguments match between the two languages`() {
        val mismatched = english.strings.mapNotNull { (key, text) ->
            val translated = turkish.strings[key] ?: return@mapNotNull null
            val expected = arguments(text)
            val actual = arguments(translated)
            if (expected == actual) null else "$key: en=$expected tr=$actual"
        }

        assertTrue("format arguments differ:\n${mismatched.joinToString("\n")}", mismatched.isEmpty())
    }

    /**
     * Turkish carries BOTH `one` and `other`.
     *
     * An earlier draft of values-tr shipped only `other`, on the belief that
     * Turkish has a single plural category. It does not: CLDR gives Turkish
     * `one` for `i = 1 and v = 0`, and Android lint says so — `MissingQuantity`
     * is an error, not a warning. What differs from English is the grammar
     * rather than the category, so the two forms read alike ("1 gün", "3 gün",
     * neither taking a plural suffix), but both must be present or lint fails
     * the build.
     */
    @Test
    fun `every Turkish plural carries both quantities`() {
        val missing = turkish.plurals
            .filterValues { forms -> "one" !in forms || "other" !in forms }
            .keys

        assertTrue(
            "Turkish needs `one` AND `other` — CLDR gives it both, and lint " +
                "fails the build without them: $missing",
            missing.isEmpty(),
        )
    }

    /**
     * Every Turkish plural form must still carry its count argument, or the
     * reader gets "gün önce" with no number in it.
     */
    @Test
    fun `Turkish plurals keep their count argument`() {
        val argumentless = turkish.plurals
            .filterValues { forms -> forms.values.any { arguments(it).isEmpty() } }
            .keys

        assertTrue("no count in a Turkish form of: $argumentless", argumentless.isEmpty())
    }

    /**
     * The language names are deliberately NOT translated — each is written in
     * its own tongue so an owner who has just switched to a language they
     * cannot read can still find their way back.
     */
    @Test
    fun `the language names read the same in both files`() {
        listOf("settings_language_en", "settings_language_tr").forEach { key ->
            assertEquals(
                "$key must name its language in its own tongue in both files",
                english.strings[key],
                turkish.strings[key],
            )
        }
    }

    companion object {
        private const val ENGLISH = "src/main/res/values/strings.xml"
        private const val TURKISH = "src/main/res/values-tr/strings.xml"
    }
}
