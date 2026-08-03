package io.github.sudomegas.saat.ui.detail

import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.storage.minimalWatch
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.LocalDate

/**
 * The wear line and the twelve-month strip.
 *
 * `today` is a parameter throughout, so every case below states the date it is
 * asking about. A year boundary is the one these figures actually get wrong in
 * practice — "times worn this year" resets on 1 January while "days since" and
 * "longest streak" carry straight across it, and only a test that names both
 * sides of a New Year notices when one of them starts behaving like the other.
 */
class WearStatsTest {

    private fun watch(vararg worn: LocalDate) = minimalWatch().copy(worn = worn.toList())

    private fun days(year: Int, month: Int, vararg days: Int) =
        days.map { LocalDate.of(year, month, it) }.toTypedArray()

    // --- the line -----------------------------------------------------------

    @Test
    fun `a watch that has never been worn has no stats at all`() {
        // Null hides the line AND the strip. A line reading "Last worn — · 0
        // times this year" is exactly the noise the rest of the app avoids.
        assertNull(wearStats(minimalWatch(), LocalDate.of(2026, 8, 3)))
    }

    @Test
    fun `worn today reads zero days since, not one`() {
        val today = LocalDate.of(2026, 8, 3)
        val stats = wearStats(watch(today), today)!!

        assertEquals("03.08.2026", stats.lastWorn)
        assertEquals(0, stats.daysSince)
    }

    @Test
    fun `days since counts calendar days`() {
        val stats = wearStats(
            watch(LocalDate.of(2026, 7, 28)),
            LocalDate.of(2026, 8, 3),
        )!!

        assertEquals(6, stats.daysSince)
    }

    @Test
    fun `a day recorded ahead of today gives a negative interval rather than a clamp`() {
        // SPEC-ANDROID 5.5 allows planning ahead. The UI drops the interval from
        // the line rather than printing "-3 days ago"; what matters here is that
        // the model reports the truth instead of pretending it is zero.
        val stats = wearStats(
            watch(LocalDate.of(2026, 8, 6)),
            LocalDate.of(2026, 8, 3),
        )!!

        assertEquals(-3, stats.daysSince)
    }

    // --- across a year boundary ---------------------------------------------

    @Test
    fun `times worn this year counts only this year`() {
        val stats = wearStats(
            watch(
                LocalDate.of(2025, 12, 30),
                LocalDate.of(2025, 12, 31),
                LocalDate.of(2026, 1, 1),
                LocalDate.of(2026, 1, 2),
            ),
            LocalDate.of(2026, 1, 5),
        )!!

        assertEquals(2, stats.timesThisYear)
    }

    @Test
    fun `a streak runs straight through New Year`() {
        // The one that is easy to get wrong by grouping per calendar year first:
        // 30, 31, 1, 2 is a four-day streak, not two runs of two.
        val stats = wearStats(
            watch(
                LocalDate.of(2025, 12, 30),
                LocalDate.of(2025, 12, 31),
                LocalDate.of(2026, 1, 1),
                LocalDate.of(2026, 1, 2),
            ),
            LocalDate.of(2026, 1, 5),
        )!!

        assertEquals(4, stats.longestStreak)
        assertEquals(3, stats.daysSince)
        assertEquals("02.01.2026", stats.lastWorn)
    }

    @Test
    fun `a leap day is an ordinary day in a streak`() {
        val stats = wearStats(
            watch(
                LocalDate.of(2028, 2, 28),
                LocalDate.of(2028, 2, 29),
                LocalDate.of(2028, 3, 1),
            ),
            LocalDate.of(2028, 3, 2),
        )!!

        assertEquals(3, stats.longestStreak)
    }

    // --- the strip ----------------------------------------------------------

    @Test
    fun `the strip is twelve months ending with today's`() {
        val months = trailingTwelveMonths(emptyList(), LocalDate.of(2026, 8, 3))

        assertEquals(12, months.size)
        // September of last year through August of this one.
        assertEquals(R.string.screen_month_short_sep, months.first().labelRes)
        assertEquals(R.string.screen_month_short_aug, months.last().labelRes)
    }

    @Test
    fun `each block knows how long its month is`() {
        val months = trailingTwelveMonths(emptyList(), LocalDate.of(2024, 3, 15))

        // March 2023 back-count: the window is Apr 2023 .. Mar 2024, so
        // February in it is 2024's — a leap year, 29 days.
        assertEquals(listOf(30, 31, 30, 31, 31, 30, 31, 30, 31, 31, 29, 31), months.map { it.daysInMonth })
    }

    @Test
    fun `worn days land in their own month and nowhere else`() {
        val worn = listOf(
            LocalDate.of(2026, 8, 1),
            LocalDate.of(2026, 8, 31),
            LocalDate.of(2026, 7, 15),
        )
        val months = trailingTwelveMonths(worn, LocalDate.of(2026, 8, 3))

        assertEquals(listOf(1, 31), months.last().wornDays)
        assertEquals(listOf(15), months[months.size - 2].wornDays)
        assertEquals(emptyList<Int>(), months.first().wornDays)
    }

    @Test
    fun `days outside the window are simply absent`() {
        // Not an error and not clamped into the first block: a watch with years
        // of history has most of it outside a twelve-month strip, and only the
        // window is being drawn.
        val months = trailingTwelveMonths(
            listOf(LocalDate.of(2019, 4, 4), LocalDate.of(2026, 8, 2)),
            LocalDate.of(2026, 8, 3),
        )

        assertEquals(1, months.sumOf { it.wornDays.size })
        assertEquals(listOf(2), months.last().wornDays)
    }

    @Test
    fun `a day listed twice is drawn once`() {
        val duplicated = LocalDate.of(2026, 8, 2)
        val months = trailingTwelveMonths(listOf(duplicated, duplicated), LocalDate.of(2026, 8, 3))

        assertEquals(listOf(2), months.last().wornDays)
    }

    @Test
    fun `the window crosses a year boundary without losing a month`() {
        val months = trailingTwelveMonths(emptyList(), LocalDate.of(2026, 1, 15))

        assertEquals(12, months.size)
        assertEquals(R.string.screen_month_short_feb, months.first().labelRes)
        assertEquals(R.string.screen_month_short_jan, months.last().labelRes)
        // Feb 2025 is not a leap year; the window must not have picked 2026's.
        assertEquals(28, months.first().daysInMonth)
    }

    @Test
    fun `the strip is built from the same worn list the line is`() {
        val today = LocalDate.of(2026, 8, 3)
        val stats = wearStats(watch(*days(2026, 8, 1, 2, 3)), today)!!

        assertEquals(listOf(1, 2, 3), stats.months.last().wornDays)
        assertEquals(3, stats.longestStreak)
        assertEquals(3, stats.timesThisYear)
        assertEquals(0, stats.daysSince)
    }
}
