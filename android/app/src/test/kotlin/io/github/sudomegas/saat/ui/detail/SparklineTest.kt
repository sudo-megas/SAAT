package io.github.sudomegas.saat.ui.detail

import io.github.sudomegas.saat.storage.TimingEntry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

/**
 * The sparkline's arithmetic — AM9b.
 *
 * The threshold, the scale and the position of the zero rule are the whole of
 * what could be wrong here, and every one of them is a number rather than a
 * pixel. The drawing itself is nine lines of `Canvas` that turn a unit square
 * into a path.
 */
class SparklineTest {

    private fun reading(day: Int, deviation: Double?) = TimingEntry(
        date = LocalDate.of(2026, 1, day),
        deviationSec = deviation,
        position = "Dial Up",
    )

    // --- the threshold --------------------------------------------------------

    @Test
    fun `two readings are not a trend`() {
        assertNull(sparkline(listOf(reading(1, 2.0), reading(2, 3.0))))
    }

    @Test
    fun `three readings draw`() {
        assertNotNull(sparkline(listOf(reading(1, 2.0), reading(2, 3.0), reading(3, 4.0))))
    }

    @Test
    fun `no readings at all is silent`() {
        assertNull(sparkline(emptyList()))
    }

    /**
     * The threshold counts PLOTTABLE readings, not entries. Four readings of
     * which two have no date is a two-point chart, and a two-point chart is a
     * line segment pretending to be a trend.
     */
    @Test
    fun `entries missing a date or a deviation do not count towards the three`() {
        val readings = listOf(
            reading(1, 5.0),
            reading(2, 6.0),
            TimingEntry(date = null, deviationSec = 7.0),
            TimingEntry(date = LocalDate.of(2026, 1, 4), deviationSec = null),
        )

        assertNull(sparkline(readings))
    }

    @Test
    fun `an undated reading is dropped but the rest still draw`() {
        val readings = listOf(
            reading(1, 5.0),
            reading(2, 6.0),
            reading(3, 7.0),
            TimingEntry(date = null, deviationSec = 99.0),
        )

        // Three points, not four — the undated one has no place on a time axis.
        assertEquals(3, sparkline(readings)!!.points.size)
    }

    // --- order and shape ------------------------------------------------------

    /**
     * Oldest on the left, whatever order the file lists them in. The readings
     * list on the page reads newest first; the chart reads left to right as time
     * passing, and it sorts for itself rather than trusting its caller.
     */
    @Test
    fun `readings are drawn oldest first regardless of input order`() {
        val jumbled = listOf(reading(3, 9.0), reading(1, 1.0), reading(2, 5.0))

        val points = sparkline(jumbled)!!.points

        assertEquals(0f, points.first().x, TOLERANCE)
        assertEquals(1f, points.last().x, TOLERANCE)

        // 9.0 is the highest value, so it sits at the top of the scale.
        assertEquals(0f, points.last().y, TOLERANCE)

        // 1.0 is the LOWEST READING but not the bottom of the scale: zero is
        // folded in, so the range is 0..9 and 1.0 lands at 1 - 1/9. Asserting
        // y = 1 here would be asserting the auto-scaled chart this deliberately
        // is not.
        assertEquals(1f - 1f / 9f, points.first().y, TOLERANCE)
        assertEquals(1f, sparkline(jumbled)!!.zeroY, TOLERANCE)
    }

    @Test
    fun `points are evenly spaced across the width`() {
        val points = sparkline(listOf(reading(1, 1.0), reading(2, 2.0), reading(3, 3.0)))!!.points

        assertEquals(listOf(0f, 0.5f, 1f), points.map { it.x })
    }

    // --- the zero rule --------------------------------------------------------

    /**
     * THE PORTED DECISION THAT MATTERS. Zero is folded into the range whether or
     * not any reading crosses it, so the reference line is always on the chart
     * and a watch running +2 to +4 sec/day looks like what it is — consistently
     * fast — instead of filling the box the way a wildly varying one would.
     */
    @Test
    fun `zero stays on the chart for a watch that never crosses it`() {
        val alwaysFast = sparkline(listOf(reading(1, 2.0), reading(2, 3.0), reading(3, 4.0)))!!

        // Range is 0..4, so zero is at the very bottom and every reading is above it.
        assertEquals(1f, alwaysFast.zeroY, TOLERANCE)
        assertTrue(alwaysFast.points.all { it.y < alwaysFast.zeroY })
    }

