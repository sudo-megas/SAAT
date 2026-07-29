package io.github.sudomegas.saat.storage

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
import java.time.LocalDateTime

/**
 * The storage layer against a real filesystem.
 *
 * Every fixture tree is built in a temp directory by the test that needs it and
 * deleted afterwards — SPEC-ANDROID hard rule 1 applies to test assets exactly
 * as it applies to shipped code, so there is no `fixtures/` folder anywhere in
 * this repository and never will be.
 */
class WatchStoreTest {

    @get:Rule
    val temp = TemporaryFolder()

    private var clock = LocalDateTime.of(2026, 7, 29, 14, 30, 0)

    private val paths get() = SaatPaths(temp.root)
    private val store get() = WatchStore(paths) { clock }

    private fun writeWatch(slug: String, body: String): File {
        val dir = File(paths.watchesDir, slug)
        dir.mkdirs()
        val file = File(dir, SaatPaths.WATCH_FILENAME)
        file.writeText(body)
        return file
    }

    private fun watchToml(brand: String, model: String) = "brand = \"$brand\"\nmodel = \"$model\"\n"

    // ---- loading ---------------------------------------------------------

    @Test
    fun `an empty collection is an empty list, not a failure`() {
        assertEquals(emptyList<WatchRecord>(), store.loadCollection())

        paths.watchesDir.mkdirs()
        assertEquals(emptyList<WatchRecord>(), store.loadCollection())
    }

    @Test
    fun `watches load in slug order`() {
        writeWatch("seiko-skx007", watchToml("Seiko", "SKX007"))
        writeWatch("casio-f-91w", watchToml("Casio", "F-91W"))
        writeWatch("orient-bambino", watchToml("Orient", "Bambino"))

        assertEquals(
            listOf("casio-f-91w", "orient-bambino", "seiko-skx007"),
            store.loadCollection().map { it.slug },
        )
    }

    @Test
    fun `entries starting with underscore or dot are skipped`() {
        writeWatch("seiko-skx007", watchToml("Seiko", "SKX007"))
        writeWatch("_template", watchToml("Template", "Template"))
        writeWatch(".hidden", watchToml("Hidden", "Hidden"))
        File(paths.watchesDir, "notes.txt").writeText("not a watch")

        assertEquals(listOf("seiko-skx007"), store.loadCollection().map { it.slug })
    }

    @Test
    fun `a folder with no watch toml is reported rather than skipped`() {
        File(paths.watchesDir, "empty-folder").mkdirs()

        val record = store.loadCollection().single()
        assertEquals("empty-folder", record.slug)
        assertNull(record.watch)
        assertTrue(
            "the error must name what is missing: ${record.loadError}",
            record.loadError.orEmpty().contains(SaatPaths.WATCH_FILENAME),
        )
    }

    @Test
    fun `a malformed watch does not take the rest of the collection with it`() {
        writeWatch("good-one", watchToml("Seiko", "SKX007"))
        writeWatch("broken", "this is not = = valid toml [[[")
        writeWatch("nameless", "reference = \"no brand here\"\n")
        writeWatch("also-good", watchToml("Casio", "F-91W"))

        val records = store.loadCollection().associateBy { it.slug }

        assertEquals(4, records.size)
        assertNotNull(records.getValue("good-one").watch)
        assertNotNull(records.getValue("also-good").watch)

        val broken = records.getValue("broken")
        assertNull(broken.watch)
        assertNotNull("never silent — hard rule 6", broken.loadError)

        val nameless = records.getValue("nameless")
        assertNull(nameless.watch)
        assertTrue(
            "the error must say what is missing: ${nameless.loadError}",
            nameless.loadError.orEmpty().contains("brand"),
        )
    }

    @Test
    fun `field warnings travel out with the record`() {
        writeWatch("seiko-skx007", "brand = \"Seiko\"\nmodel = \"SKX007\"\nrating = \"high\"\n")

        val record = store.loadCollection().single()
        assertNotNull("a bad field costs the field, not the watch", record.watch)
        assertNull(record.loadError)
        assertTrue(record.warnings.single().startsWith("rating:"))
    }

    // ---- byte preservation -----------------------------------------------

