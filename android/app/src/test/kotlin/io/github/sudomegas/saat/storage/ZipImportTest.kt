package io.github.sudomegas.saat.storage

import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/**
 * Import — AM10b, SPEC-ANDROID 3.2.
 *
 * The security cases are the ones worth writing first: an archive arrives from
 * outside the app, and "reject before touching disk" is only a claim until
 * something asserts that a refused archive left the collection exactly as it
 * was.
 */
class ZipImportTest {

    private lateinit var root: File
    private lateinit var paths: SaatPaths

    @Before
    fun setUp() {
        root = File.createTempFile("saat-import", "").let {
            it.delete()
            it.mkdirs()
            it
        }
        paths = SaatPaths(root)
    }

    @After
    fun tearDown() {
        root.deleteRecursively()
    }

    private val validToml = "brand = \"Seiko\"\nmodel = \"SARB033\"\n"

    private fun archive(vararg entries: Pair<String, ByteArray>): ByteArray {
        val buffer = ByteArrayOutputStream()
        ZipOutputStream(buffer).use { zip ->
            entries.forEach { (name, bytes) ->
                zip.putNextEntry(ZipEntry(name))
                zip.write(bytes)
                zip.closeEntry()
            }
        }
        return buffer.toByteArray()
    }

    // `open` named, because the trailing-lambda position belongs to onProgress.
    private fun import(bytes: ByteArray) =
        importCollection(paths, open = { ByteArrayInputStream(bytes) })

    private fun existing(slug: String, toml: String = "brand = \"Mine\"\n") {
        paths.watchDir(slug).mkdirs()
        paths.watchToml(slug).writeText(toml)
    }

    // --- both archive roots ----------------------------------------------------

    @Test
    fun `an archive rooted at watches is accepted`() {
        val summary = import(
            archive("watches/seiko-sarb033/watch.toml" to validToml.toByteArray()),
        )

        assertEquals(listOf("seiko-sarb033"), summary.added)
        assertTrue(paths.watchToml("seiko-sarb033").isFile)
    }

    @Test
    fun `an archive rooted at slug level is accepted too`() {
        val summary = import(archive("seiko-sarb033/watch.toml" to validToml.toByteArray()))

        assertEquals(listOf("seiko-sarb033"), summary.added)
    }

    @Test
    fun `photographs land in the media tree, not inside the watch folder`() {
        val jpeg = byteArrayOf(1, 2, 3, 4)
        import(
            archive(
                "watches/a/watch.toml" to validToml.toByteArray(),
                "watches/a/images/front.jpg" to jpeg,
            ),
        )

        // The archive keeps the desktop's shape; the phone splits the trees.
        assertArrayEquals(jpeg, File(paths.watchMedia("a"), "front.jpg").readBytes())
        assertFalse(File(paths.watchDir("a"), "images").exists())
    }

    // --- the refusals ----------------------------------------------------------

    /**
     * The refusal must be TOTAL and must happen before anything is written. A
     * `../` is not a mistake anybody makes by accident, and the honest response
     * to one bad entry is to distrust the file it came in.
     */
    @Test
    fun `path traversal refuses the whole archive and writes nothing`() {
        val bytes = archive(
            "watches/good/watch.toml" to validToml.toByteArray(),
            "watches/../../evil.toml" to "gotcha".toByteArray(),
        )

        assertThrows(UnsafeArchiveException::class.java) { import(bytes) }

        // The good watch did not land either — the survey ran first.
        assertFalse(paths.watchDir("good").exists())
        assertFalse(File(root.parentFile, "evil.toml").exists())
    }

    @Test
    fun `an absolute path is refused`() {
        assertThrows(UnsafeArchiveException::class.java) {
            import(archive("/etc/passwd" to "root".toByteArray()))
        }
    }

    @Test
    fun `a windows drive letter is absolute too`() {
        assertThrows(UnsafeArchiveException::class.java) {
            import(archive("C:\\Windows\\system32\\evil.dll" to "x".toByteArray()))
        }
    }

    @Test
    fun `a backslash separated traversal is caught as well`() {
        assertThrows(UnsafeArchiveException::class.java) {
            import(archive("watches\\..\\..\\evil.toml" to "x".toByteArray()))
        }
    }

