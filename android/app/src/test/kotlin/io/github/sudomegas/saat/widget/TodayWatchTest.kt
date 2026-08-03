package io.github.sudomegas.saat.widget

import io.github.sudomegas.saat.storage.SaatPaths
import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.WatchRecord
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.io.File
import java.time.LocalDate
import java.time.LocalDateTime

/**
 * What the widget shows, and when it rolls over — SPEC-ANDROID 5.9.
 *
 * Both are pure functions of a date, which is the whole reason the widget's
 * logic is not inside the provider: an AppWidgetProvider can only be exercised
 * on a device, and "does it become 'Nothing recorded today' at midnight" is not
 * a question anyone should answer by staying up.
 */
class TodayWatchTest {

    private val paths = SaatPaths(File("/files"))
    private val today = LocalDate.of(2026, 8, 3)

    private fun record(
        slug: String,
        status: String = Watch.STATUS_OWNED,
        images: List<String> = emptyList(),
        vararg worn: LocalDate,
    ): WatchRecord {
        val watch = Watch(
            brand = "Seiko",
            model = slug,
            status = status,
            worn = worn.toList(),
            images = images,
        )
        return WatchRecord(slug, File("/watches/$slug"), watch = watch, loaded = watch)
    }

    // --- what it shows ------------------------------------------------------

    @Test
    fun `today's watch is the one holding today`() {
        val watch = listOf(
            record("skx", worn = arrayOf(today.minusDays(1))),
            record("f91w", worn = arrayOf(today)),
        ).todayWatch(today, paths)!!

        assertEquals("f91w", watch.slug)
        assertEquals("Seiko", watch.brand)
    }

    @Test
    fun `nothing recorded today is null, not an empty watch`() {
        assertNull(listOf(record("skx", worn = arrayOf(today.minusDays(1)))).todayWatch(today, paths))
        assertNull(emptyList<WatchRecord>().todayWatch(today, paths))
    }

    @Test
    fun `a watch that is not Owned does not hold today`() {
        // The same rule the calendar's index keeps: a sold watch is not on
        // anybody's wrist, so it cannot be what you are wearing.
        val records = listOf(record("sold", status = "Sold", worn = arrayOf(today)))

        assertNull(records.todayWatch(today, paths))
    }

    @Test
    fun `the primary photograph resolves into the media tree`() {
        val watch = listOf(
            record("skx", images = listOf("front.jpg", "back.jpg"), worn = arrayOf(today)),
        ).todayWatch(today, paths)!!

        assertEquals(File(paths.watchMedia("skx"), "front.jpg"), watch.image)
    }

    @Test
    fun `a watch with no photograph still shows, with no image`() {
        val watch = listOf(record("skx", worn = arrayOf(today))).todayWatch(today, paths)!!

        assertNull(watch.image)
        assertEquals("skx", watch.slug)
    }

    // --- when it rolls over -------------------------------------------------

    @Test
    fun `the next midnight is the start of tomorrow`() {
        assertEquals(
            LocalDateTime.of(2026, 8, 4, 0, 0),
            nextMidnight(LocalDateTime.of(2026, 8, 3, 14, 30)),
        )
    }

    @Test
    fun `a moment just before midnight rolls over within the minute`() {
        assertEquals(
            LocalDateTime.of(2026, 8, 4, 0, 0),
            nextMidnight(LocalDateTime.of(2026, 8, 3, 23, 59, 59)),
        )
    }

    @Test
    fun `midnight itself schedules the NEXT one, not itself`() {
        // Otherwise the alarm that just fired would re-arm for the instant it
        // fired at, and either fire again immediately or never.
        assertEquals(
            LocalDateTime.of(2026, 8, 4, 0, 0),
            nextMidnight(LocalDateTime.of(2026, 8, 3, 0, 0)),
        )
    }

    @Test
    fun `it crosses a month and a year boundary`() {
        assertEquals(
            LocalDateTime.of(2026, 9, 1, 0, 0),
            nextMidnight(LocalDateTime.of(2026, 8, 31, 22, 0)),
        )
        assertEquals(
            LocalDateTime.of(2027, 1, 1, 0, 0),
            nextMidnight(LocalDateTime.of(2026, 12, 31, 23, 30)),
        )
    }

    @Test
    fun `a leap day is an ordinary day to roll over`() {
        assertEquals(
            LocalDateTime.of(2028, 2, 29, 0, 0),
            nextMidnight(LocalDateTime.of(2028, 2, 28, 12, 0)),
        )
    }

    // --- the bitmap ---------------------------------------------------------

    @Test
    fun `a photograph is subsampled to fit a Binder transaction`() {
        // BitmapFactory only honours powers of two, so anything else would be
        // silently rounded anyway.
        assertEquals(1, sampleSize(512, 384, 512))
        assertEquals(2, sampleSize(1024, 768, 512))
        assertEquals(4, sampleSize(2048, 1536, 512))
        assertEquals(8, sampleSize(4000, 3000, 512))
    }

    @Test
    fun `an image already small enough is not subsampled`() {
        assertEquals(1, sampleSize(100, 100, 512))
        assertEquals(1, sampleSize(1, 1, 512))
    }

    @Test
    fun `the longer edge decides`() {
        assertEquals(2, sampleSize(400, 1024, 512))
    }
}
