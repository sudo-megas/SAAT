package io.github.sudomegas.saat.storage

import java.time.LocalDate
import java.time.temporal.ChronoUnit
import kotlin.math.floor

/**
 * Everything SPEC-ANDROID 4 lists as "derived, never stored", as pure functions
 * over a [Watch] — ports of the desktop's `saat/ui/wear_stats.py`,
 * `saat/ui/maintenance.py` and `saat/ui/formatting.py`.
 *
 * Pure and stored nowhere, for a reason that outlives this milestone: every one
 * of these is a question about `worn` or `log`, and those lists are edited from
 * the calendar (AM7), the detail page and the widget (AM8). A cached "days since
 * worn" would have three places to invalidate it from and would be wrong in the
 * fourth.
 *
 * `today` is a parameter everywhere it matters rather than being read from the
 * clock inside, so the tests state the date they are asking about instead of
 * being true only on the day they were written.
 */

/** Overdue, or due within this many days, is what the UI calls "due". */
const val MAINTENANCE_DUE_SOON_DAYS = 90L

/** A mechanical movement's beat rate divides by this to give hertz. */
const val BPH_PER_HZ = 7200.0

/** The most recent day this watch was worn, or null if it never has been. */
fun Watch.lastWorn(): LocalDate? = worn.maxOrNull()

/**
 * Days since the watch was last worn.
 *
 * Null means never worn, which is a different thing from 0 (worn today) and the
 * UI renders it differently — SPEC.md §4. A watch whose only recorded day is in
 * the future (SPEC-ANDROID 5.5 allows planning ahead) gives a negative number
 * rather than being clamped, matching the desktop.
 */
fun Watch.daysSinceWorn(today: LocalDate): Int? {
    val last = lastWorn() ?: return null
    return ChronoUnit.DAYS.between(last, today).toInt()
}

/** How many days in `today`'s calendar year this watch was worn. */
fun Watch.timesWornThisYear(today: LocalDate): Int = worn.count { it.year == today.year }

/**
 * The longest run of consecutive calendar days in `worn`.
 *
 * Duplicates are collapsed first: a hand-edited file can list the same day
 * twice, and two entries for one day are not a two-day streak.
 */
fun Watch.longestStreak(): Int {
    val days = worn.distinct().sorted()
    if (days.isEmpty()) return 0

    var best = 1
    var current = 1
    for (i in 1 until days.size) {
        if (ChronoUnit.DAYS.between(days[i - 1], days[i]) == 1L) {
            current += 1
            if (current > best) best = current
        } else {
            current = 1
        }
    }
    return best
}

/**
 * When this watch is next due a service: the most recent `Service` log entry
 * plus `maintenance.serviceIntervalYears`.
 *
 * Null whenever either half is missing, and that silence is the point. No
 * Service entry means there is nothing to project from, and a blank interval
 * means the owner is not tracking this watch's schedule at all — most watches
 * never will be, and the UI must not nag about them (SPEC.md §4).
 *
 * Two details are ports of the desktop's arithmetic rather than choices:
 *
 *  - A fractional interval (5.5 years) advances by whole years and then by
 *    `fraction × 365.25` days, rounded HALF TO EVEN. Python's `round()` is
 *    half-to-even and `Math.round` is half-up, so `Math.rint` is what actually
 *    agrees with the desktop on a tie.
 *  - A baseline of 29 February lands on the 28th in a non-leap target year.
 *    `plusYears` clamps there by itself, which is what the desktop's
 *    `date.replace()`-and-catch-ValueError does the long way round.
 */
fun Watch.nextServiceDue(): LocalDate? {
    val interval = maintenance.serviceIntervalYears ?: return null
    val baseline = log
        .filter { it.kind == LogEntry.KIND_SERVICE && it.date != null }
        .mapNotNull { it.date }
        .maxOrNull() ?: return null

    val wholeYears = floor(interval)
    val fraction = interval - wholeYears

    var due = baseline.plusYears(wholeYears.toLong())
    if (fraction != 0.0) {
        due = due.plusDays(Math.rint(fraction * 365.25).toLong())
    }
    return due
}

/**
 * Overdue, or due within [MAINTENANCE_DUE_SOON_DAYS]. False — silent — when
 * there is no baseline to project from.
 */
fun Watch.isMaintenanceDue(today: LocalDate): Boolean {
    val due = nextServiceDue() ?: return false
    return !due.isAfter(today.plusDays(MAINTENANCE_DUE_SOON_DAYS))
}

/** True only once the due date has actually passed, for the harsher wording. */
fun Watch.isMaintenanceOverdue(today: LocalDate): Boolean {
    val due = nextServiceDue() ?: return false
    return due.isBefore(today)
}

/**
 * Beat rate as frequency in hertz — bph ÷ 7200, shown beside the bph figure.
 * Null when the movement has no bph, which is every quartz watch.
 */
fun Movement.frequencyHz(): Double? = bph?.let { it / BPH_PER_HZ }

/**
 * A strap's effective width: its own, or the watch's lug width when it does not
 * state one. SPEC.md §4 — "defaults to `case.lug_width_mm`". AM9's strap
 * compatibility matches on this rather than on the raw field.
 */
fun Strap.effectiveWidthMm(owner: Watch): Int? = widthMm ?: owner.case.lugWidthMm