    @Test
    fun `a watch that was loaded and not edited is never rewritten`() {
        // The file is hand-shaped: comments, blank lines, an unusual key order,
        // spacing the writer would never produce. If anything rewrites it, the
        // comments are the first thing to go — this app's writer regenerates
        // files rather than editing them in place.
        val handWritten = """
            # My first good watch. Bought in İzmir, 2019.
            brand = "Seiko"
            model  =  "SKX007"

            # Still on the original bracelet.
            [case]
            lug_width_mm = 22   # measured, not from the spec sheet
            diameter_mm  = 42.5
        """.trimIndent() + "\n"

        val file = writeWatch("seiko-skx007", handWritten)

        val records = store.loadCollection()
        assertEquals(handWritten, file.readText())

        // Saving an untouched record must be a no-op, even when asked directly.
        val saved = store.save(records.single())
        assertEquals("an unedited watch must keep its exact bytes", handWritten, file.readText())
        assertEquals(records.single(), saved)

        assertFalse(
            "a no-op save must not take a backup either",
            paths.backupsDir.exists() && paths.backupsDir.listFiles().orEmpty().isNotEmpty(),
        )
    }

    @Test
    fun `an actual edit does rewrite, and the old version goes to backups`() {
        val original = "# a comment\nbrand = \"Seiko\"\nmodel = \"SKX007\"\n"
        val file = writeWatch("seiko-skx007", original)

        val record = store.loadCollection().single()
        val edited = record.copy(watch = record.watch!!.copy(rating = 5))
        assertTrue("the record must know it is dirty", edited.isDirty)

        val saved = store.save(edited)

        assertTrue("the edit must reach disk", file.readText().contains("rating = 5"))
        assertFalse(
            "the comment is lost on first edit, and the docs say so",
            file.readText().contains("# a comment"),
        )
        assertFalse("saving again must now be a no-op", saved.isDirty)

        val backup = paths.backupsDir.listFiles().orEmpty().single()
        assertEquals("the backup must hold the version from BEFORE the edit", original, backup.readText())
    }

    @Test
    fun `saving a record twice writes once`() {
        writeWatch("seiko-skx007", watchToml("Seiko", "SKX007"))
        val record = store.loadCollection().single()

        val saved = store.save(record.copy(watch = record.watch!!.copy(rating = 4)))
        val backupsAfterFirst = paths.backupsDir.listFiles().orEmpty().size

        store.save(saved)
        assertEquals(
            "the second save has nothing to write and nothing to back up",
            backupsAfterFirst,
            paths.backupsDir.listFiles().orEmpty().size,
        )
    }

    @Test
    fun `a write leaves no temp file behind`() {
        val created = store.create(minimalWatch())
        store.save(created.copy(watch = created.watch!!.copy(rating = 3)))

        val strays = created.dir.listFiles().orEmpty().filter { it.name.endsWith(".tmp") }
        assertTrue("an orphaned .tmp looks like corruption to someone browsing: $strays", strays.isEmpty())
        assertEquals(listOf(SaatPaths.WATCH_FILENAME), created.dir.listFiles().orEmpty().map { it.name })
    }

    @Test
    fun `saving a watch that failed to load is refused`() {
        writeWatch("broken", "not valid toml [[[")
        val record = store.loadCollection().single()

        val failure = runCatching { store.save(record) }.exceptionOrNull()
        assertTrue("expected a refusal, got $failure", failure is IllegalArgumentException)
        assertEquals("the unreadable file must be left alone", "not valid toml [[[", File(record.dir, SaatPaths.WATCH_FILENAME).readText())
    }

    // ---- creating --------------------------------------------------------

    @Test
    fun `a new watch gets a slug, a folder and a file`() {
        val record = store.create(Watch(brand = "Seiko", model = "SKX007"))

        assertEquals("seiko-skx007", record.slug)
        assertTrue(paths.watchToml("seiko-skx007").exists())
        assertFalse("a brand new watch has no previous version to back up", paths.backupsDir.exists())
        assertFalse(record.isDirty)
        assertEquals(record.watch, store.loadCollection().single().watch)
    }

