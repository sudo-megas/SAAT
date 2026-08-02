package io.github.sudomegas.saat.storage

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.time.LocalDate
import java.util.Locale

/**
 * Search and sort, the two things AM6's Specs list reuses verbatim.
 *
 * The milestone insists the matcher lives in the repository layer rather than in
 * a composable, and this file is the payoff: every interesting decision is
 * testable on a plain JVM with no device and no Robolectric.
 *
 * `today` is injected everywhere. A test that called `LocalDate.now()` would
 * pass for a year and then fail on some particular Tuesday.
 */
class WatchQueryTest {

    private val today = LocalDate.of(2026, 3, 14)

    private var originalLocale: Locale = Locale.getDefault()

    @After
    fun restoreLocale() {
        Locale.setDefault(originalLocale)
    }

    private fun record(
        slug: String,
        watch: Watch?,
    ) = WatchRecord(slug = slug, dir = File(slug), watch = watch, loaded = watch)

    private fun watch(
        brand: String = "Seiko",
        model: String = "SKX007",
        reference: String? = null,
        caliber: String? = null,
        tags: List<String> = emptyList(),
        acquired: LocalDate? = null,
        worn: List<LocalDate> = emptyList(),
    ) = Watch(
        brand = brand,
        model = model,
        reference = reference,
        tags = tags,
        movement = Movement(caliber = caliber),
        acquisition = Acquisition(date = acquired),
        worn = worn,
    )

    // ---- fuzzy matching --------------------------------------------------

    @Test
    fun `a subsequence matches, with gaps allowed`() {
        assertTrue(fuzzyMatch("gs", "Grand Seiko"))
        assertTrue(fuzzyMatch("grsk", "Grand Seiko"))
        assertTrue(fuzzyMatch("Grand Seiko", "Grand Seiko"))
    }

    @Test
    fun `characters out of order do not match`() {
        assertFalse(fuzzyMatch("sg", "Grand Seiko"))
        assertFalse(fuzzyMatch("zzz", "Grand Seiko"))
    }

    @Test
    fun `an empty or blank query matches everything`() {
        assertTrue(fuzzyMatch("", "anything"))
        assertTrue(watch().matchesSearch(""))
        assertTrue(watch().matchesSearch("   "))
    }

    @Test
    fun `matching is per field, never across the concatenation`() {
        // The trap the desktop's search.py calls out by name. Concatenating the
        // fields would let "sksk" borrow the s and k from the brand and then the
        // s and k from the model, producing a hit the owner cannot explain.
        val seiko = watch(brand = "Seiko", model = "SKX007")

        assertTrue(seiko.matchesSearch("seiko"))
        assertTrue(seiko.matchesSearch("skx"))
        assertFalse("a query must match within ONE field", seiko.matchesSearch("sksk"))
    }

    @Test
    fun `reference, caliber and every tag are searchable`() {
        val subject = watch(
            brand = "Grand Seiko",
            model = "SBGA211",
            reference = "SBGA211G",
            caliber = "9R65",
            tags = listOf("grail", "dress"),
        )

        assertTrue(subject.matchesSearch("211g"))
        assertTrue(subject.matchesSearch("9r65"))
        assertTrue(subject.matchesSearch("grail"))
        assertTrue("every tag, not just the first", subject.matchesSearch("dress"))
    }

    @Test
    fun `search is case-insensitive on a Turkish phone`() {
        // The dotless-i trap, arriving by a different door than Slugs'. Under
        // tr-TR, lowercase(Locale.getDefault()) maps I to ı, so "iwc" would stop
        // matching "IWC" — on the one device this app is actually built for.
        val watches = listOf(
            record("iwc-mark-xviii", watch(brand = "IWC", model = "Mark XVIII")),
            record("seiko-skx007", watch(brand = "Seiko", model = "SKX007")),
        )

        Locale.setDefault(Locale.ENGLISH)
        val inEnglish = watches.query("iwc", WatchSort.BRAND, today).map { it.slug }

        Locale.setDefault(Locale.forLanguageTag("tr-TR"))
        val inTurkish = watches.query("iwc", WatchSort.BRAND, today).map { it.slug }

        assertEquals(listOf("iwc-mark-xviii"), inEnglish)
        assertEquals("the whole result list must be identical", inEnglish, inTurkish)
    }

