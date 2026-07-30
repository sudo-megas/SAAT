package io.github.sudomegas.saat.storage

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.time.LocalDate

/**
 * The in-memory collection and its write-through edits.
 *
 * Fixtures are built in a temp directory by each test and deleted afterwards —
 * hard rule 1. The dispatcher is [Dispatchers.Unconfined] so that `runBlocking`
 * sees every state update in order without needing a test scheduler, and so
 * without adding a dependency for the sake of four tests.
 */
class WatchRepositoryTest {

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

    // ---- loading ---------------------------------------------------------

    @Test
    fun `before a load, the collection is not empty — it is unread`() {
        val state = repository().state.value

        assertFalse("the empty state must not claim an empty collection yet", state.isLoaded)
        assertEquals(emptyList<WatchRecord>(), state.records)
    }

    @Test
    fun `loading publishes the collection`() = runBlocking {
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\n")
        writeWatch("casio-f-91w", "brand = \"Casio\"\nmodel = \"F-91W\"\n")

        val repository = repository()
        repository.load()

        val state = repository.state.value
        assertTrue(state.isLoaded)
        assertEquals(listOf("casio-f-91w", "seiko-skx007"), state.watches.map { it.slug })
        assertEquals(emptyList<WatchRecord>(), state.failures)
    }

    @Test
    fun `an empty collection loads as loaded and empty`() = runBlocking {
        val repository = repository()
        repository.load()

        assertTrue("this is what the empty state renders from", repository.state.value.isLoaded)
        assertEquals(emptyList<WatchRecord>(), repository.state.value.records)
    }

    @Test
    fun `failures stay in the collection instead of disappearing from it`() = runBlocking {
        writeWatch("good", "brand = \"Seiko\"\nmodel = \"SKX007\"\n")
        writeWatch("broken", "not valid toml [[[")

        val repository = repository()
        repository.load()
        val state = repository.state.value

        assertEquals("both folders are the owner's", 2, state.records.size)
        assertEquals(listOf("good"), state.watches.map { it.slug })
        assertEquals(listOf("broken"), state.failures.map { it.slug })
        assertNotNull(state.failures.single().loadError)
    }

    @Test
    fun `field warnings are collected across the collection and named by watch`() = runBlocking {
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\nrating = \"high\"\n")

        val repository = repository()
        repository.load()

