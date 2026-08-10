package io.github.sudomegas.saat.storage

import java.time.LocalDate
import java.time.temporal.ChronoUnit
import kotlin.random.Random

/**
 * "Pick for me" — SPEC-ANDROID 5.5, ported from the desktop's
 * `saat/selection.py`. Pure — no ViewModel, no Compose, no I/O. Only the
 * single-day picker is ported; the desktop's week planner (`pick_week`) is
 * explicitly out of scope.
 */

/**
 * A never-worn watch's weight sits this far above whatever the most-neglected
 * *real* value in the batch is, rather than a fixed always-huge constant — a
 * collection-relative bonus so "never worn is favoured" holds without making
 * a recently-worn watch's chance so small it stops feeling like "never zero."
 */
private const val NEVER_WORN_BONUS = 30.0

/** Random vs Weighted. [token] is what reaches `config.toml`'s `[picker]` table. */
enum class PickerMode(val token: String) {
    RANDOM("random"),
    WEIGHTED("weighted"),
    ;

    companion object {
        val DEFAULT: PickerMode = RANDOM

        fun fromToken(token: String?): PickerMode =
            entries.firstOrNull { it.token == token } ?: DEFAULT
    }
}

/**
 * Callers check `records.ownedWatches().isEmpty()` before presenting the
 * picker at all (see `CalendarViewModel.openPickForMe`), exactly as the
 * desktop dialog special-cases an empty collection, rather than relying on
 * this being caught.
 */
class NoOwnedWatchesException : IllegalStateException("no owned watches to pick from")

/**
 * slug -> weight for weighted mode. [watches] must already be owned-only
 * (see [ownedWatches]) — this function does no filtering of its own, mirroring
 * the desktop's `compute_weights`/`_weights_from_last_worn` split.
 *
 * Weight is linear in days-since-[today], floored at 0 rather than going
 * negative — a pre-planned future wear date must not do so, since
 * [Watch.daysSinceWorn] itself deliberately does not floor (SPEC-ANDROID 5.5:
 * "every day is editable, past or future"). Every result is > 0: never worn
 * gets the collection-relative [NEVER_WORN_BONUS], everyone else gets
 * `daysSince + 1.0`, so nothing is ever truly excluded.
 */
fun computeWeights(watches: List<WatchRecord>, today: LocalDate): Map<String, Double> {
    val daysSince: Map<String, Double?> = watches.associate { record ->
        val last = record.watch?.lastWorn()
        val since = last?.let { maxOf(0.0, ChronoUnit.DAYS.between(it, today).toDouble()) }
        record.slug to since
    }
    val neverWornWeight = (daysSince.values.filterNotNull().maxOrNull() ?: 0.0) + NEVER_WORN_BONUS
    return daysSince.mapValues { (_, since) -> since?.plus(1.0) ?: neverWornWeight }
}

/**
 * Uniform over owned watches — a true dN. Throws [NoOwnedWatchesException]
 * with no owned watches; see the class doc for why callers check first.
 */
fun pickRandom(records: List<WatchRecord>, random: Random = Random.Default): WatchRecord {
    val owned = records.ownedWatches()
    if (owned.isEmpty()) throw NoOwnedWatchesException()
    return owned[random.nextInt(owned.size)]
}

/**
 * Favours watches worn least recently — see [computeWeights] for the curve.
 * Throws [NoOwnedWatchesException] with no owned watches; see [pickRandom].
 *
 * Cumulative-weight sampling: draw a point in `[0, total)`, walk the running
 * sum, return the watch whose slice the draw landed in. `total >= 1.0` always
 * (every weight is > 0), so there is no divide-by-zero case — the trailing
 * fallback exists only for floating-point drift leaving the final comparison
 * a hair short of `total`.
 */
fun pickWeighted(
    records: List<WatchRecord>,
    today: LocalDate,
    random: Random = Random.Default,
): WatchRecord {
    val owned = records.ownedWatches()
    if (owned.isEmpty()) throw NoOwnedWatchesException()
    val weights = computeWeights(owned, today)
    val total = owned.sumOf { weights.getValue(it.slug) }
    val draw = random.nextDouble() * total
    var cumulative = 0.0
    for (record in owned) {
        cumulative += weights.getValue(record.slug)
        if (draw < cumulative) return record
    }
    return owned.last()
}

/** Dispatches to [pickRandom]/[pickWeighted] by [mode]. */
fun pickOne(
    records: List<WatchRecord>,
    mode: PickerMode,
    today: LocalDate,
    random: Random = Random.Default,
): WatchRecord = when (mode) {
    PickerMode.RANDOM -> pickRandom(records, random)
    PickerMode.WEIGHTED -> pickWeighted(records, today, random)
}