    // ---- sorting ---------------------------------------------------------

    @Test
    fun `brand order ignores case`() {
        // Raw string order would put every capitalised brand ahead of every
        // lowercase one, which reads as a bug rather than as a convention.
        val records = listOf(
            record("zenith", watch(brand = "Zenith")),
            record("rolex", watch(brand = "rolex")),
            record("iwc", watch(brand = "IWC")),
        )

        assertEquals(
            listOf("iwc", "rolex", "zenith"),
            records.query("", WatchSort.BRAND, today).map { it.slug },
        )
    }

    @Test
    fun `acquired newest first puts watches with no date last`() {
        val records = listOf(
            record("unknown", watch(brand = "A", acquired = null)),
            record("older", watch(brand = "B", acquired = LocalDate.of(2020, 1, 1))),
            record("newer", watch(brand = "C", acquired = LocalDate.of(2024, 1, 1))),
        )

        // "We do not know when you bought it" is not "you bought it most
        // recently" — reversing the whole comparator would float nulls to the top.
        assertEquals(
            listOf("newer", "older", "unknown"),
            records.query("", WatchSort.ACQUIRED, today).map { it.slug },
        )
    }

    @Test
    fun `least worn puts never-worn first, then longest since worn`() {
        val records = listOf(
            record("worn-today", watch(brand = "A", worn = listOf(today))),
            record("never", watch(brand = "B", worn = emptyList())),
            record("long-ago", watch(brand = "C", worn = listOf(today.minusDays(200)))),
            record("recent", watch(brand = "D", worn = listOf(today.minusDays(3)))),
        )

        assertEquals(
            listOf("never", "long-ago", "recent", "worn-today"),
            records.query("", WatchSort.LEAST_WORN, today).map { it.slug },
        )
    }

    @Test
    fun `a watch recorded as worn tomorrow sorts last under least worn`() {
        // daysSinceWorn goes negative for a future date, which negates to a
        // positive key. A watch worn "tomorrow" is the opposite of least worn,
        // and this is the honest answer rather than a clamp.
        val records = listOf(
            record("future", watch(brand = "A", worn = listOf(today.plusDays(1)))),
            record("today", watch(brand = "B", worn = listOf(today))),
            record("never", watch(brand = "C")),
        )

        assertEquals(
            listOf("never", "today", "future"),
            records.query("", WatchSort.LEAST_WORN, today).map { it.slug },
        )
    }

    @Test
    fun `ties break on the slug so the order is total`() {
        // Without a total order, two identical watches could swap between
        // emissions and the grid would visibly twitch.
        val records = listOf(
            record("b-one", watch(brand = "Same", model = "Same")),
            record("a-two", watch(brand = "Same", model = "Same")),
        )

        assertEquals(
            listOf("a-two", "b-one"),
            records.query("", WatchSort.BRAND, today).map { it.slug },
        )
    }

    @Test
    fun `records that failed to load are excluded from results`() {
        // They have no fields to match and no values to sort by. The grid
        // surfaces them as a notice instead of as cards.
        val records = listOf(
            record("broken", null).copy(loadError = "not valid UTF-8"),
            record("fine", watch(brand = "Seiko")),
        )

        assertEquals(
            listOf("fine"),
            records.query("", WatchSort.BRAND, today).map { it.slug },
        )
    }

    // ---- the persisted token --------------------------------------------

    @Test
    fun `every sort has a stable token and unknown tokens fall back`() {
        // The token is what reaches config.toml, so renaming a constant must not
        // silently invalidate a stored preference.
        assertEquals(
            listOf("brand", "model", "acquired", "least_worn"),
            WatchSort.entries.map { it.token },
        )
        WatchSort.entries.forEach {
            assertEquals(it, WatchSort.fromToken(it.token))
        }
        assertEquals(WatchSort.DEFAULT, WatchSort.fromToken("from_a_later_version"))
        assertEquals(WatchSort.DEFAULT, WatchSort.fromToken(null))
    }
}