    @Test
    fun `zero sits in the middle when readings straddle it evenly`() {
        val straddling = sparkline(listOf(reading(1, -5.0), reading(2, 0.0), reading(3, 5.0)))!!

        assertEquals(0.5f, straddling.zeroY, TOLERANCE)
    }

    @Test
    fun `a slow watch puts zero at the top`() {
        val alwaysSlow = sparkline(listOf(reading(1, -8.0), reading(2, -4.0), reading(3, -2.0)))!!

        assertEquals(0f, alwaysSlow.zeroY, TOLERANCE)
    }

    /**
     * Three identical readings of exactly zero: `high - low` is 0 and the naive
     * scale divides by it. The desktop's `or 1.0` is what this asserts.
     */
    @Test
    fun `three readings dead on the mark do not divide by zero`() {
        val perfect = sparkline(listOf(reading(1, 0.0), reading(2, 0.0), reading(3, 0.0)))!!

        assertTrue(perfect.points.all { it.y.isFinite() })
        assertTrue(perfect.zeroY.isFinite())
        // Every point sits exactly on the zero rule, which is the truth.
        assertTrue(perfect.points.all { it.y == perfect.zeroY })
    }

    @Test
    fun `identical non-zero readings still produce a finite chart`() {
        val flat = sparkline(listOf(reading(1, 3.0), reading(2, 3.0), reading(3, 3.0)))!!

        assertTrue(flat.points.all { it.y.isFinite() })
        // Range 0..3: the flat line is at the top, the zero rule at the bottom.
        assertEquals(0f, flat.points.first().y, TOLERANCE)
        assertEquals(1f, flat.zeroY, TOLERANCE)
    }

    @Test
    fun `every coordinate stays inside the unit square`() {
        val readings = listOf(
            reading(1, -30.0),
            reading(2, 12.5),
            reading(3, 0.0),
            reading(4, 7.0),
        )

        val chart = sparkline(readings)!!
        assertTrue(chart.points.all { it.x in 0f..1f && it.y in 0f..1f })
        assertTrue(chart.zeroY in 0f..1f)
    }

    /**
     * A NaN deviation must cost its own reading and NOTHING ELSE.
     *
     * `deviation_sec = "NaN"` is reachable from a hand-edited file — the TOML
     * reader coerces a quoted number in silence — and from a paste into the
     * form, which filters no keystrokes. Before this was filtered, one such
     * reading poisoned `min`/`max`, and because `NaN != 0.0` is true the
     * `span == 0.0` guard did not catch it: every coordinate became NaN and the
     * whole chart drew nothing at all.
     */
    @Test
    fun `one NaN reading does not blank the entire chart`() {
        val readings = listOf(
            reading(1, Double.NaN),
            reading(2, 1.0),
            reading(3, 2.0),
            reading(4, 3.0),
        )

        val chart = sparkline(readings)!!

        assertEquals("the NaN reading is dropped, the other three plot", 3, chart.points.size)
        assertTrue(chart.points.all { it.x.isFinite() && it.y.isFinite() })
        assertTrue(chart.zeroY.isFinite())
        assertTrue(chart.points.all { it.x in 0f..1f && it.y in 0f..1f })
    }

    @Test
    fun `an infinite reading is dropped the same way`() {
        val readings = listOf(
            reading(1, Double.POSITIVE_INFINITY),
            reading(2, -2.0),
            reading(3, 4.0),
            reading(4, 1.0),
        )

        val chart = sparkline(readings)!!

        assertEquals(3, chart.points.size)
        assertTrue(chart.points.all { it.y.isFinite() })
    }

    /**
     * The threshold counts PLOTTABLE readings, so three entries of which one is
     * NaN is not a chart — exactly as three of which one is undated is not.
     */
    @Test
    fun `a NaN reading does not count towards the three`() {
        assertNull(sparkline(listOf(reading(1, Double.NaN), reading(2, 1.0), reading(3, 2.0))))
    }

    @Test
    fun `three is the threshold the spec names`() {
        assertEquals(3, MIN_SPARKLINE_READINGS)
    }
}

private const val TOLERANCE = 0.0001f
