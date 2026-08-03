package io.github.sudomegas.saat.ui.detail

import io.github.sudomegas.saat.storage.TimingEntry

/**
 * The timing sparkline as pure geometry — SPEC.md §4, SPEC-ANDROID 5.6.
 *
 * Deviation over time, oldest on the left, with a zero reference line: how a
 * mechanical owner sees at a glance whether a watch runs fast, slow, or drifted
 * after a service. A direct port of the desktop's `_TimingSparkline`, including
 * the two decisions below that a fresh implementation would have got differently
 * and worse.
 *
 * Coordinates come out normalised to the unit square, y measured DOWNWARD from
 * the top so it drops straight into Compose's canvas space. Nothing here knows
 * about pixels, padding or colour, so the whole of the interesting behaviour —
 * which readings qualify, what the scale is, where zero sits — is testable
 * without a device.
 */
data class Sparkline(
    /** Oldest first, left to right. Always [MIN_SPARKLINE_READINGS] or more. */
    val points: List<SparkPoint>,
    /**
     * Where a deviation of zero sits, normalised. Always within 0..1, because
     * zero is folded into the range — see [sparkline].
     */
    val zeroY: Float,
)

/** A point in the unit square. `y` 0 is the TOP, matching canvas coordinates. */
data class SparkPoint(val x: Float, val y: Float)

/**
 * Three. Two readings are a line segment, not a trend, and one is a dot —
 * SPEC.md §4 sets the threshold and the desktop's `MIN_SPARKLINE_READINGS`
 * carries the same value.
 */
const val MIN_SPARKLINE_READINGS = 3

/**
 * Build the sparkline, or null when there is not enough to draw.
 *
 * Null — hidden entirely — rather than an empty chart, which is the same rule
 * the empty spec group follows. The list of readings itself still renders
 * beneath; the sparkline is the extra that appears once it can say something.
 *
 * A READING NEEDS BOTH A DATE AND A DEVIATION. One without a date has no
 * position on the time axis and one without a deviation has no height, so
 * neither can be plotted — but both stay in the list below, because the owner
 * typed them and a half-filled reading is still a record. The threshold counts
 * PLOTTABLE readings, so four entries of which two are dateless do not produce a
 * two-point "sparkline".
 *
 * TWO PORTED DECISIONS, both load-bearing:
 *
 *  - **Zero is always folded into the range.** Without it the reference line
 *    would leave the widget whenever a watch never crossed zero, and — worse —
 *    a line wiggling in the middle of an auto-scaled box would look identical
 *    whether it was ±0.5 sec/day (excellent) or ±30 sec/day (broken). Folding
 *    zero in costs vertical detail on a consistently fast watch and buys the
 *    only comparison the chart is actually for.
 *  - **The x axis is the reading's INDEX, not its date.** Timing readings are
 *    taken irregularly — three in the week after a service, then nothing for a
 *    year — and true date spacing would crush that first cluster into a
 *    vertical smear. Even spacing shows the sequence, which is what the owner
 *    is reading. The dates are in the list below for anyone who wants them.
 */
fun sparkline(readings: List<TimingEntry>): Sparkline? {
    val values = readings
        // isFinite() as well as non-null, and it belongs HERE rather than in a
        // guard further down. `deviation_sec = "NaN"` is reachable two ways —
        // a hand-edited file (the TOML reader coerces a quoted number in
        // silence) and a paste into the form, which filters no keystrokes — and
        // NaN poisons `min`/`max`, so `low` and `high` both become NaN. The
        // `span == 0.0` guard below does NOT catch that, because `NaN != 0.0`
        // is true: span stays NaN, every coordinate becomes NaN, and the whole
        // chart silently draws nothing rather than losing one reading.
        //
        // Filtering here also keeps the threshold honest: a NaN reading is not
        // plottable, so it must not count towards the three.
        //
        // Deliberately NOT matching the desktop, which is differently broken —
        // Python's `min` is position-dependent with NaN, so `_TimingSparkline`
        // survives or fails depending on where the bad reading sits.
        .filter { it.date != null && it.deviationSec?.isFinite() == true }
        .sortedBy { it.date }
        .map { it.deviationSec!! }

    if (values.size < MIN_SPARKLINE_READINGS) return null

    // Zero joins the values purely to set the scale, never as a plotted point.
    val low = minOf(values.min(), 0.0)
    val high = maxOf(values.max(), 0.0)
    // `or 1.0` in the desktop: every reading identical AND zero — a watch dead
    // on the mark three times running — would otherwise divide by zero.
    val span = (high - low).takeIf { it != 0.0 } ?: 1.0

    // Normalised, and inverted: the HIGHEST deviation belongs at the top of the
    // canvas, which is y = 0.
    fun yFor(value: Double): Float = (1.0 - (value - low) / span).toFloat()

    val lastIndex = values.size - 1
    return Sparkline(
        points = values.mapIndexed { index, value ->
            SparkPoint(x = index.toFloat() / lastIndex, y = yFor(value))
        },
        zeroY = yFor(0.0),
    )
}
