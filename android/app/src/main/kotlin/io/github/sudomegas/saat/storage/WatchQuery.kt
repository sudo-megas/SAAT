package io.github.sudomegas.saat.storage

import java.time.LocalDate

/**
 * Searching and ordering a collection.
 *
 * Free functions beside [Derived], deliberately not methods on
 * [WatchRepository]. The repository owns mutation and shared state; a query is
 * a pure transform of a list, and AM6's Specs screen will want to interleave its
 * filter facets with this search. Freezing the pipeline order inside a
 * repository method now would be deciding that for a consumer that does not
 * exist yet.
 *
 * The milestone brief asks for the matcher to live in the repository layer
 * rather than in a composable for exactly that reason: AM6 reuses it, and one
 * implementation is the point.
 *
 * Operates on [WatchRecord] rather than [Watch] because both consumers need the
 * slug — the grid to key its items, and navigation to name a destination.
 */

/** Never worn sorts ahead of any real day count. Ported from the desktop. */
const val NEVER_WORN_SORT_DAYS: Int = 1_000_000

/**
 * True if every character of [query] appears in [text] in order, gaps allowed —
 * the classic fuzzy-finder subsequence match, and a direct port of the desktop's
 * `saat/ui/search.py`. No fuzzy-matching library is in the dependency budget,
 * and this is the standard dependency-free reading of "fuzzy".
 *
 * Case folding uses the NO-ARGUMENT `lowercase()`, and that is load-bearing on
 * this owner's phone. `lowercase(Locale.getDefault())` under a Turkish locale
 * maps `I` to `ı`, so a search for `iwc` would stop matching `IWC` — the same
 * dotless-i trap `Slugs` is careful about, arriving by a different door.
 *
 * One documented divergence from the desktop: Python's `casefold()` maps `ß` to
 * `ss` and Kotlin's `lowercase()` does not. It affects what a search finds,
 * never what is stored, so the two apps still agree about every file on disk.
 */
fun fuzzyMatch(query: String, text: String): Boolean {
    if (query.isEmpty()) return true
    val haystack = text.lowercase()
    var from = 0
    for (character in query.lowercase()) {
        val found = haystack.indexOf(character, from)
        if (found < 0) return false
        from = found + 1
    }
    return true
}

/**
 * SPEC-ANDROID 5.12: fuzzy search across brand, model, reference, caliber and
 * tags.
 *
 * Matched PER FIELD, never against the fields concatenated. A concatenated
 * search would let a query borrow letters across a boundary — `sksk` would match
 * brand "Seiko" plus model "SKX007" — which produces results the owner cannot
 * explain to themselves.
 */
fun Watch.matchesSearch(query: String): Boolean {
    if (query.isBlank()) return true
    val fields = buildList {
        add(brand)
        add(model)
        reference?.let(::add)
        movement.caliber?.let(::add)
        addAll(tags)
    }
    return fields.any { it.isNotEmpty() && fuzzyMatch(query, it) }
}

/**
 * The four orders SPEC-ANDROID 5.1 puts in the top bar's sort menu.
 *
 * [token] is what reaches `config.toml`, so renaming an enum constant cannot
 * silently invalidate a stored preference.
 */
enum class WatchSort(val token: String) {
    BRAND("brand"),
    MODEL("model"),
    ACQUIRED("acquired"),
    LEAST_WORN("least_worn"),
    ;

    companion object {
        val DEFAULT: WatchSort = BRAND

        /**
         * Unknown tokens fall back rather than throwing — a config written by a
         * later version must not stop this one from starting, which is the same
         * leniency `ConfigStore` already applies to an unrecognised theme mode.
         */
        fun fromToken(token: String?): WatchSort =
            entries.firstOrNull { it.token == token } ?: DEFAULT
    }
}

/**
 * The reusable primitive. AM6 composes this with its facets.
 *
 * Every comparator ends by breaking ties on the slug, which is unique. Without a
 * total order, two watches comparing equal could swap places between emissions
 * and the grid would visibly twitch for no reason the owner can see.
 */
fun WatchSort.comparator(today: LocalDate): Comparator<WatchRecord> = when (this) {
    // Case-insensitive, so `rolex` does not sort after `Zenith`. This diverges
    // from the desktop, which sorts raw strings and therefore puts every
    // capitalised brand ahead of every lowercase one; on a phone that reads as
    // a bug rather than as a convention.
    WatchSort.BRAND -> compareBy<WatchRecord> { it.watch?.brand?.lowercase().orEmpty() }
        .thenBy { it.watch?.model?.lowercase().orEmpty() }
        .thenBy { it.slug }

    WatchSort.MODEL -> compareBy<WatchRecord> { it.watch?.model?.lowercase().orEmpty() }
        .thenBy { it.watch?.brand?.lowercase().orEmpty() }
        .thenBy { it.slug }

    // Newest first, and watches with no acquisition date go LAST. The desktop
    // puts unknowns last in an ascending sort; reversing the whole comparator
    // would float them to the top, and "we do not know when you bought it" is
    // not the same claim as "you bought it most recently".
    WatchSort.ACQUIRED -> compareBy<WatchRecord> { it.watch?.acquisition?.date == null }
        .thenByDescending { it.watch?.acquisition?.date ?: LocalDate.MIN }
        .thenBy { it.watch?.brand?.lowercase().orEmpty() }
        .thenBy { it.slug }

    // A port of the desktop's _least_worn_key, sentinel and all: never worn
    // first, then longest-since-worn. Note this means "least recently worn"
    // rather than "fewest days worn" — that is what the phrase already means in
    // the desktop app, and Derived deliberately offers daysSinceWorn and no
    // total-wear count. A future-dated worn entry gives a negative day count and
    // therefore sorts last, which is the honest answer for a watch recorded as
    // worn tomorrow.
    WatchSort.LEAST_WORN -> compareBy<WatchRecord> { record ->
        -(record.watch?.daysSinceWorn(today) ?: NEVER_WORN_SORT_DAYS)
    }.thenBy { it.slug }
}

/**
 * Filter, then order. Records that failed to load are excluded — they have no
 * fields to match and no values to sort by; the grid surfaces them as a notice
 * instead of as cards.
 */
fun List<WatchRecord>.query(
    search: String,
    sort: WatchSort,
    today: LocalDate,
): List<WatchRecord> =
    filter { record ->
        val watch = record.watch
        watch != null && watch.matchesSearch(search)
    }.sortedWith(sort.comparator(today))
