package io.github.sudomegas.saat.storage

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.time.LocalDate

/**
 * The single wear-logging path — SPEC-ANDROID 5.5 and 5.6.
 *
 * This is the method AM4's detail button, AM7's calendar, AM8's widget and
 * AM8's shortcut all call, so the rules it enforces are tested here rather than
 * near any one of them. The two that matter are the two that are invisible when
 * they break: a second tap on the same day must write nothing, and a day
 * already belonging to another watch must MOVE rather than be shared.
 *
 * Dates are parameters everywhere, never `LocalDate.now()`, so these are true on
 * every day rather than on the day they were written — the convention `Derived`
 * set and the reason `assignWorn` takes its dates from the caller.
 */
class WearLoggingTest {

    @get:Rule
    val temp = TemporaryFolder()

    private val paths get() = SaatPaths(temp.root)

    private fun repository(store: WatchStore = WatchStore(paths)) =
        WatchRepository(store, Dispatchers.Unconfined)

    private fun writeWatch(slug: String, body: String) {
        val dir = File(paths.watchesDir, slug)
        dir.mkdirs()
        File(dir, SaatPaths.WATCH_FILENAME).writeText(body)
    }

    private fun tomlOf(slug: String) = File(paths.watchDir(slug), SaatPaths.WATCH_FILENAME)

    private suspend fun loaded(): WatchRepository = repository().also { it.load() }

    private fun WatchRepository.wornOf(slug: String): List<LocalDate> =
        record(slug)?.watch?.worn.orEmpty()

    private val today = LocalDate.of(2026, 8, 3)

    // ---- idempotence -------------------------------------------------------

    @Test
    fun `recording a day writes it once`() = runBlocking {
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\n")
        val repository = loaded()

        val result = repository.assignWorn("seiko-skx007", listOf(today))!!

        assertEquals(listOf(today), repository.wornOf("seiko-skx007"))
        assertEquals(listOf(today), result.recorded)
        assertEquals(emptyList<LocalDate>(), result.alreadyRecorded)
        assertFalse(result.changedNothing)
    }

    @Test
    fun `a second tap the same day changes nothing and says so`() = runBlocking {
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\n")
        val repository = loaded()

        repository.assignWorn("seiko-skx007", listOf(today))
        val before = tomlOf("seiko-skx007").readText()

        val second = repository.assignWorn("seiko-skx007", listOf(today))!!

        assertEquals(listOf(today), repository.wornOf("seiko-skx007"))
        assertEquals(listOf(today), second.alreadyRecorded)
        assertEquals(emptyList<LocalDate>(), second.recorded)
        assertTrue("a repeat tap must be a no-op the UI can see", second.changedNothing)
        // Not merely equal in memory: the file must not have been rewritten at
        // all, or every idle tap would burn a backup slot and churn the disk.
        assertEquals(before, tomlOf("seiko-skx007").readText())
    }

    @Test
    fun `idempotence is per calendar date, not per call`() = runBlocking {
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\n")
        val repository = loaded()

        repository.assignWorn("seiko-skx007", listOf(today))
        repository.assignWorn("seiko-skx007", listOf(today.plusDays(1)))
        repository.assignWorn("seiko-skx007", listOf(today))

        assertEquals(listOf(today, today.plusDays(1)), repository.wornOf("seiko-skx007"))
    }

    // ---- one watch per day -------------------------------------------------

    @Test
    fun `a day already owned by another watch moves silently`() = runBlocking {
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\nworn = [2026-08-03]\n")
        writeWatch("casio-f-91w", "brand = \"Casio\"\nmodel = \"F-91W\"\n")
        val repository = loaded()

        val result = repository.assignWorn("casio-f-91w", listOf(today))!!

        assertEquals(listOf(today), repository.wornOf("casio-f-91w"))
        assertEquals(emptyList<LocalDate>(), repository.wornOf("seiko-skx007"))
        assertEquals(mapOf("seiko-skx007" to listOf(today)), result.takenFrom)
        // No error, no prompt: the move is the rule working, not a failure.
        assertNull(repository.state.value.writeError)
    }

    @Test
    fun `moving a day leaves that watch's other days alone`() = runBlocking {
        writeWatch(
            "seiko-skx007",
            "brand = \"Seiko\"\nmodel = \"SKX007\"\nworn = [2026-08-01, 2026-08-03, 2026-08-05]\n",
        )
        writeWatch("casio-f-91w", "brand = \"Casio\"\nmodel = \"F-91W\"\n")
        val repository = loaded()

        repository.assignWorn("casio-f-91w", listOf(today))

        assertEquals(
            listOf(LocalDate.of(2026, 8, 1), LocalDate.of(2026, 8, 5)),
            repository.wornOf("seiko-skx007"),
        )
    }