    @Test
    fun `a second watch of the same model gets a numbered slug`() {
        store.create(Watch(brand = "Seiko", model = "SKX007"))
        val second = store.create(Watch(brand = "Seiko", model = "SKX007"))

        assertEquals("seiko-skx007-2", second.slug)
        assertEquals(2, store.loadCollection().size)
    }

    @Test
    fun `a hidden folder still occupies its name`() {
        // The loader skips `_seiko-skx007`, but the filesystem does not: creating
        // a second folder with that name would fail, so the slug must dodge it.
        File(paths.watchesDir, "_seiko-skx007").mkdirs()
        File(paths.watchesDir, "Seiko-SKX007").mkdirs()

        val record = store.create(Watch(brand = "Seiko", model = "SKX007"))
        assertEquals("case-insensitively, seiko-skx007 is taken", "seiko-skx007-2", record.slug)
    }

    @Test
    fun `a watch with only a brand and a model is creatable`() {
        val record = store.create(minimalWatch())
        assertEquals(minimalWatch(), store.loadCollection().single().watch)
        assertEquals("casio-f-91w", record.slug)
    }

    @Test
    fun `a fully populated watch survives create and reload`() {
        store.create(fullyPopulatedWatch())
        assertEquals(fullyPopulatedWatch(), store.loadCollection().single().watch)
    }

    // ---- backups ---------------------------------------------------------

    @Test
    fun `a backup is named for its watch and the moment it was taken`() {
        val file = writeWatch("seiko-skx007", watchToml("Seiko", "SKX007"))
        store.backupWatchToml("seiko-skx007", file)

        assertEquals(
            listOf("seiko-skx007-20260729T143000.toml"),
            paths.backupsDir.listFiles().orEmpty().map { it.name },
        )
    }

    @Test
    fun `two backups in the same second do not overwrite each other`() {
        val file = writeWatch("seiko-skx007", watchToml("Seiko", "SKX007"))
        store.backupWatchToml("seiko-skx007", file)
        store.backupWatchToml("seiko-skx007", file)
        store.backupWatchToml("seiko-skx007", file)

        assertEquals(
            listOf(
                "seiko-skx007-20260729T143000-2.toml",
                "seiko-skx007-20260729T143000-3.toml",
                "seiko-skx007-20260729T143000.toml",
            ),
            paths.backupsDir.listFiles().orEmpty().map { it.name }.sorted(),
        )
    }

    @Test
    fun `backups are pruned to the newest twenty`() {
        val file = writeWatch("seiko-skx007", watchToml("Seiko", "SKX007"))

        repeat(25) { i ->
            clock = clock.plusMinutes(1)
            file.writeText("brand = \"Seiko\"\nmodel = \"SKX007\"\nrating = $i\n")
            store.backupWatchToml("seiko-skx007", file)
        }

        val remaining = paths.backupsDir.listFiles().orEmpty().map { it.name }.sorted()
        assertEquals(BACKUP_KEEP, remaining.size)
        assertTrue(
            "the oldest five must be the ones gone; kept: $remaining",
            remaining.first() == "seiko-skx007-20260729T143600.toml",
        )
        assertTrue(remaining.last() == "seiko-skx007-20260729T145500.toml")
    }

    @Test
    fun `a deleted watch does not compete with backups for slots`() {
        // backups/deleted/ is a directory, so it is outside the 20-file budget.
        store.create(Watch(brand = "Old", model = "Watch"))
        store.delete(store.loadCollection().single())

        val file = writeWatch("seiko-skx007", watchToml("Seiko", "SKX007"))
        repeat(25) {
            clock = clock.plusMinutes(1)
            store.backupWatchToml("seiko-skx007", file)
        }

        assertEquals(BACKUP_KEEP, paths.backupsDir.listFiles().orEmpty().count { it.isFile })
        assertTrue("the deleted watch must survive the pruning", File(paths.deletedDir, "old-watch").isDirectory)
    }

