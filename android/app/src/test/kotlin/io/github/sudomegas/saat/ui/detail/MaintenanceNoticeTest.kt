package io.github.sudomegas.saat.ui.detail

import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.storage.LogEntry
import io.github.sudomegas.saat.storage.Maintenance
import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.minimalWatch
import io.github.sudomegas.saat.storage.needsAttention
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

/**
 * The maintenance line — AM9b — and above all its SILENCE.
 *
 * "Silent when nothing is due, silent entirely when the interval is blank" is
 * the requirement most of these tests are about. Most watches in a real
 * collection will never carry a service interval, and a page that found
 * something to say about all of them would be a page the owner learns to skim.
 *
 * `today` is stated by every test rather than read from the clock, so these stay
 * true on a day other than the one they were written.
 */
class MaintenanceNoticeTest {

    private val today = LocalDate.of(2026, 6, 1)

    private fun serviced(on: LocalDate, intervalYears: Double?): Watch = minimalWatch().copy(
        maintenance = Maintenance(serviceIntervalYears = intervalYears),
        log = listOf(LogEntry(date = on, kind = LogEntry.KIND_SERVICE, note = "Full service")),
    )

    private fun notices(watch: Watch) = maintenanceNotices(watch, today)

    // --- the silence ----------------------------------------------------------

    @Test
    fun `a watch with nothing recorded says nothing`() {
        assertTrue(notices(minimalWatch()).isEmpty())
    }

    /**
     * The single most important case in this file. A watch serviced long ago,
     * with NO interval recorded, must stay silent — there is no schedule to be
     * late for, and inventing one from the service date would nag every owner
     * who ever logged a service.
     */
    @Test
    fun `a blank service interval is silent however old the service is`() {
        val watch = serviced(on = LocalDate.of(1998, 1, 1), intervalYears = null)

        assertTrue(notices(watch).isEmpty())
        assertFalse(watch.needsAttention(today))
    }

    /** The mirror: an interval with no Service entry has nothing to project from. */
    @Test
    fun `an interval with no service entry is silent`() {
        val watch = minimalWatch().copy(maintenance = Maintenance(serviceIntervalYears = 5.0))

        assertTrue(notices(watch).isEmpty())
        assertFalse(watch.needsAttention(today))
    }

    @Test
    fun `a service comfortably in the future is silent`() {
        // Serviced Jan 2026, five-year interval: due 2031, nowhere near.
        val watch = serviced(on = LocalDate.of(2026, 1, 1), intervalYears = 5.0)

        assertTrue(notices(watch).isEmpty())
        assertFalse(watch.needsAttention(today))
    }

    // --- due and overdue ------------------------------------------------------

    @Test
    fun `a service due within ninety days speaks, without alarm`() {
        // Due 2026-07-01: thirty days out.
        val watch = serviced(on = LocalDate.of(2021, 7, 1), intervalYears = 5.0)

        val notice = notices(watch).single()
        assertEquals(R.string.screen_detail_service_due, notice.messageRes)
        assertFalse(notice.isOverdue)
        assertEquals("01.07.2026", notice.date)
        assertTrue(watch.needsAttention(today))
    }

    @Test
    fun `a service past its date is overdue and says so differently`() {
        // Due 2026-01-01, five months ago.
        val watch = serviced(on = LocalDate.of(2021, 1, 1), intervalYears = 5.0)

        val notice = notices(watch).single()
        assertEquals(R.string.screen_detail_service_overdue, notice.messageRes)
        assertTrue(notice.isOverdue)
    }

    /**
     * The boundary. Ninety days out is due; ninety-one is not. The notice and
     * the grid's accent dot must agree on which side of that line a date falls,
     * so both are asserted together — a one-day disagreement between them is
     * the sort of bug nobody reports and everybody notices.
     */
    @Test
    fun `the ninetieth day is due and the ninety-first is not`() {
        val ninety = minimalWatch().copy(
            maintenance = Maintenance(serviceIntervalYears = 1.0),
            log = listOf(
                LogEntry(
                    // +1 year lands on 2026-08-30, exactly 90 days after today.
                    date = LocalDate.of(2025, 8, 30),
                    kind = LogEntry.KIND_SERVICE,
                ),
            ),
        )
        val ninetyOne = minimalWatch().copy(
            maintenance = Maintenance(serviceIntervalYears = 1.0),
            log = listOf(
                LogEntry(date = LocalDate.of(2025, 8, 31), kind = LogEntry.KIND_SERVICE),
            ),
        )

        assertEquals(1, notices(ninety).size)
        assertTrue(ninety.needsAttention(today))

        assertTrue(notices(ninetyOne).isEmpty())
        assertFalse(ninetyOne.needsAttention(today))
    }

    // --- the battery clock ----------------------------------------------------

    @Test
    fun `a battery due date behaves the same way`() {
        val quartz = minimalWatch().copy(
            maintenance = Maintenance(batteryDue = LocalDate.of(2026, 7, 1)),
        )

        val notice = notices(quartz).single()
        assertEquals(R.string.screen_detail_battery_due, notice.messageRes)
        assertTrue(quartz.needsAttention(today))
    }

    @Test
    fun `a battery date long past is overdue`() {
        val quartz = minimalWatch().copy(
            maintenance = Maintenance(batteryDue = LocalDate.of(2024, 3, 3)),
        )

        assertEquals(R.string.screen_detail_battery_overdue, notices(quartz).single().messageRes)
    }

    @Test
    fun `a battery date far ahead is silent`() {
        val quartz = minimalWatch().copy(
            maintenance = Maintenance(batteryDue = LocalDate.of(2030, 1, 1)),
        )

        assertTrue(notices(quartz).isEmpty())
        assertFalse(quartz.needsAttention(today))
    }

    /**
     * Both clocks can run at once on a watch whose owner tracks both. Neither is
     * suppressed, and the overdue one is read first.
     */
    @Test
    fun `service and battery can both be due, overdue first`() {
        val both = serviced(on = LocalDate.of(2021, 7, 1), intervalYears = 5.0)
            .copy(maintenance = Maintenance(serviceIntervalYears = 5.0, batteryDue = LocalDate.of(2025, 1, 1)))

        val notices = notices(both)

        assertEquals(2, notices.size)
        assertTrue("the overdue line is read first", notices.first().isOverdue)
        assertEquals(R.string.screen_detail_battery_overdue, notices.first().messageRes)
    }
}