        assertEquals(1, repository.state.value.warnings.size)
        assertTrue(
            "a warning must say which watch it is about: ${repository.state.value.warnings}",
            repository.state.value.warnings.single().startsWith("seiko-skx007: rating:"),
        )
    }

    @Test
    fun `loading reads from disk and writes nothing`() = runBlocking {
        val handWritten = "# a comment the loader must not disturb\nbrand = \"Seiko\"\nmodel = \"SKX007\"\n"
        writeWatch("seiko-skx007", handWritten)

        repository().load()

        assertEquals(handWritten, paths.watchToml("seiko-skx007").readText())
        assertFalse("no backup, because nothing was written", paths.backupsDir.exists())
    }

    // ---- creating --------------------------------------------------------

    @Test
    fun `creating adds to memory and to disk, in slug order`() = runBlocking {
        val repository = repository()
        repository.load()

        repository.create(Watch(brand = "Seiko", model = "SKX007"))
        repository.create(Watch(brand = "Casio", model = "F-91W"))

        assertEquals(
            listOf("casio-f-91w", "seiko-skx007"),
            repository.state.value.records.map { it.slug },
        )
        assertTrue(paths.watchToml("seiko-skx007").exists())
        assertTrue(paths.watchToml("casio-f-91w").exists())
    }

    // ---- editing ---------------------------------------------------------

    @Test
    fun `an edit reaches memory and disk`() = runBlocking {
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\n")
        val repository = repository()
        repository.load()

        repository.update("seiko-skx007") { it.copy(rating = 5, notes = "A keeper.") }

        assertEquals(5, repository.state.value.watches.single().watch!!.rating)
        assertTrue(paths.watchToml("seiko-skx007").readText().contains("rating = 5"))
        assertNull(repository.state.value.writeError)
        assertFalse(
            "after a successful save the record is clean again",
            repository.state.value.watches.single().isDirty,
        )
    }

    @Test
    fun `an edit that changes nothing writes nothing`() = runBlocking {
        val handWritten = "# keep me\nbrand = \"Seiko\"\nmodel = \"SKX007\"\nrating = 5\n"
        writeWatch("seiko-skx007", handWritten)
        val repository = repository()
        repository.load()

        // Byte preservation reaches all the way up: a transform that returns an
        // equal watch is not an edit, whatever the caller believed.
        repository.update("seiko-skx007") { it.copy(rating = 5) }

        assertEquals(handWritten, paths.watchToml("seiko-skx007").readText())
        assertFalse(paths.backupsDir.exists())
    }

    @Test
    fun `a wear toggle can skip the backup`() = runBlocking {
        // Created here rather than hand-written, because a file this app has
        // not written yet is snapshotted whatever the flag says — regenerating
        // it would change bytes nothing else keeps a copy of. See
        // `a wear toggle still snapshots a file it is about to regenerate`.
        val repository = repository()
        repository.load()
        repository.create(Watch(brand = "Seiko", model = "SKX007"))

        repository.update("seiko-skx007", backup = false) {
            it.copy(worn = it.worn + LocalDate.of(2026, 7, 29))
        }

        assertEquals(
            listOf(LocalDate.of(2026, 7, 29)),
            repository.state.value.watches.single().watch!!.worn,
        )
        assertFalse(paths.backupsDir.exists())
    }

    @Test
    fun `editing an unknown or unreadable watch is a no-op`() = runBlocking {
        writeWatch("broken", "not valid toml [[[")
        val repository = repository()
        repository.load()

        assertNull(repository.update("no-such-watch") { it.copy(rating = 1) })
        assertNull("a watch that did not load has nothing to edit", repository.update("broken") { it })
        assertNull(repository.state.value.writeError)
    }

    // ---- when the disk says no -------------------------------------------

    @Test
    fun `a failed write keeps the edit in memory and surfaces the error`() = runBlocking {
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\n")
        val repository = repository(FailingStore(paths, "No space left on device"))
        repository.load()

        val result = repository.update("seiko-skx007") { it.copy(rating = 5) }

        assertEquals("the owner's edit must not be thrown away", 5, result!!.watch!!.rating)
        assertEquals(5, repository.state.value.watches.single().watch!!.rating)
        assertTrue(
            "and it must still be pending, so a later save writes it",
            repository.state.value.watches.single().isDirty,
        )

        val error = repository.state.value.writeError
        assertNotNull("hard rule 6: never a log line", error)
        assertTrue(
            "the real message must survive intact: $error",
            error!!.contains("No space left on device") && error.contains("seiko-skx007"),
        )

        repository.clearWriteError()
        assertNull(repository.state.value.writeError)
    }

    @Test
    fun `a reload keeps an edit that has not reached disk`() = runBlocking {
        // Nothing calls load() twice today, but AM10's import will, and a
        // wholesale replacement takes the record whose write failed — kept in
        // memory on purpose — and swaps it for the older text still in the file.
        // That is the loss the write-through policy exists to prevent, and it
        // would happen without a word.
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\n")
        val store = SometimesFailingStore(paths)
        val repository = repository(store)
        repository.load()

        store.failing = true
        repository.update("seiko-skx007") { it.copy(notes = "typed by the owner") }
        store.failing = false

        repository.load()

        val record = repository.state.value.watches.single()
        assertEquals(
            "a reload must not swap the owner's edit for what is still on disk",
            "typed by the owner",
            record.watch!!.notes,
        )
        assertTrue("and it must still be pending, so a later save writes it", record.isDirty)
    }

    @Test
    fun `a reload does not dismiss a notice the owner has not seen`() = runBlocking {
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\n")
        val store = SometimesFailingStore(paths)
        val repository = repository(store)
        repository.load()

        store.failing = true
        repository.update("seiko-skx007") { it.copy(rating = 5) }
        store.failing = false
        assertNotNull(repository.state.value.writeError)

        repository.load()

        assertNotNull(
            "only clearWriteError() dismisses it, once the owner has read it",
            repository.state.value.writeError,
        )
    }

    @Test
    fun `a failed delete puts the watch back`() = runBlocking {
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\n")
        val repository = repository(FailingStore(paths, "Read-only file system"))
        repository.load()

        assertFalse(repository.delete("seiko-skx007"))

        // Unlike a failed edit there is nothing the owner typed to preserve, and
        // a watch missing from the grid while still on disk would be a lie.
        assertEquals(listOf("seiko-skx007"), repository.state.value.records.map { it.slug })
        assertTrue(repository.state.value.writeError!!.contains("Read-only file system"))
    }

    @Test
    fun `a failed create reports and adds nothing`() = runBlocking {
        val repository = repository(FailingStore(paths, "No space left on device"))
        repository.load()

        assertNull(repository.create(Watch(brand = "Seiko", model = "SKX007")))
        assertEquals(emptyList<WatchRecord>(), repository.state.value.records)
        assertTrue(repository.state.value.writeError!!.contains("No space left on device"))
    }

    // ---- deleting --------------------------------------------------------

    @Test
    fun `deleting removes it from memory and from the collection folder`() = runBlocking {
        val repository = repository()
        repository.load()
        val created = repository.create(fullyPopulatedWatch())!!

        assertTrue(repository.delete(created.slug))

        assertEquals(emptyList<WatchRecord>(), repository.state.value.records)
        assertFalse(paths.watchDir(created.slug).exists())
        assertTrue(
            "moved, not erased",
            File(paths.deletedDir, "${created.slug}/${SaatPaths.WATCH_FILENAME}").exists(),
        )
    }

    @Test
    fun `deleting an unknown slug is a no-op`() = runBlocking {
        val repository = repository()
        repository.load()
        assertFalse(repository.delete("no-such-watch"))
        assertNull(repository.state.value.writeError)
    }

    // ---- concurrency -----------------------------------------------------

    @Test
    fun `simultaneous edits do not overwrite one another`() = runBlocking {
        // Not hypothetical after AM8: "wore this today" lives on the detail
        // page, on the home-screen widget and on an app shortcut, all three
        // driving this one collection. Each edit is a read-modify-write with a
        // suspension point in the middle, so two at once would otherwise both
        // start from the same record and the second would silently overwrite
        // the first — a lost day, on disk, with nothing to notice it by.
        //
        // Real threads here rather than Unconfined, because Unconfined would
        // run these sequentially and the test would pass whether or not the
        // repository actually serialises anything.
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\n")
        val repository = WatchRepository(WatchStore(paths), Dispatchers.Default)
        repository.load()

        val days = (1..20).map { LocalDate.of(2026, 1, it) }
        coroutineScope {
            days.forEach { day ->
                launch(Dispatchers.Default) {
                    repository.update("seiko-skx007", backup = false) {
                        it.copy(worn = (it.worn + day).sorted())
                    }
                }
            }
        }

        assertEquals("every edit must survive in memory", days, repository.state.value.watches.single().watch!!.worn)

        val reread = repository()
        reread.load()
        assertEquals("and on disk", days, reread.state.value.watches.single().watch!!.worn)
    }

    // ---- a full turn -----------------------------------------------------

    @Test
    fun `create, edit, reload — the collection matches what is on disk`() = runBlocking {
        val repository = repository()
        repository.load()

        val created = repository.create(fullyPopulatedWatch())!!
        repository.update(created.slug) { it.copy(rating = 3, notes = "Re-rated.") }

        val reread = repository()
        reread.load()

        assertEquals(repository.state.value.watches.single().watch, reread.state.value.watches.single().watch)
        assertEquals(3, reread.state.value.watches.single().watch!!.rating)
        assertEquals("Re-rated.", reread.state.value.watches.single().watch!!.notes)
    }

    /** A store whose writes always fail, for the paths that only exist when they do. */
    /** Fails on demand, so a test can fail one write and let the next through. */
    private class SometimesFailingStore(paths: SaatPaths) : WatchStore(paths) {
        var failing = false

        override fun save(record: WatchRecord, backup: Boolean): WatchRecord {
            if (failing) throw java.io.IOException("No space left on device")
            return super.save(record, backup)
        }
    }

    private class FailingStore(paths: SaatPaths, private val reason: String) : WatchStore(paths) {
        override fun save(record: WatchRecord, backup: Boolean): WatchRecord =
            throw java.io.IOException(reason)

        override fun create(watch: Watch): WatchRecord = throw java.io.IOException(reason)

        override fun delete(record: WatchRecord): Unit = throw java.io.IOException(reason)
    }
}
