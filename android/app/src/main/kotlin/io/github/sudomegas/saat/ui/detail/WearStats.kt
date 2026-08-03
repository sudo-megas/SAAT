package io.github.sudomegas.saat.ui.detail

import androidx.annotation.StringRes
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.daysSinceWorn
import io.github.sudomegas.saat.storage.lastWorn
import io.github.sudomegas.saat.storage.longestStreak
import io.github.sudomegas.saat.storage.timesWornThisYear
import io.github.sudomegas.saat.ui.formatDate
import java.time.LocalDate
import java.time.YearMonth

/**
 * The wear line and the twelve-month strip — SPEC-ANDROID 5.6.
 *
 * Separate from [DetailPage] rather than a field on it, because this is the one
 * part of the page that depends on what day it is. Everything in `detailPage`
 * is a pure function of the file; this is a pure function of the file AND
 * `today`, and mixing the two would mean either passing a clock into the whole
 * page or letting the page read one, and `Derived` already established which of
 * those this codebase does.
 */
data class WearStats(
    /** `DD.MM.YYYY`, already formatted. */
    val lastWorn: String,
    /**
     * Days since [lastWorn]. Zero is today; NEGATIVE is a day recorded ahead,
     * which SPEC-ANDROID 5.5 allows because planning is a use of the calendar.
     */
    val daysSince: Int,
    val timesThisYear: Int,
    val longestStreak: Int,
    /** The trailing twelve months, oldest first, ending with the current one. */
    val months: List<MonthDensity>,
)

/** One block of the strip: which days of that month this watch was worn. */
data class MonthDensity(
    @StringRes val labelRes: Int,
    val daysInMonth: Int,
    /** Day-of-month numbers, 1-based, ascending and deduplicated. */
    val wornDays: List<Int>,
)

/**
 * The stats, or null for a watch that has never been worn.
 *
 * Null hides the line AND the strip together. SPEC-ANDROID 5.6 says the strip is
 * "hidden when it has never been worn", and a stats line reading "Last worn — ·
 * 0 times this year" would be exactly the noise the rest of the app goes out of
 * its way not to make — the desktop's `build_wear_section` returns None for the
 * same reason.
 */
fun wearStats(watch: Watch, today: LocalDate): WearStats? {
    val last = watch.lastWorn() ?: return null

    return WearStats(
        lastWorn = formatDate(last),
        daysSince = watch.daysSinceWorn(today) ?: return null,
        timesThisYear = watch.timesWornThisYear(today),
        longestStreak = watch.longestStreak(),
        months = trailingTwelveMonths(watch.worn, today),
    )
}

/**
 * Twelve blocks ending with the month [today] falls in, oldest first.
 *
 * A density strip, not a navigable calendar: each block knows only how long its
 * month is and which of its days are marked, which is everything the drawing
 * needs and nothing it does not. `YearMonth` does the December-to-January
 * arithmetic and the leap-year day count, both of which are easy to get subtly
 * wrong by hand and neither of which is interesting.
 */
internal fun trailingTwelveMonths(worn: List<LocalDate>, today: LocalDate): List<MonthDensity> {
    val current = YearMonth.from(today)
    // Bucketed once rather than filtered twelve times: a collection with years
    // of history would otherwise walk the whole `worn` list per block.
    val byMonth = worn.groupBy { YearMonth.from(it) }

    return (MONTHS_IN_STRIP - 1 downTo 0).map { back ->
        val month = current.minusMonths(back.toLong())
        MonthDensity(
            labelRes = MONTH_LABELS[month.monthValue - 1],
            daysInMonth = month.lengthOfMonth(),
            wornDays = byMonth[month].orEmpty()
                .map { it.dayOfMonth }
                .distinct()
                .sorted(),
        )
    }
}

private const val MONTHS_IN_STRIP = 12

/**
 * Month names as resources rather than from `java.time`.
 *
 * `Month.getDisplayName` needs a `Locale`, and both answers are wrong here: the
 * default locale is the system one hard rule 7 forbids reading, and
 * `Locale.ENGLISH` would leave the strip in English forever, silently surviving
 * AM11's Turkish sweep because no `values-tr` entry would exist to translate.
 * Twelve resources cost twelve lines and are the only version that can be
 * translated. AM7's calendar reuses them.
 */
private val MONTH_LABELS = intArrayOf(
    R.string.screen_month_short_jan,
    R.string.screen_month_short_feb,
    R.string.screen_month_short_mar,
    R.string.screen_month_short_apr,
    R.string.screen_month_short_may,
    R.string.screen_month_short_jun,
    R.string.screen_month_short_jul,
    R.string.screen_month_short_aug,
    R.string.screen_month_short_sep,
    R.string.screen_month_short_oct,
    R.string.screen_month_short_nov,
    R.string.screen_month_short_dec,
)
