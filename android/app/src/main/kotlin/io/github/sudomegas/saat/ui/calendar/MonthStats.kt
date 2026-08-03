package io.github.sudomegas.saat.ui.calendar

import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.WatchRecord
import io.github.sudomegas.saat.storage.wornIndex
import java.time.YearMonth

/**
 * The footer strip beneath the month grid — SPEC-ANDROID 5.5.
 *
 * Three plain figures, and the brief is candid about which one earns its place:
 * days recorded and distinct watches are both visible by looking at the grid,
 * but the watches NOT worn this month is "the only figure here that tells the
 * owner something he did not already know". It is the whole reason the strip
 * exists, so it names them rather than counting them.
 *
 * No streaks, no badges, no goals. The brief forbids gamification outright, and
 * a hobby that starts scoring itself stops being one.
 */
data class MonthStats(
    val daysRecorded: Int,
    val distinctWatches: Int,
    /** `Brand Model` for each Owned watch with no day this month, name-sorted. */
    val notWorn: List<String>,
)

/**
 * Owned watches only, matching the index — a Sold or Wishlist watch is not
 * "not worn this month", it is simply not in rotation, and listing it would
 * make the one useful figure noise.
 */
fun List<WatchRecord>.monthStats(month: YearMonth): MonthStats {
    val index = wornIndex().filterKeys { YearMonth.from(it) == month }
    val wornSlugs = index.values.mapTo(mutableSetOf()) { it.slug }

    val owned = mapNotNull { record ->
        val watch = record.watch ?: return@mapNotNull null
        if (watch.status != Watch.STATUS_OWNED) null else record to watch
    }

    return MonthStats(
        daysRecorded = index.size,
        distinctWatches = wornSlugs.size,
        notWorn = owned
            .filterNot { (record, _) -> record.slug in wornSlugs }
            .map { (_, watch) -> "${watch.brand} ${watch.model}" }
            .sortedBy { it.lowercase() },
    )
}
