package io.github.sudomegas.saat.storage

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

/**
 * The derived values SPEC-ANDROID 4 says are never stored.
 *
 * The empty-collection cases matter more than the populated ones here. A watch
 * with no `worn` list is not an edge case in this app — it is the state every
 * watch starts in and most stay in, and "never worn" has to stay distinguishable
 * from "worn today" all the way to the UI.
 *
 * The service-due expectations are not derived from first principles: they were
 * MEASURED by running the desktop's own `saat.ui.maintenance.next_service_due`
 * over the same baselines, so a divergence in the fractional-year arithmetic
 * fails here rather than showing a different date on each device.
 */
class DerivedValuesTest {

    private val today = LocalDate.of(2026, 7, 29)

    private fun watch(
        worn: List<LocalDate> = emptyList(),
        log: List<LogEntry> = emptyList(),
        serviceIntervalYears: Double? = null,
    ) = Watch(
        brand = "Seiko",
        model = "SKX007",
        worn = worn,
        log = log,
        maintenance = Maintenance(serviceIntervalYears = serviceIntervalYears),
    )

    private fun serviced(on: LocalDate) = LogEntry(date = on, kind = LogEntry.KIND_SERVICE)

    // ---- worn: the empty cases first ------------------------------------

    @Test
    fun `a watch never worn has no last-worn date`() {
        assertNull(watch().lastWorn())
    }

    @Test
    fun `never worn is null days rather than zero days`() {
        assertNull(
            "0 means worn today; never worn must stay distinguishable from it",
            watch().daysSinceWorn(today),
        )
    }

    @Test
    fun `never worn is zero times this year and a zero streak`() {
        assertEquals(0, watch().timesWornThisYear(today))
        assertEquals(0, watch().longestStreak())
    }

    @Test
    fun `last worn is the newest date regardless of list order`() {
        val w = watch(
            worn = listOf(
                LocalDate.of(2026, 1, 5),
                LocalDate.of(2026, 7, 20),
                LocalDate.of(2025, 12, 31),
            )
        )
        assertEquals(LocalDate.of(2026, 7, 20), w.lastWorn())
        assertEquals(9, w.daysSinceWorn(today))
    }

    @Test
    fun `worn today is zero days since`() {
        assertEquals(0, watch(worn = listOf(today)).daysSinceWorn(today))
    }

    @Test
    fun `a planned future day gives a negative count rather than being clamped`() {
        // SPEC-ANDROID 5.5: every day is editable, and future days are how you
        // plan. The desktop reports the negative too; clamping to 0 here would
        // claim the watch was worn today.
        val w = watch(worn = listOf(LocalDate.of(2026, 8, 3)))
        assertEquals(-5, w.daysSinceWorn(today))
    }

    @Test
    fun `times worn this year counts only this year`() {
        val w = watch(
            worn = listOf(
                LocalDate.of(2025, 12, 31),
                LocalDate.of(2026, 1, 1),
                LocalDate.of(2026, 6, 30),
                LocalDate.of(2027, 1, 1),
            )
        )
        assertEquals(2, w.timesWornThisYear(today))
    }

    // ---- streaks ---------------------------------------------------------

    @Test
    fun `a single day is a streak of one`() {
        assertEquals(1, watch(worn = listOf(LocalDate.of(2026, 3, 1))).longestStreak())
    }

    @Test
    fun `the longest run wins, not the last one`() {
        val w = watch(
            worn = listOf(
                LocalDate.of(2026, 3, 1),
                LocalDate.of(2026, 3, 2),
                LocalDate.of(2026, 3, 3),
                LocalDate.of(2026, 3, 10),
                LocalDate.of(2026, 3, 11),
            )
        )
        assertEquals(3, w.longestStreak())
    }

    @Test
    fun `an unsorted list still finds the run`() {
        val w = watch(
            worn = listOf(
                LocalDate.of(2026, 3, 11),
                LocalDate.of(2026, 3, 1),
                LocalDate.of(2026, 3, 10),
                LocalDate.of(2026, 3, 2),
                LocalDate.of(2026, 3, 3),
            )
        )
        assertEquals(3, w.longestStreak())
    }

