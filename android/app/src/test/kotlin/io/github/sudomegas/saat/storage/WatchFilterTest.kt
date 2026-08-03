package io.github.sudomegas.saat.storage

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.time.LocalDate

/**
 * The filter facets and the collection summary — SPEC-ANDROID 5.11 and 5.12.
 *
 * `today` is a parameter throughout, so the 90-day facet is tested against
 * stated dates rather than against whatever day the suite happens to run on.
 */
class WatchFilterTest {

    private val today = LocalDate.of(2026, 8, 3)

    private fun watch(
        brand: String = "Seiko",
        model: String = "SKX007",
        style: String? = null,
        group: String? = null,
        status: String = Watch.STATUS_OWNED,
        kind: String? = null,
        material: String? = null,
        lugWidth: Int? = null,
        tags: List<String> = emptyList(),
        worn: List<LocalDate> = emptyList(),
        price: Double? = null,
        currency: String? = null,
    ) = Watch(
        brand = brand,
        model = model,
        style = style,
        group = group,
        status = status,
        tags = tags,
        movement = Movement(kind = kind),
        case = Case(material = material, lugWidthMm = lugWidth),
        acquisition = Acquisition(price = price, currency = currency),
        worn = worn,
    )

    private fun records(vararg watches: Watch) = watches.mapIndexed { index, watch ->
        WatchRecord("w$index", File("/watches/w$index"), watch = watch, loaded = watch)
    }

    private fun facet(watches: List<Watch>, filter: WatchFilter, kind: FacetKind) =
        watches.facets(filter, today).firstOrNull { it.kind == kind }

    // --- matching -----------------------------------------------------------

    @Test
    fun `an empty filter matches everything`() {
        // The line that decides whether an untouched sheet shows the collection
        // or nothing at all.
        val all = listOf(watch(style = "Diver"), watch(), watch(status = "Sold"))

        assertTrue(all.all { it.matches(WatchFilter(), today) })
    }

    @Test
    fun `values within one facet are ORed`() {
        val diver = watch(style = "Diver")
        val field = watch(style = "Field")
        val dress = watch(style = "Dress")
        val filter = WatchFilter(styles = setOf("Diver", "Field"))

        assertTrue(diver.matches(filter, today))
        assertTrue(field.matches(filter, today))
        assertFalse(dress.matches(filter, today))
    }

    @Test
    fun `facets are ANDed across kinds`() {
        val filter = WatchFilter(styles = setOf("Diver"), movementKinds = setOf("Automatic"))

        assertTrue(watch(style = "Diver", kind = "Automatic").matches(filter, today))
        assertFalse(watch(style = "Diver", kind = "Quartz").matches(filter, today))
        assertFalse(watch(style = "Dress", kind = "Automatic").matches(filter, today))
    }

    @Test
    fun `a watch matches a tag facet if it carries any of the tags`() {
        val filter = WatchFilter(tags = setOf("grail", "daily"))

        assertTrue(watch(tags = listOf("daily", "beater")).matches(filter, today))
        assertFalse(watch(tags = listOf("beater")).matches(filter, today))
        assertFalse(watch().matches(filter, today))
    }

    // --- the 90-day facet ---------------------------------------------------

    @Test
    fun `not worn in 90 days counts from the last worn date`() {
        val recent = watch(worn = listOf(today.minusDays(89)))
        val stale = watch(worn = listOf(today.minusDays(90)))
        val filter = WatchFilter(notWornIn90Days = true)

        assertFalse("89 days is still recent", recent.matches(filter, today))
        assertTrue("90 days is the threshold", stale.matches(filter, today))
    }

    @Test
    fun `a watch never worn is the strongest answer the facet has`() {
        // Excluding it because it has no last-worn date would leave the facet
        // answering a subtly different question from the one it is labelled
        // with.
        assertTrue(watch().matches(WatchFilter(notWornIn90Days = true), today))
    }

    @Test
    fun `a watch worn today is not stale, and neither is one recorded ahead`() {
        val filter = WatchFilter(notWornIn90Days = true)

        assertFalse(watch(worn = listOf(today)).matches(filter, today))
        // A planned day gives a negative interval; it must not read as "long ago".
        assertFalse(watch(worn = listOf(today.plusDays(7))).matches(filter, today))
    }

    // --- facet building -----------------------------------------------------

    @Test
    fun `a facet with no values across the collection is not offered`() {
        // SPEC-ANDROID 5.12: "facets with no values hidden". A collection where
        // nobody recorded a case material should not be shown a Case material
        // heading with nothing under it.
        val watches = listOf(watch(style = "Diver"), watch(style = "Field"))
        val kinds = watches.facets(WatchFilter(), today).map { it.kind }

        assertTrue(FacetKind.STYLE in kinds)
        assertFalse(FacetKind.CASE_MATERIAL in kinds)
        assertFalse(FacetKind.TAG in kinds)
    }

    @Test
    fun `an empty collection offers no facets at all`() {
        assertEquals(emptyList<Facet>(), emptyList<Watch>().facets(WatchFilter(), today))
    }

    @Test
    fun `counts say how many watches each value holds`() {
        val watches = listOf(
            watch(style = "Diver"),
            watch(style = "Diver"),
            watch(style = "Field"),
        )

        assertEquals(
            listOf(FacetValue("Diver", 2), FacetValue("Field", 1)),
            facet(watches, WatchFilter(), FacetKind.STYLE)!!.values,
        )
    }

