package io.github.sudomegas.saat.storage

import java.time.LocalDate

/**
 * The filter facets — SPEC-ANDROID 5.12, the desktop sidebar folded into a
 * sheet.
 *
 * ONE FILTER, ONE IMPLEMENTATION. This milestone's brief forbids implementing
 * filters twice, and the shape here is what makes that easy to honour: a filter
 * is plain data, matching is a pure predicate, and the Grid, the Specs list and
 * AM7's calendar picker all compose it with the AM3 query the same way. Nothing
 * about it belongs to a screen.
 *
 * Each facet is a SET, and within a facet the values are ORed — picking Diver
 * and Field shows both. Across facets they are ANDed, because that is what
 * anyone means by narrowing: a Diver AND a Seiko Group watch. An empty set is
 * not a filter at all rather than a filter that matches nothing, which is the
 * one place this could quietly show an empty collection.
 */
data class WatchFilter(
    val statuses: Set<String> = emptySet(),
    val styles: Set<String> = emptySet(),
    val groups: Set<String> = emptySet(),
    val movementKinds: Set<String> = emptySet(),
    val caseMaterials: Set<String> = emptySet(),
    val lugWidths: Set<String> = emptySet(),
    val tags: Set<String> = emptySet(),
    /** SPEC-ANDROID 5.12's one boolean facet. */
    val notWornIn90Days: Boolean = false,
) {
    val isEmpty: Boolean
        get() = statuses.isEmpty() && styles.isEmpty() && groups.isEmpty() &&
            movementKinds.isEmpty() && caseMaterials.isEmpty() && lugWidths.isEmpty() &&
            tags.isEmpty() && !notWornIn90Days

    /** The set this facet holds, for reading and for toggling. */
    fun values(facet: FacetKind): Set<String> = when (facet) {
        FacetKind.STATUS -> statuses
        FacetKind.STYLE -> styles
        FacetKind.GROUP -> groups
        FacetKind.MOVEMENT_KIND -> movementKinds
        FacetKind.CASE_MATERIAL -> caseMaterials
        FacetKind.LUG_WIDTH -> lugWidths
        FacetKind.TAG -> tags
        FacetKind.NOT_WORN_90 -> if (notWornIn90Days) setOf(NOT_WORN_VALUE) else emptySet()
    }

    /** Add or remove one value. Toggling is the only edit a facet has. */
    fun toggle(facet: FacetKind, value: String): WatchFilter {
        val current = values(facet)
        val next = if (value in current) current - value else current + value
        return with(facet, next)
    }

    /** Clear one whole facet — what a dismissible chip does. */
    fun without(facet: FacetKind, value: String): WatchFilter =
        with(facet, values(facet) - value)

    private fun with(facet: FacetKind, values: Set<String>): WatchFilter = when (facet) {
        FacetKind.STATUS -> copy(statuses = values)
        FacetKind.STYLE -> copy(styles = values)
        FacetKind.GROUP -> copy(groups = values)
        FacetKind.MOVEMENT_KIND -> copy(movementKinds = values)
        FacetKind.CASE_MATERIAL -> copy(caseMaterials = values)
        FacetKind.LUG_WIDTH -> copy(lugWidths = values)
        FacetKind.TAG -> copy(tags = values)
        FacetKind.NOT_WORN_90 -> copy(notWornIn90Days = values.isNotEmpty())
    }

    companion object {
        /** The single value the boolean facet holds, so it can be toggled like any other. */
        const val NOT_WORN_VALUE = "not_worn_90"
    }
}

/** The eight facets SPEC-ANDROID 5.12 names, and no more — the brief is explicit. */
enum class FacetKind {
    STATUS,
    STYLE,
    GROUP,
    MOVEMENT_KIND,
    CASE_MATERIAL,
    LUG_WIDTH,
    TAG,
    NOT_WORN_90,
}

/** One selectable value in a facet, with how many watches it would leave. */
data class FacetValue(val value: String, val count: Int)

/** A facet and its values. A facet with no values is not built at all. */
data class Facet(val kind: FacetKind, val values: List<FacetValue>)

/**
 * Every value a watch offers to a facet.
 *
 * Multi-valued for tags only; everything else answers zero or one. Blank is
 * absence and contributes nothing — a facet is a list of things the collection
 * actually says, and "" is not one of them.
 */
internal fun Watch.facetValues(kind: FacetKind, today: LocalDate): List<String> = when (kind) {
    FacetKind.STATUS -> listOfNotNull(status.orNull())
    FacetKind.STYLE -> listOfNotNull(style.orNull())
    FacetKind.GROUP -> listOfNotNull(group.orNull())
    FacetKind.MOVEMENT_KIND -> listOfNotNull(movement.kind.orNull())
    FacetKind.CASE_MATERIAL -> listOfNotNull(case.material.orNull())
    // As a string like every other facet, so one toggle mechanism serves all
    // eight. Sorted numerically when the sheet builds the list — see [facets].
    FacetKind.LUG_WIDTH -> listOfNotNull(case.lugWidthMm?.toString())
    FacetKind.TAG -> tags.mapNotNull { it.orNull() }
    FacetKind.NOT_WORN_90 ->
        if (isNotWornIn(NOT_WORN_DAYS, today)) listOf(WatchFilter.NOT_WORN_VALUE) else emptyList()
}

/**
 * Not worn in the last [days] days — including never worn at all.
 *
 * A watch nobody has ever recorded wearing is the strongest possible answer to
 * "what have I not worn lately", and excluding it because it has no last-worn
 * date would leave the facet answering a subtly different question from the one
 * it is labelled with.
 */