    @Test
    fun `the same day listed twice is not a two-day streak`() {
        val day = LocalDate.of(2026, 3, 1)
        assertEquals(1, watch(worn = listOf(day, day, day)).longestStreak())
    }

    @Test
    fun `a run across a month boundary still counts`() {
        val w = watch(
            worn = listOf(
                LocalDate.of(2026, 1, 30),
                LocalDate.of(2026, 1, 31),
                LocalDate.of(2026, 2, 1),
            )
        )
        assertEquals(3, w.longestStreak())
    }

    @Test
    fun `a run across a leap day counts the leap day`() {
        val w = watch(
            worn = listOf(
                LocalDate.of(2028, 2, 28),
                LocalDate.of(2028, 2, 29),
                LocalDate.of(2028, 3, 1),
            )
        )
        assertEquals(3, w.longestStreak())
    }

    // ---- service due: silence is the default -----------------------------

    @Test
    fun `no interval means nothing is due, however many services are logged`() {
        val w = watch(log = listOf(serviced(LocalDate.of(2010, 1, 1))), serviceIntervalYears = null)
        assertNull(w.nextServiceDue())
        assertFalse("the UI must not nag about an untracked watch", w.isMaintenanceDue(today))
    }

    @Test
    fun `an interval with no service entry projects from nothing`() {
        val w = watch(serviceIntervalYears = 5.0)
        assertNull(w.nextServiceDue())
        assertFalse(w.isMaintenanceDue(today))
    }

    @Test
    fun `log entries of other kinds are not a service baseline`() {
        val w = watch(
            log = listOf(
                LogEntry(date = LocalDate.of(2024, 1, 1), kind = "Battery"),
                LogEntry(date = LocalDate.of(2024, 2, 1), kind = "Note"),
            ),
            serviceIntervalYears = 5.0,
        )
        assertNull(w.nextServiceDue())
    }

    @Test
    fun `a service entry with no date cannot be a baseline`() {
        val w = watch(
            log = listOf(LogEntry(date = null, kind = LogEntry.KIND_SERVICE)),
            serviceIntervalYears = 5.0,
        )
        assertNull(w.nextServiceDue())
    }

    // ---- service due: arithmetic measured against the desktop ------------

    @Test
    fun `service due matches the desktop for whole and fractional intervals`() {
        // baseline, interval, expected — every expectation produced by running
        // saat.ui.maintenance.next_service_due on the desktop.
        val cases = listOf(
            Triple(LocalDate.of(2020, 3, 11), 5.0, LocalDate.of(2025, 3, 11)),
            Triple(LocalDate.of(2020, 3, 11), 5.5, LocalDate.of(2025, 9, 10)),
            Triple(LocalDate.of(2020, 3, 11), 0.25, LocalDate.of(2020, 6, 10)),
            Triple(LocalDate.of(2024, 1, 1), 0.1, LocalDate.of(2024, 2, 7)),
            Triple(LocalDate.of(2019, 12, 31), 8.0, LocalDate.of(2027, 12, 31)),
            Triple(LocalDate.of(2024, 6, 15), 1.2, LocalDate.of(2025, 8, 27)),
            Triple(LocalDate.of(2023, 11, 30), 2.75, LocalDate.of(2026, 8, 31)),
        )

        for ((baseline, interval, expected) in cases) {
            val w = watch(log = listOf(serviced(baseline)), serviceIntervalYears = interval)
            assertEquals("baseline $baseline + $interval years", expected, w.nextServiceDue())
        }
    }

    @Test
    fun `a 29 February baseline lands on the 28th in a non-leap year`() {
        val w = watch(log = listOf(serviced(LocalDate.of(2020, 2, 29))), serviceIntervalYears = 1.0)
        assertEquals(LocalDate.of(2021, 2, 28), w.nextServiceDue())

        val fractional =
            watch(log = listOf(serviced(LocalDate.of(2020, 2, 29))), serviceIntervalYears = 3.5)
        assertEquals(LocalDate.of(2023, 8, 30), fractional.nextServiceDue())
    }

