package io.github.sudomegas.saat.ui.calendar

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate
import java.time.YearMonth

/** The month grid's shape — SPEC-ANDROID 5.5: seven columns, weeks from Monday. */
class MonthGridTest {

    @Test
    fun `a month starting on Monday has no leading blanks`() {
        // June 2026 begins on a Monday.
        val layout = monthLayout(YearMonth.of(2026, 6))

        assertEquals(LocalDate.of(2026, 6, 1), layout.cells.first())
        assertEquals(30, layout.days.size)
    }

    @Test
    fun `a month starting on Sunday gets six leading blanks`() {
        // Sunday is the LAST column in a Monday-first week, so the 1st sits at
        // index 6. Getting this backwards is the classic off-by-one here.
        val layout = monthLayout(YearMonth.of(2026, 3))

        assertEquals(LocalDate.of(2026, 3, 1), layout.cells[6])
        assertTrue(layout.cells.take(6).all { it == null })
    }

    @Test
    fun `every grid is a whole number of weeks`() {
        // A short final row would make the cells resize, and a calendar that
        // changes its own cell size month to month reads as a rendering bug.
        (1..12).forEach { month ->
            val layout = monthLayout(YearMonth.of(2026, month))
            assertEquals(0, layout.cells.size % DAYS_IN_WEEK)
        }
    }

    @Test
    fun `a leap February is 29 days and still whole weeks`() {
        val layout = monthLayout(YearMonth.of(2028, 2))

        assertEquals(29, layout.days.size)
        assertEquals(0, layout.cells.size % DAYS_IN_WEEK)
    }

    @Test
    fun `the blanks are blanks, not last month's days`() {
        // Rendered as nothing rather than as greyed-out numbers: a calendar
        // showing the 31st of last month above the 1st invites tapping it, and
        // every tap would silently edit a month you are not looking at.
        val layout = monthLayout(YearMonth.of(2026, 3))

        assertNull(layout.cells.first())
        assertNull(layout.cells.last())
        assertTrue(layout.days.all { YearMonth.from(it) == YearMonth.of(2026, 3) })
    }

    @Test
    fun `a range is every day between two, whichever way round they came`() {
        val from = LocalDate.of(2026, 8, 3)
        val to = LocalDate.of(2026, 8, 6)
        val expected = listOf(3, 4, 5, 6).map { LocalDate.of(2026, 8, it) }

        assertEquals(expected, daysBetween(from, to))
        assertEquals("dragging backwards is the same span", expected, daysBetween(to, from))
    }

    @Test
    fun `a range of one day is one day`() {
        val day = LocalDate.of(2026, 8, 3)

        assertEquals(listOf(day), daysBetween(day, day))
    }

    @Test
    fun `a range crosses a month and a year boundary intact`() {
        val span = daysBetween(LocalDate.of(2025, 12, 30), LocalDate.of(2026, 1, 2))

        assertEquals(4, span.size)
        assertEquals(LocalDate.of(2026, 1, 2), span.last())
    }
}