    @Test
    fun `a range can take days from more than one watch at once`() = runBlocking {
        // AM7's drag-selected span. One call, one critical section — which is
        // why assignWorn takes a collection rather than being called in a loop.
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\nworn = [2026-08-01]\n")
        writeWatch("casio-f-91w", "brand = \"Casio\"\nmodel = \"F-91W\"\nworn = [2026-08-02]\n")
        writeWatch("orient-bambino", "brand = \"Orient\"\nmodel = \"Bambino\"\n")
        val repository = loaded()

        val span = (1..3).map { LocalDate.of(2026, 8, it) }
        val result = repository.assignWorn("orient-bambino", span)!!

        assertEquals(span, repository.wornOf("orient-bambino"))
        assertEquals(emptyList<LocalDate>(), repository.wornOf("seiko-skx007"))
        assertEquals(emptyList<LocalDate>(), repository.wornOf("casio-f-91w"))
        assertEquals(setOf("seiko-skx007", "casio-f-91w"), result.takenFrom.keys)
    }

    @Test
    fun `a watch that is not Owned still gives up a day it holds`() = runBlocking {
        // The desktop's _strip_dates does not filter on status either: only the
        // calendar's INDEX is Owned-only. A sold watch's stale day must be
        // released rather than left to shadow the new assignment.
        writeWatch(
            "seiko-skx007",
            "brand = \"Seiko\"\nmodel = \"SKX007\"\nstatus = \"Sold\"\nworn = [2026-08-03]\n",
        )
        writeWatch("casio-f-91w", "brand = \"Casio\"\nmodel = \"F-91W\"\n")
        val repository = loaded()

        repository.assignWorn("casio-f-91w", listOf(today))

        assertEquals(emptyList<LocalDate>(), repository.wornOf("seiko-skx007"))
    }

    // ---- clearing (AM7's calendar) -----------------------------------------

    @Test
    fun `clearing takes days off whichever watches hold them`() = runBlocking {
        // A drag-selected span can cross more than one owner, so one gesture can
        // touch several watches — the desktop's clear_worn behaves the same.
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\nworn = [2026-08-01, 2026-08-03]\n")
        writeWatch("casio-f-91w", "brand = \"Casio\"\nmodel = \"F-91W\"\nworn = [2026-08-02]\n")
        val repository = loaded()

        val cleared = repository.clearWorn((1..2).map { LocalDate.of(2026, 8, it) })

        assertEquals(setOf("seiko-skx007", "casio-f-91w"), cleared.toSet())
        assertEquals(listOf(today), repository.wornOf("seiko-skx007"))
        assertEquals(emptyList<LocalDate>(), repository.wornOf("casio-f-91w"))
    }

    @Test
    fun `clearing a day nobody holds changes nothing`() = runBlocking {
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\nworn = [2026-08-03]\n")
        val repository = loaded()
        val before = tomlOf("seiko-skx007").readText()

        assertEquals(emptyList<String>(), repository.clearWorn(listOf(LocalDate.of(2026, 9, 9))))
        assertEquals(before, tomlOf("seiko-skx007").readText())
    }

    @Test
    fun `clearing an empty span is a no-op`() = runBlocking {
        val repository = loaded()

        assertEquals(emptyList<String>(), repository.clearWorn(emptyList()))
    }

    @Test
    fun `a range assignment fills every day in the span`() = runBlocking {
        // What long-press range mode does: one call, one critical section, and
        // the same one-per-day rule applied across the whole span.
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\n")
        val repository = loaded()

        val span = (1..7).map { LocalDate.of(2026, 8, it) }
        repository.assignWorn("seiko-skx007", span)

        assertEquals(span, repository.wornOf("seiko-skx007"))
    }

    // ---- what it writes ----------------------------------------------------

    @Test
    fun `worn days are stored sorted and deduplicated`() = runBlocking {
        // A hand-edited file can list a day twice and list them out of order.
        // The desktop writes sorted(set(...)), and longestStreak already has to
        // defend against duplicates, so the first wear tap tidies them.
        writeWatch(
            "seiko-skx007",
            "brand = \"Seiko\"\nmodel = \"SKX007\"\nworn = [2026-08-05, 2026-08-01, 2026-08-05]\n",
        )
        val repository = loaded()

        repository.assignWorn("seiko-skx007", listOf(today))

        assertEquals(
            listOf(LocalDate.of(2026, 8, 1), today, LocalDate.of(2026, 8, 5)),
            repository.wornOf("seiko-skx007"),
        )
    }