    @Test
    fun `a wear toggle can skip the snapshot`() {
        // SPEC.md §3: a calendar gesture can touch many watches at once, and
        // backups/ has 20 shared slots. Evictable wear toggles must not crowd
        // out a real snapshot.
        writeWatch("seiko-skx007", watchToml("Seiko", "SKX007"))
        val record = store.loadCollection().single()

        store.save(
            record.copy(watch = record.watch!!.copy(worn = listOf(LocalDate.of(2026, 7, 29)))),
            backup = false,
        )

        assertFalse(paths.backupsDir.exists() && paths.backupsDir.listFiles().orEmpty().isNotEmpty())
        assertEquals(
            listOf(LocalDate.of(2026, 7, 29)),
            store.loadCollection().single().watch!!.worn,
        )
    }

    // ---- deleting --------------------------------------------------------

    @Test
    fun `deleting moves both trees into one restorable folder`() {
        val record = store.create(fullyPopulatedWatch())
        val media = paths.watchMedia(record.slug)
        media.mkdirs()
        File(media, "front.jpg").writeText("photo bytes")
        File(media, "clasp.jpg").writeText("more photo bytes")

        store.delete(record)

        assertFalse("the record is gone from the collection", record.dir.exists())
        assertFalse("and so are its photographs", media.exists())
        assertEquals(emptyList<WatchRecord>(), store.loadCollection())

        val grave = File(paths.deletedDir, record.slug)
        assertTrue(File(grave, SaatPaths.WATCH_FILENAME).exists())
        assertEquals("photo bytes", File(grave, "images/front.jpg").readText())
        assertEquals("more photo bytes", File(grave, "images/clasp.jpg").readText())

        // The result is shaped exactly like a desktop watch folder, which is
        // what makes it readable to a human and zippable without transforming.
        assertEquals(
            listOf(SaatPaths.IMAGES, SaatPaths.WATCH_FILENAME),
            grave.listFiles().orEmpty().map { it.name }.sorted(),
        )
    }

    @Test
    fun `deleting a watch with no photographs still works`() {
        val record = store.create(minimalWatch())
        store.delete(record)

        val grave = File(paths.deletedDir, record.slug)
        assertTrue(File(grave, SaatPaths.WATCH_FILENAME).exists())
        assertFalse("no empty images folder", File(grave, SaatPaths.IMAGES).exists())
    }

    @Test
    fun `deleting also leaves a timestamped copy in backups`() {
        val record = store.create(Watch(brand = "Seiko", model = "SKX007"))
        store.delete(record)

        assertEquals(
            listOf("seiko-skx007-20260729T143000.toml"),
            paths.backupsDir.listFiles().orEmpty().filter { it.isFile }.map { it.name },
        )
    }

    @Test
    fun `deleting the same slug twice does not overwrite the first grave`() {
        val first = store.create(Watch(brand = "Seiko", model = "SKX007"))
        File(first.dir, "marker.txt").writeText("the first one")
        store.delete(first)

        clock = clock.plusHours(1)
        val second = store.create(Watch(brand = "Seiko", model = "SKX007"))
        assertEquals("seiko-skx007", second.slug)
        store.delete(second)

        assertEquals(
            "the first one",
            File(paths.deletedDir, "seiko-skx007/marker.txt").readText(),
        )
        assertTrue(File(paths.deletedDir, "seiko-skx007-20260729T153000").isDirectory)
    }

    @Test
    fun `an imported desktop tree with its own images folder still deletes cleanly`() {
        // A watch that arrived from a ZIP can already have watches/<slug>/images/
        // beside its watch.toml. Both sources then want the same destination, so
        // the move has to merge rather than fail.
        val record = store.create(minimalWatch())
        val nested = File(record.dir, SaatPaths.IMAGES)
        nested.mkdirs()
        File(nested, "from-the-zip.jpg").writeText("zip photo")

        val media = paths.watchMedia(record.slug)
        media.mkdirs()
        File(media, "from-the-phone.jpg").writeText("phone photo")

        store.delete(record)

        val images = File(paths.deletedDir, "${record.slug}/${SaatPaths.IMAGES}")
        assertEquals("zip photo", File(images, "from-the-zip.jpg").readText())
        assertEquals("phone photo", File(images, "from-the-phone.jpg").readText())
        assertFalse(record.dir.exists())
        assertFalse(media.exists())
    }
}