    /**
     * A symlink entry cannot escape because extraction never creates a link:
     * every file is written through a path this code builds, so the entry lands
     * as an ordinary file holding the text of its target. Asserted rather than
     * assumed, since the platform's zip API gives no way to see the symlink bit.
     */
    @Test
    fun `a symlink-shaped entry becomes an ordinary file inside the collection`() {
        import(
            archive(
                "watches/a/watch.toml" to validToml.toByteArray(),
                "watches/a/images/link.jpg" to "../../../../etc/passwd".toByteArray(),
            ),
        )

        val written = File(paths.watchMedia("a"), "link.jpg")
        assertTrue(written.isFile)
        // A regular file holding text, not a link to anything.
        assertEquals("../../../../etc/passwd", written.readText())
    }

    // --- skip existing ---------------------------------------------------------

    /**
     * The owner's decision, recorded in SPEC-ANDROID 3.2: only NEW watches are
     * added. Not merged, not overwritten — anything else would put the archive's
     * opinion of a watch above the one being edited on the phone.
     */
    @Test
    fun `an existing slug is skipped and its file is untouched`() {
        existing("seiko-sarb033", toml = "brand = \"Mine\"\nmodel = \"Edited here\"\n")

        val summary = import(
            archive("watches/seiko-sarb033/watch.toml" to validToml.toByteArray()),
        )

        assertEquals(listOf("seiko-sarb033"), summary.skipped)
        assertTrue(summary.added.isEmpty())
        assertEquals(
            "brand = \"Mine\"\nmodel = \"Edited here\"\n",
            paths.watchToml("seiko-sarb033").readText(),
        )
    }

    @Test
    fun `a skipped watch's photographs are not imported either`() {
        existing("a")

        import(
            archive(
                "watches/a/watch.toml" to validToml.toByteArray(),
                "watches/a/images/front.jpg" to byteArrayOf(9),
            ),
        )

        assertFalse(File(paths.watchMedia("a"), "front.jpg").exists())
    }

    @Test
    fun `new watches still arrive alongside skipped ones`() {
        existing("old")

        val summary = import(
            archive(
                "watches/old/watch.toml" to validToml.toByteArray(),
                "watches/new/watch.toml" to validToml.toByteArray(),
            ),
        )

        assertEquals(listOf("new"), summary.added)
        assertEquals(listOf("old"), summary.skipped)
    }

    // --- byte preservation -----------------------------------------------------

    /**
     * Parsed to decide, written unchanged. A comment written on the desktop is
     * still there after the import, which is why parsing and writing are
     * separate steps rather than a decode-then-encode.
     */
    @Test
    fun `an imported watch toml keeps its original bytes`() {
        val handWritten = "# bought in Kadıköy\nbrand = \"Seiko\"  # not Grand\nmodel = \"SKX007\"\n"

        import(archive("watches/skx/watch.toml" to handWritten.toByteArray()))

        assertArrayEquals(handWritten.toByteArray(), paths.watchToml("skx").readBytes())
    }

    // --- malformed and ignored -------------------------------------------------

    /**
     * "Reported by name and skipped without aborting the rest of the import" —
     * a broken watch in an archive of forty must not cost the other thirty-nine.
     */
    @Test
    fun `a malformed watch is named and the rest still import`() {
        val summary = import(
            archive(
                "watches/good/watch.toml" to validToml.toByteArray(),
                "watches/broken/watch.toml" to "this is not [ toml".toByteArray(),
            ),
        )

        assertEquals(listOf("good"), summary.added)
        assertEquals(listOf("broken"), summary.malformed)
        assertFalse(paths.watchDir("broken").exists())
    }

    @Test
    fun `entries that are not part of a collection are named, not guessed at`() {
        val summary = import(
            archive(
                "watches/a/watch.toml" to validToml.toByteArray(),
                "README.txt" to "hello".toByteArray(),
                "config.toml" to "theme = \"dark\"".toByteArray(),
            ),
        )

        assertEquals(listOf("a"), summary.added)
        assertEquals(listOf("README.txt", "config.toml"), summary.ignored)
        assertFalse(File(root, "config.toml").exists())
    }

