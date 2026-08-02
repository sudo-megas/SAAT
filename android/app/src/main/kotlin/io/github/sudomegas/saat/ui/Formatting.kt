package io.github.sudomegas.saat.ui

import kotlin.math.floor

/**
 * Number formatting for display, ported from the desktop's `saat/ui/formatting.py`.
 *
 * The storage layer keeps measurements as the model declares them — `41.0` is a
 * `Double` because a case can be 40.5 mm — but a card that reads "41.0 mm" looks
 * like a spreadsheet. Python's `:g` drops the trailing zero and that is the
 * behaviour being matched.
 *
 * Deliberately built from `Double.toString()` rather than `String.format`. The
 * default-locale overload of `String.format` would render 41.5 as "41,5" on a
 * Turkish phone, which is a locale read by the back door — and while hard rule 7
 * is about the UI language rather than number formats, the whole point of that
 * rule is that the app decides its own presentation rather than inheriting the
 * device's. Kotlin's `toString` always emits a `.` separator.
 *
 * AM11 revisits this: Turkish genuinely writes 41,5 and a localised build should
 * say so. That is a decision for the milestone that adds `values-tr/`, not one to
 * take by accident here.
 */
fun formatMeasurement(value: Double): String =
    if (value.isFinite() && value == floor(value)) {
        value.toLong().toString()
    } else {
        value.toString()
    }
