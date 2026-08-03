package io.github.sudomegas.saat.ui

import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.abs
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

/**
 * `DD.MM.YYYY` — SPEC-ANDROID 4, and the desktop's `fmt_date`.
 *
 * `Locale.ROOT` is passed explicitly. `ofPattern` with no locale resolves
 * against `Locale.getDefault(FORMAT)`, which decides the numbering system: on a
 * device set to a locale with non-Latin digits the same pattern renders
 * `٠٣.٠٨.٢٠٢٦`, and the app would be reading the system locale through a door
 * hard rule 7 never thought to close. The pattern is fixed and so is its
 * alphabet.
 */
fun formatDate(value: LocalDate): String = value.format(UI_DATE)

/**
 * A signed figure, matching Python's `:+g` — `+8`, `-5`, `+0`.
 *
 * Only accuracy uses it, where the sign IS the information: a movement running
 * −5 to +8 sec/day is a different watch from one running 5 to 8. Built from
 * [formatMeasurement] so the trailing zero goes the same way it does everywhere
 * else, and from the absolute value so `-0.0` cannot print as `-0`.
 */
fun formatSignedMeasurement(value: Double): String {
    val magnitude = formatMeasurement(abs(value))
    return if (value < 0) "-$magnitude" else "+$magnitude"
}

/**
 * `1,234.50` — two decimals and grouped thousands, the desktop's `:,.2f`.
 *
 * `Locale.ROOT` for the same reason [formatDate] states it, and for one more:
 * the default-locale overload would render a Turkish phone's prices as
 * `1.234,50` while the currency code beside it stayed `TRY`, which is a number
 * formatted by the device and a currency named by the file disagreeing about
 * which convention they are in. AM11 revisits this with the rest of the
 * localisation work.
 */
fun formatPrice(value: Double): String = String.format(Locale.ROOT, "%,.2f", value)

private val UI_DATE: DateTimeFormatter = DateTimeFormatter.ofPattern("dd.MM.yyyy", Locale.ROOT)