    @Test
    fun `underscore and dot folders in an archive are not imported`() {
        val summary = import(
            archive(
                "watches/_scratch/watch.toml" to validToml.toByteArray(),
                "watches/a/images/.thumb.jpg" to byteArrayOf(1),
                "watches/a/watch.toml" to validToml.toByteArray(),
            ),
        )

        assertEquals(listOf("a"), summary.added)
        assertFalse(paths.watchDir("_scratch").exists())
        assertFalse(File(paths.watchMedia("a"), ".thumb.jpg").exists())
    }

    @Test
    fun `a photograph whose watch never arrived is not written`() {
        import(archive("watches/ghost/images/front.jpg" to byteArrayOf(1)))

        assertFalse(paths.watchMedia("ghost").exists())
    }

    @Test
    fun `an empty archive imports nothing and does not throw`() {
        val summary = import(archive())

        assertTrue(summary.added.isEmpty())
        assertTrue(summary.skipped.isEmpty())
    }

    // --- directory entries, which are never content ----------------------------

    /**
     * SILENT DATA LOSS BEFORE THIS WAS FIXED. An archive holding both
     * `a/images/f.jpg` and the directory entry `a/images/f.jpg/` wrote the real
     * image and then truncated it to zero bytes with the directory entry —
     * while still reporting the watch as imported.
     */
    @Test
    fun `a directory entry never truncates a real file of the same name`() {
        val jpeg = byteArrayOf(1, 2, 3, 4, 5, 6, 7, 8)

        import(
            archive(
                "watches/a/watch.toml" to validToml.toByteArray(),
                "watches/a/images/f.jpg" to jpeg,
                "watches/a/images/f.jpg/" to ByteArray(0),
            ),
        )

        assertArrayEquals(jpeg, File(paths.watchMedia("a"), "f.jpg").readBytes())
    }

    @Test
    fun `a directory entry named like a watch toml does not mark the watch malformed`() {
        val summary = import(
            archive(
                "watches/a/watch.toml" to validToml.toByteArray(),
                "watches/a/watch.toml/" to ByteArray(0),
            ),
        )

        assertEquals(listOf("a"), summary.added)
        assertTrue("a good watch was reported malformed", summary.malformed.isEmpty())
    }

    // --- slugs an archive must not be allowed to name ---------------------------

    /**
     * THE COLLISION THE ZIP CONTRACT EXISTS TO AVOID CREATING. Import is the
     * only writer of `watches/<slug>` that does not go through `slugify`, and
     * `uniqueSlug` detects collisions case-insensitively precisely because two
     * folders differing only in case are the same folder on a case-insensitive
     * filesystem. A one-character case change used to defeat skip-existing.
     */
    @Test
    fun `an existing slug is skipped whatever case the archive spells it in`() {
        existing("seiko-skx007")

        val summary = import(
            archive("watches/Seiko-SKX007/watch.toml" to validToml.toByteArray()),
        )

        assertEquals(listOf("Seiko-SKX007"), summary.skipped)
        assertTrue(summary.added.isEmpty())
        assertEquals(
            "a second folder differing only in case was created",
            1,
            paths.watchesDir.listFiles().orEmpty().size,
        )
    }

    @Test
    fun `an archive cannot collide with itself by case either`() {
        val summary = import(
            archive(
                "watches/Seiko/watch.toml" to validToml.toByteArray(),
                "watches/seiko/watch.toml" to validToml.toByteArray(),
            ),
        )

        assertEquals(1, summary.added.size)
        assertEquals(1, summary.skipped.size)
    }

    /**
     * A slug longer than the filesystem accepts used to be discovered by the
     * write throwing — after earlier watches had already landed, leaving a
     * partial import reported as a total failure.
     */
    @Test
    fun `an over-long slug is ignored rather than failing mid-import`() {
        val summary = import(
            archive(
                "watches/good/watch.toml" to validToml.toByteArray(),
                "watches/${"s".repeat(300)}/watch.toml" to validToml.toByteArray(),
            ),
        )

        assertEquals(listOf("good"), summary.added)
        assertEquals(1, summary.ignored.size)
        assertTrue(paths.watchToml("good").isFile)
    }