    @Test
    fun `a facet's own counts ignore its own selection`() {
        // The behaviour that makes the numbers useful rather than tautological:
        // having picked Diver, the Style facet still says how many Field
        // watches are one tap away. Counting against the fully-filtered set
        // would show 0 beside every value you had not picked.
        val watches = listOf(
            watch(style = "Diver"),
            watch(style = "Diver"),
            watch(style = "Field"),
        )
        val filter = WatchFilter(styles = setOf("Diver"))

        assertEquals(
            listOf(FacetValue("Diver", 2), FacetValue("Field", 1)),
            facet(watches, filter, FacetKind.STYLE)!!.values,
        )
    }

    @Test
    fun `other facets do narrow as you go`() {
        val watches = listOf(
            watch(style = "Diver", kind = "Automatic"),
            watch(style = "Field", kind = "Quartz"),
        )
        val filter = WatchFilter(styles = setOf("Diver"))

        // Quartz stays visible at zero rather than vanishing: a value that
        // disappeared as you narrowed would make the sheet appear to lose
        // options you could still get back by unpicking Diver.
        assertEquals(
            listOf(FacetValue("Automatic", 1), FacetValue("Quartz", 0)),
            facet(watches, filter, FacetKind.MOVEMENT_KIND)!!.values,
        )
    }

    @Test
    fun `lug widths sort as numbers, not as strings`() {
        val watches = listOf(watch(lugWidth = 22), watch(lugWidth = 8), watch(lugWidth = 20))

        assertEquals(
            listOf("8", "20", "22"),
            facet(watches, WatchFilter(), FacetKind.LUG_WIDTH)!!.values.map { it.value },
        )
    }

    @Test
    fun `a blank value is not a facet value`() {
        val watches = listOf(watch(style = "  "), watch(style = "Diver"), watch(style = null))

        assertEquals(
            listOf(FacetValue("Diver", 1)),
            facet(watches, WatchFilter(), FacetKind.STYLE)!!.values,
        )
    }

    // --- the pipeline -------------------------------------------------------

    @Test
    fun `a facet and a search narrow together`() {
        val records = records(
            watch(brand = "Seiko", model = "SKX007", style = "Diver"),
            watch(brand = "Seiko", model = "SARB033", style = "Dress"),
            watch(brand = "Citizen", model = "NY0040", style = "Diver"),
        )

        val result = records.filtered(
            filter = WatchFilter(styles = setOf("Diver")),
            search = "seiko",
            sort = WatchSort.BRAND,
            today = today,
        )

        assertEquals(listOf("SKX007"), result.map { it.watch!!.model })
    }

    @Test
    fun `filtering keeps the sort it was given`() {
        val records = records(
            watch(brand = "Zenith", style = "Diver"),
            watch(brand = "Aera", style = "Diver"),
        )

        val result = records.filtered(WatchFilter(styles = setOf("Diver")), "", WatchSort.BRAND, today)

        assertEquals(listOf("Aera", "Zenith"), result.map { it.watch!!.brand })
    }

    @Test
    fun `a record that did not load never survives the filter`() {
        val broken = WatchRecord("broken", File("/watches/broken"), loadError = "line 3")

        assertEquals(emptyList<WatchRecord>(), listOf(broken).filtered(WatchFilter(), "", WatchSort.BRAND, today))
    }

    // --- toggling -----------------------------------------------------------

    @Test
    fun `toggling adds then removes, and the boolean facet behaves like any other`() {
        val once = WatchFilter().toggle(FacetKind.STYLE, "Diver")
        assertEquals(setOf("Diver"), once.styles)
        assertTrue(WatchFilter().toggle(FacetKind.NOT_WORN_90, WatchFilter.NOT_WORN_VALUE).notWornIn90Days)

        val twice = once.toggle(FacetKind.STYLE, "Diver")
        assertTrue(twice.isEmpty)
        assertEquals(WatchFilter(), twice)
    }

    // --- the summary --------------------------------------------------------

    @Test
    fun `the summary counts watches and splits them by movement kind`() {
        val summary = listOf(
            watch(kind = "Automatic"),
            watch(kind = "Automatic"),
            watch(kind = "Quartz"),
            watch(),
        ).summarise()

        assertEquals(4, summary.watchCount)
        // Commonest first, ties alphabetically, so the footer cannot reshuffle
        // between emissions. A watch with no recorded kind is counted in the
        // total and in no split, which is the honest answer.
        assertEquals(listOf("Automatic" to 2, "Quartz" to 1), summary.byMovementKind)
    }

    @Test
    fun `acquisition value totals per currency and never mixes them`() {
        val summary = listOf(
            watch(price = 850.0, currency = "TRY"),
            watch(price = 150.5, currency = "TRY"),
            watch(price = 300.0, currency = "EUR"),
            watch(),
        ).summarise()

        assertEquals(listOf("EUR" to 300.0, "TRY" to 1000.5), summary.valueByCurrency)
    }

    @Test
    fun `a price with no currency is counted, not dropped`() {
        // It is still money the owner spent. Folding it into TRY would be
        // inventing a fact about what was paid, so it totals under the empty
        // key and the footer renders it as an unlabelled figure.
        val summary = listOf(watch(price = 500.0)).summarise()

        assertEquals(listOf("" to 500.0), summary.valueByCurrency)
    }

    @Test
    fun `an empty collection summarises to zero rather than to nothing`() {
        val summary = emptyList<Watch>().summarise()

        assertEquals(0, summary.watchCount)
        assertEquals(emptyList<Pair<String, Int>>(), summary.byMovementKind)
        assertEquals(emptyList<Pair<String, Double>>(), summary.valueByCurrency)
    }
}