internal fun Watch.isNotWornIn(days: Long, today: LocalDate): Boolean {
    val since = daysSinceWorn(today) ?: return true
    return since >= days
}

/** SPEC-ANDROID 5.12 names the facet "Not worn in 90 days". */
const val NOT_WORN_DAYS = 90L

/** True when this watch survives every facet the filter holds. */
fun Watch.matches(filter: WatchFilter, today: LocalDate): Boolean =
    FacetKind.entries.all { kind ->
        val wanted = filter.values(kind)
        // An untouched facet is not a filter. This is the line that decides
        // whether an empty sheet shows everything or nothing.
        wanted.isEmpty() || facetValues(kind, today).any { it in wanted }
    }

/**
 * The facets to show, with live counts.
 *
 * A COUNT IS TAKEN AGAINST THE COLLECTION FILTERED BY EVERY OTHER FACET, not by
 * this one. That is what makes the numbers useful rather than tautological:
 * having picked Diver, the Style facet still shows how many Field and Dress
 * watches are one tap away, while the other facets narrow as you go. Counting
 * against the fully-filtered set would show 0 beside every value you had not
 * picked, and a zero that only means "you did not pick this" teaches nothing.
 *
 * A facet with no values across the collection is omitted entirely —
 * SPEC-ANDROID 5.12's "facets with no values hidden". A collection where nobody
 * has recorded a case material should not be offered a Case material facet.
 */
fun List<Watch>.facets(filter: WatchFilter, today: LocalDate): List<Facet> =
    FacetKind.entries.mapNotNull { kind ->
        // Everything except this facet, so its own values still count.
        val others = filter.withoutFacet(kind)
        val eligible = filter { it.matches(others, today) }

        val counts = LinkedHashMap<String, Int>()
        // Seeded from the WHOLE collection so a value stays visible at zero
        // once other facets have excluded it — a value that vanished as you
        // narrowed would make the sheet appear to lose options.
        forEach { watch -> watch.facetValues(kind, today).forEach { counts.putIfAbsent(it, 0) } }
        eligible.forEach { watch ->
            watch.facetValues(kind, today).forEach { counts[it] = counts.getValue(it) + 1 }
        }
        if (counts.isEmpty()) return@mapNotNull null

        Facet(kind, counts.entries.sortedWith(kind.ordering()).map { FacetValue(it.key, it.value) })
    }

/**
 * Lug widths sort as numbers, everything else alphabetically.
 *
 * 8 before 20 before 22, not "20", "22", "8" — the one facet whose values are
 * figures, and the one place a string sort reads as a bug.
 */
private fun FacetKind.ordering(): Comparator<Map.Entry<String, Int>> =
    if (this == FacetKind.LUG_WIDTH) {
        compareBy({ it.key.toIntOrNull() ?: Int.MAX_VALUE }, { it.key })
    } else {
        compareBy { it.key.lowercase() }
    }

private fun WatchFilter.withoutFacet(kind: FacetKind): WatchFilter =
    values(kind).fold(this) { filter, value -> filter.without(kind, value) }

/**
 * Filter, then search, then sort — the AM3 pipeline with one step in front.
 *
 * Composed here rather than folded into `query()` so the order is stated once
 * and every screen gets the same one. Records that failed to load are excluded
 * by `query` already; they have no fields to match and the grid names them in a
 * notice instead.
 */
fun List<WatchRecord>.filtered(
    filter: WatchFilter,
    search: String,
    sort: WatchSort,
    today: LocalDate,
): List<WatchRecord> =
    filter { record -> record.watch?.matches(filter, today) == true }
        .query(search, sort, today)

// ---------------------------------------------------------------------------

/**
 * The filter sheet's footer — SPEC-ANDROID 5.11.
 *
 * Plain figures. No charts, no gauges, no progress rings: the spec says so, and
 * a collection of eleven watches has nothing to plot that a sentence does not
 * say better.
 *
 * Computed over the FILTERED collection rather than the whole one, because the
 * sheet it sits in is the thing doing the filtering — a total that ignored the
 * facets above it would be answering a question nobody asked.
 */
data class CollectionSummary(
    val watchCount: Int,
    /** Movement kind to how many, commonest first. Unrecorded kinds are not counted. */
    val byMovementKind: List<Pair<String, Int>>,
    /** Currency to total acquisition price, alphabetically. */
    val valueByCurrency: List<Pair<String, Double>>,
)

fun List<Watch>.summarise(): CollectionSummary {
    val kinds = LinkedHashMap<String, Int>()
    forEach { watch ->
        watch.movement.kind.orNull()?.let { kinds[it] = (kinds[it] ?: 0) + 1 }
    }

    val totals = LinkedHashMap<String, Double>()
    forEach { watch ->
        val price = watch.acquisition.price ?: return@forEach
        // A price with no currency is still money the owner spent, so it is
        // counted rather than dropped — under the empty key, which the UI
        // renders as an unlabelled figure. Silently folding it into TRY would
        // be inventing a fact about what was paid.
        val currency = watch.acquisition.currency.orNull().orEmpty()
        totals[currency] = (totals[currency] ?: 0.0) + price
    }

    return CollectionSummary(
        watchCount = size,
        // Commonest first, ties alphabetically, so the order is total and the
        // footer cannot reshuffle between emissions.
        byMovementKind = kinds.entries
            .sortedWith(compareByDescending<Map.Entry<String, Int>> { it.value }.thenBy { it.key })
            .map { it.key to it.value },
        valueByCurrency = totals.entries.sortedBy { it.key }.map { it.key to it.value },
    )
}

private fun String?.orNull(): String? = this?.trim()?.takeIf { it.isNotEmpty() }