    @Test
    fun `a slug carrying a NUL is ignored`() {
        val summary = import(
            archive(
                "watches/good/watch.toml" to validToml.toByteArray(),
                "watches/a\u0000b/watch.toml" to validToml.toByteArray(),
            ),
        )

        assertEquals(listOf("good"), summary.added)
        assertEquals(1, summary.ignored.size)
    }

    /**
     * A plain FILE sitting at `watches/<slug>` counts as existing. Filtering on
     * isDirectory meant the slug was accepted and then failed at mkdirs, again
     * after other watches had been written.
     */
    @Test
    fun `a plain file where a watch folder would go counts as existing`() {
        paths.watchesDir.mkdirs()
        File(paths.watchesDir, "a").writeText("not a folder")

        val summary = import(archive("watches/a/watch.toml" to validToml.toByteArray()))

        assertEquals(listOf("a"), summary.skipped)
        assertTrue(summary.added.isEmpty())
    }

    // --- resource limits --------------------------------------------------------

    /**
     * An entry claiming to be a watch.toml can claim any size, and every
     * accepted one is held in memory until the write loop — so the peak is
     * their sum. A real watch.toml is a couple of kilobytes.
     */
    @Test
    fun `an absurdly large watch toml is rejected rather than read into memory`() {
        val huge = ByteArray(5 * 1024 * 1024) { '#'.code.toByte() }

        val summary = import(
            archive(
                "watches/good/watch.toml" to validToml.toByteArray(),
                "watches/bomb/watch.toml" to huge,
            ),
        )

        assertEquals(listOf("good"), summary.added)
        assertEquals(listOf("bomb"), summary.malformed)
    }

    // --- duplicates within one archive -----------------------------------------

    /**
     * Both roots are accepted, so one archive can carry the same slug twice.
     * First wins and the second is NAMED — last-wins in silence would let a
     * decoy entry replace the real one with nothing said.
     */
    @Test
    fun `the same slug twice in one archive keeps the first and reports the second`() {
        val first = "brand = \"First\"\nmodel = \"One\"\n"
        val second = "brand = \"Second\"\nmodel = \"Two\"\n"

        val summary = import(
            archive(
                "watches/a/watch.toml" to first.toByteArray(),
                "a/watch.toml" to second.toByteArray(),
            ),
        )

        assertEquals(listOf("a"), summary.added)
        assertEquals(listOf("a/watch.toml"), summary.ignored)
        assertEquals(first, paths.watchToml("a").readText())
    }

    // --- entry mapping ---------------------------------------------------------

    @Test
    fun `both roots map onto the same target`() {
        assertEquals(EntryTarget.Toml("a"), targetOf("watches/a/watch.toml"))
        assertEquals(EntryTarget.Toml("a"), targetOf("a/watch.toml"))
        assertEquals(EntryTarget.Image("a", "f.jpg"), targetOf("watches/a/images/f.jpg"))
        assertEquals(EntryTarget.Image("a", "f.jpg"), targetOf("a/images/f.jpg"))
    }

    @Test
    fun `anything that is not those two shapes maps to nothing`() {
        assertEquals(null, targetOf("watches/a/notes.txt"))
        assertEquals(null, targetOf("watches/a/images/nested/f.jpg"))
        assertEquals(null, targetOf("README.md"))
        assertEquals(null, targetOf("watches/a/watch.toml.bak"))
    }

    /**
     * A watch legitimately slugged `watches` survives the root stripping,
     * because the shape is decided per entry rather than once for the archive.
     */
    @Test
    fun `a watch slugged watches is not mistaken for the archive root`() {
        assertEquals(EntryTarget.Toml("watches"), targetOf("watches/watches/watch.toml"))
    }

    /**
     * The documented limit of the above. In a SLUG-ROOTED archive a watch
     * slugged `watches` is indistinguishable from an archive root with a stray
     * file in it, and is ignored. Asserted so the limitation is a decision
     * rather than a surprise.
     */
    @Test
    fun `a slug-rooted archive cannot express a watch slugged watches`() {
        assertEquals(null, targetOf("watches/watch.toml"))
    }
}
