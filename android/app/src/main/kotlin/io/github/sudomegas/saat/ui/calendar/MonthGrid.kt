package io.github.sudomegas.saat.ui.calendar

import java.time.DayOfWeek
import java.time.LocalDate
import java.time.YearMonth

/**
 * A month laid out as SPEC-ANDROID 5.5 asks: seven columns, weeks starting
 * Monday.
 *
 * Monday-first is not the platform default and is not negotiable — it is what
 * the desktop draws and what this owner's week looks like. Deriving it from the
 * locale would be reading the system locale to decide the interface, which hard
 * rule 7 exists to prevent, arriving through a door nobody thought to close.
 *
 * The leading blanks are days of the PREVIOUS month and are rendered as nothing
 * rather than as greyed-out numbers. A calendar that shows the 29th, 30th and
 * 31st of last month above the 1st invites tapping them, and every tap would
 * silently be an edit to a month you are not looking at.
 */
data class MonthLayout(
    val month: YearMonth,
    /** Null for a leading or trailing blank; a date for every real day. */
    val cells: List<LocalDate?>,
) {
    val days: List<LocalDate> get() = cells.filterNotNull()
}

const val DAYS_IN_WEEK = 7

/**
 * The grid for [month].
 *
 * Padded to whole weeks at both ends so the last row is not short — a grid whose
 * final row has three cells makes the cells resize, and a calendar that changes
 * its own cell size from month to month is the sort of thing that reads as a
 * rendering bug.
 */
fun monthLayout(month: YearMonth): MonthLayout {
    val first = month.atDay(1)
    // DayOfWeek.MONDAY.value is 1, so this is 0 for a month starting Monday.
    val leading = first.dayOfWeek.value - DayOfWeek.MONDAY.value

    val cells = buildList<LocalDate?> {
        repeat(leading) { add(null) }
        (1..month.lengthOfMonth()).forEach { add(month.atDay(it)) }
        while (size % DAYS_IN_WEEK != 0) add(null)
    }
    return MonthLayout(month, cells)
}

/**
 * Every day between two, inclusive, in order — what long-press range mode fills.
 *
 * Order-independent: dragging a selection backwards is the same span as dragging
 * it forwards, and making the caller normalise it would be one more thing for a
 * gesture handler to get wrong.
 */
fun daysBetween(a: LocalDate, b: LocalDate): List<LocalDate> {
    val from = minOf(a, b)
    val to = maxOf(a, b)
    return generateSequence(from) { day -> day.plusDays(1).takeIf { !it.isAfter(to) } }.toList()
}
