package io.github.sudomegas.saat.widget

import io.github.sudomegas.saat.storage.SaatPaths
import io.github.sudomegas.saat.storage.WatchRecord
import io.github.sudomegas.saat.storage.wornIndex
import java.io.File
import java.time.LocalDate
import java.time.LocalDateTime

/** What the widget shows when a watch is recorded for today. */
data class TodayWatch(
    val slug: String,
    val brand: String,
    val model: String,
    val image: File?,
)

/**
 * The watch recorded for [today], or null — SPEC-ANDROID 5.9.
 *
 * Reads the same index the calendar builds, from the same per-watch `worn`
 * lists. The widget is a fourth reader of the wear history and it adds no fifth
 * store: there is still exactly one place a worn day is written down, which is
 * the watch's own file.
 */
fun List<WatchRecord>.todayWatch(today: LocalDate, paths: SaatPaths): TodayWatch? {
    val record = wornIndex()[today] ?: return null
    val watch = record.watch ?: return null

    return TodayWatch(
        slug = record.slug,
        brand = watch.brand,
        model = watch.model,
        image = watch.images.firstOrNull()
            ?.let { File(paths.watchMedia(record.slug), File(it).name) },
    )
}

/**
 * The next local midnight after [now] — when the widget has to roll over to
 * "Nothing recorded today" without anybody tapping it.
 *
 * A pure function of a local date-time, which is what makes the rollover
 * testable against a fake clock rather than by waiting up. Local, deliberately:
 * a `worn` entry is a plain calendar date with no time and no zone
 * (SPEC-ANDROID 4), so the day the widget is about turns over at the owner's
 * midnight and not at UTC's.
 *
 * Exactly midnight rather than a second after. The alarm that carries this is
 * INEXACT — see [MidnightRefresh] — so it fires at or after the requested time
 * anyway, and asking for the moment itself keeps the arithmetic honest.
 */
fun nextMidnight(now: LocalDateTime): LocalDateTime =
    now.toLocalDate().plusDays(1).atStartOfDay()