    @Test
    fun `the most recent service is the baseline, not the first`() {
        val w = watch(
            log = listOf(
                serviced(LocalDate.of(2015, 1, 1)),
                serviced(LocalDate.of(2021, 6, 2)),
                LogEntry(date = LocalDate.of(2023, 1, 1), kind = "Battery"),
            ),
            serviceIntervalYears = 5.0,
        )
        assertEquals(LocalDate.of(2026, 6, 2), w.nextServiceDue())
    }

    // ---- the 90-day window ----------------------------------------------

    @Test
    fun `due exactly ninety days out is due, ninety-one is not`() {
        val ninety = watch(
            log = listOf(serviced(today.plusDays(MAINTENANCE_DUE_SOON_DAYS).minusYears(1))),
            serviceIntervalYears = 1.0,
        )
        assertTrue(ninety.isMaintenanceDue(today))

        val ninetyOne = watch(
            log = listOf(serviced(today.plusDays(MAINTENANCE_DUE_SOON_DAYS + 1).minusYears(1))),
            serviceIntervalYears = 1.0,
        )
        assertFalse(ninetyOne.isMaintenanceDue(today))
    }

    @Test
    fun `overdue is due, and only overdue once the date has passed`() {
        val overdue = watch(log = listOf(serviced(LocalDate.of(2015, 1, 1))), serviceIntervalYears = 5.0)
        assertTrue(overdue.isMaintenanceDue(today))
        assertTrue(overdue.isMaintenanceOverdue(today))

        val dueToday = watch(log = listOf(serviced(today.minusYears(5))), serviceIntervalYears = 5.0)
        assertTrue(dueToday.isMaintenanceDue(today))
        assertFalse("due today is not yet overdue", dueToday.isMaintenanceOverdue(today))
    }

    // ---- frequency -------------------------------------------------------

    @Test
    fun `bph converts to hertz and absence stays absent`() {
        assertEquals(3.0, Movement(bph = 21600).frequencyHz()!!, 1e-9)
        assertEquals(4.0, Movement(bph = 28800).frequencyHz()!!, 1e-9)
        assertEquals(2.5, Movement(bph = 18000).frequencyHz()!!, 1e-9)
        assertNull("a quartz movement has no beat rate", Movement(bph = null).frequencyHz())
    }

    // ---- strap width fallback and the fitted rule ------------------------

    @Test
    fun `a strap with no width of its own takes the watch's lug width`() {
        val w = Watch(brand = "A", model = "B", case = Case(lugWidthMm = 20))
        assertEquals(20, Strap(material = "NATO").effectiveWidthMm(w))
        assertEquals(18, Strap(material = "Leather", widthMm = 18).effectiveWidthMm(w))

        val unmeasured = Watch(brand = "A", model = "B")
        assertNull(Strap(material = "NATO").effectiveWidthMm(unmeasured))
    }

    @Test
    fun `enforcing the fitted rule keeps the first and clears the rest`() {
        val straps = listOf(
            Strap(material = "Bracelet", fitted = true),
            Strap(material = "Leather", fitted = true),
            Strap(material = "NATO", fitted = false),
        )
        val enforced = straps.withSingleFitted()

        assertEquals(1, enforced.fittedCount())
        assertTrue(enforced[0].fitted)
        assertFalse(enforced[1].fitted)
        assertEquals("nothing else about the strap may change", "Leather", enforced[1].material)
    }

    @Test
    fun `enforcing the fitted rule leaves a compliant list untouched`() {
        val straps = listOf(Strap(material = "Bracelet", fitted = true), Strap(material = "NATO"))
        assertEquals(straps, straps.withSingleFitted())
        assertEquals(emptyList<Strap>(), emptyList<Strap>().withSingleFitted())
    }
}