    @Test
    fun `a wear toggle does not spend a backup slot`() = runBlocking {
        // backups/ is pruned to twenty shared slots and one calendar gesture can
        // touch many watches. The first save still takes a snapshot, because
        // regenerating a hand-written file would lose bytes this app cannot
        // reproduce; every toggle after that must not.
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\n")
        val repository = loaded()

        repository.assignWorn("seiko-skx007", listOf(today))
        val afterFirst = paths.backupsDir.listFiles().orEmpty().count { it.isFile }

        repository.assignWorn("seiko-skx007", listOf(today.plusDays(1)))
        repository.assignWorn("seiko-skx007", listOf(today.plusDays(2)))

        assertEquals(
            "only the first regeneration of a hand-written file may take a snapshot",
            afterFirst,
            paths.backupsDir.listFiles().orEmpty().count { it.isFile },
        )
    }

    @Test
    fun `the edit survives a reload, which means it reached the disk`() = runBlocking {
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\n")
        val repository = loaded()

        repository.assignWorn("seiko-skx007", listOf(today))

        val reread = repository()
        reread.load()
        assertEquals(listOf(today), reread.wornOf("seiko-skx007"))
    }

    // ---- the edges ---------------------------------------------------------

    @Test
    fun `deleting a watch takes its wear history with it`() = runBlocking {
        // AM5's brief: "Its wear history goes with it — a watch folder is a
        // complete record, desktop rule." That needs no code at all, and this
        // test is what says so: `worn` lives in the watch's own file and nowhere
        // else, so moving the folder moves the history. The day it was worn is
        // also released, rather than staying claimed by a watch that is gone.
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\nworn = [2026-08-03]\n")
        writeWatch("casio-f-91w", "brand = \"Casio\"\nmodel = \"F-91W\"\n")
        val repository = loaded()

        repository.delete("seiko-skx007")

        assertNull(repository.record("seiko-skx007"))
        val grave = File(File(paths.deletedDir, "seiko-skx007"), SaatPaths.WATCH_FILENAME)
        assertTrue("the record must be in the grave", grave.exists())
        assertTrue("its wear history goes with it", grave.readText().contains("2026-08-03"))

        // And the day is now free: the rule is one watch per day across the
        // collection, and a deleted watch is not in the collection.
        val result = repository.assignWorn("casio-f-91w", listOf(today))!!
        assertEquals(listOf(today), repository.wornOf("casio-f-91w"))
        assertEquals(emptyMap<String, List<LocalDate>>(), result.takenFrom)
    }

    @Test
    fun `an unknown slug is null rather than an exception`() = runBlocking {
        val repository = loaded()

        assertNull(repository.assignWorn("nothing-here", listOf(today)))
    }

    @Test
    fun `a watch that did not load is never written to`() = runBlocking {
        // Its `watch` is null, so there is nothing to add a day to — and writing
        // would overwrite a file whose contents we could not read.
        writeWatch("broken", "brand = \"Seiko\"\nmodel =\n")
        val repository = loaded()

        assertNull(repository.assignWorn("broken", listOf(today)))
    }

    @Test
    fun `an empty date collection is a no-op`() = runBlocking {
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\n")
        val repository = loaded()

        val result = repository.assignWorn("seiko-skx007", emptyList())!!

        assertTrue(result.changedNothing)
        assertEquals(emptyList<LocalDate>(), repository.wornOf("seiko-skx007"))
    }

    @Test
    fun `a failed write leaves the day in memory and the message on the state`() = runBlocking {
        // Hard rule 6, and the write-through policy: what the owner just did
        // stays in memory, and the reason it did not reach the disk is said out
        // loud rather than swallowed.
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\n")
        val failing = object : WatchStore(paths) {
            override fun save(record: WatchRecord, backup: Boolean): WatchRecord =
                throw java.io.IOException("No space left on device")
        }
        val repository = repository(failing)
        repository.load()

        repository.assignWorn("seiko-skx007", listOf(today))

        assertEquals(listOf(today), repository.wornOf("seiko-skx007"))
        assertTrue(
            repository.state.value.writeError.orEmpty().contains("No space left on device"),
        )
    }
}
