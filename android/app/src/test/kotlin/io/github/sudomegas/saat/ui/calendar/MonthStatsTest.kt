package io.github.sudomegas.saat.ui.calendar

import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.WatchRecord
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File
import java.time.LocalDate
import java.time.YearMonth

/**
 * The month footer — SPEC-ANDROID 5.5.
 *
 * The third figure is the one worth testing hardest: days recorded and distinct
 * watches are both visible by looking at the grid, but which watches you did NOT
 * wear this month is the thing the strip exists to tell you.
 */
class MonthStatsTest {

    private val august = YearMonth.of(2026, 8)

    private fun record(
        slug: String,
        brand: String = "Seiko",
        model: String = slug,
        status: String = Watch.STATUS_OWNED,
        vararg worn: LocalDate,
    ): WatchRecord {
        val watch = Watch(brand = brand, model = model, status = status, worn = worn.toList())
        return WatchRecord(slug, File("/watches/$slug"), watch = watch, loaded = watch)
    }

    private fun day(n: Int) = LocalDate.of(2026, 8, n)

    @Test
    fun `days recorded counts distinct days in the month`() {
        val stats = listOf(
            record("a", worn = arrayOf(day(1), day(2))),
            record("b", worn = arrayOf(day(3))),
        ).monthStats(august)

        assertEquals(3, stats.daysRecorded)
        assertEquals(2, stats.distinctWatches)
    }

    @Test
    fun `days in other months do not count`() {
        val stats = listOf(
            record("a", worn = arrayOf(day(1), LocalDate.of(2026, 7, 31), LocalDate.of(2026, 9, 1))),
        ).monthStats(august)

        assertEquals(1, stats.daysRecorded)
    }

    @Test
    fun `the watches not worn this month are named, not counted`() {
        // The only figure here that tells the owner something the grid does not
        // already show, which is why it is a list.
        val stats = listOf(
            record("a", brand = "Seiko", model = "SKX007", worn = arrayOf(day(1))),
            record("b", brand = "Casio", model = "F-91W"),
            record("c", brand = "Orient", model = "Bambino"),
        ).monthStats(august)

        assertEquals(listOf("Casio F-91W", "Orient Bambino"), stats.notWorn)
    }

    @Test
    fun `a watch that is not Owned is not listed as unworn`() {
        // It is not "not worn this month", it is not in rotation at all, and
        // listing it would make the one useful figure noise.
        val stats = listOf(
            record("sold", brand = "Seiko", model = "Sold one", status = "Sold"),
            record("owned", brand = "Casio", model = "F-91W"),
        ).monthStats(august)

        assertEquals(listOf("Casio F-91W"), stats.notWorn)
    }

    @Test
    fun `a month with nothing recorded lists every owned watch`() {
        val stats = listOf(record("a", model = "One"), record("b", model = "Two")).monthStats(august)

        assertEquals(0, stats.daysRecorded)
        assertEquals(0, stats.distinctWatches)
        assertEquals(2, stats.notWorn.size)
    }

    @Test
    fun `an empty collection has nothing to say`() {
        val stats = emptyList<WatchRecord>().monthStats(august)

        assertEquals(MonthStats(0, 0, emptyList()), stats)
    }

    @Test
    fun `a record that did not load counts for nothing`() {
        val broken = WatchRecord("broken", File("/watches/broken"), loadError = "line 3")

        assertEquals(MonthStats(0, 0, emptyList()), listOf(broken).monthStats(august))
    }
}
