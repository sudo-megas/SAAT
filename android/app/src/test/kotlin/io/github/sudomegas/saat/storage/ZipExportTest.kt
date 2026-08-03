package io.github.sudomegas.saat.storage

import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.io.File
import java.time.LocalDate
import java.util.zip.ZipInputStream

/**
 * Export — AM10a, SPEC-ANDROID 3.2.
 *
 * The fixture tree is built in code in a temp directory and deleted after, per
 * hard rule 1: no test asset is ever committed to this repository.
 */
class ZipExportTest {

    private lateinit var root: File
    private lateinit var paths: SaatPaths

    @Before
    fun setUp() {
        root = File.createTempFile("saat-export", "").let {
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

    private fun watchFolder(slug: String, toml: String = "brand = \"Test\"\n") {
        paths.watchDir(slug).mkdirs()
        paths.watchToml(slug).writeText(toml)
    }

    private fun photo(slug: String, name: String, bytes: ByteArray) {
        paths.watchMedia(slug).mkdirs()
        File(paths.watchMedia(slug), name).writeBytes(bytes)
    }

    private fun export(): Pair<ExportSummary, Map<String, ByteArray>> {
        val buffer = ByteArrayOutputStream()
        val summary = exportCollection(paths, buffer)
        return summary to buffer.toByteArray().unzip()
    }

    // --- the archive's shape ---------------------------------------------------

    /**
     * THE RE-ROOT, which is the whole point of this file. On the phone the
     * photograph lives at `media/<slug>/front.jpg`; in the archive it must be at
     * `watches/<slug>/images/front.jpg`, which is the desktop's layout — so
     * unzipping into the desktop app's folder IS the import on that side.
     */
    @Test
    fun `photographs are re-rooted from media into the watch's images folder`() {
        watchFolder("seiko-sarb033")
        photo("seiko-sarb033", "front.jpg", byteArrayOf(1, 2, 3))

        val (_, entries) = export()

        assertEquals(
            setOf(
                "watches/seiko-sarb033/watch.toml",
                "watches/seiko-sarb033/images/front.jpg",
            ),
            entries.keys,
        )
    }

    @Test
    fun `nothing derived travels`() {
        watchFolder("a")
        File(root, "config.toml").writeText("theme = \"dark\"")
        paths.backupsDir.mkdirs()
        File(paths.backupsDir, "a-20260101T000000.toml").writeText("old")

        val (_, entries) = export()

        assertEquals(setOf("watches/a/watch.toml"), entries.keys)
        assertTrue(entries.keys.none { it.contains("config") || it.contains("backup") })
    }

    // --- byte preservation -----------------------------------------------------

    /**
     * The export must not re-serialise anything. A hand-written comment on a
     * field survives, because the file goes into the archive exactly as it sits
     * on disk — the byte-preservation rule of SPEC-ANDROID 3, which would be
     * pointless if the one operation that leaves the phone rewrote every file.
     */
    @Test
    fun `a hand-written watch toml keeps its exact bytes, comments and all`() {
        val handWritten = """
            # The one I wear to weddings.
            brand   =   "Grand Seiko"
            model = "SBGA211"   # snowflake
        """.trimIndent()
        watchFolder("gs", toml = handWritten)

        val (_, entries) = export()

        assertArrayEquals(
            handWritten.toByteArray(),
            entries.getValue("watches/gs/watch.toml"),
        )
    }

    @Test
    fun `photograph bytes are copied untouched`() {
        val jpeg = ByteArray(5000) { (it % 251).toByte() }
        watchFolder("a")
        photo("a", "big.jpg", jpeg)

        val (_, entries) = export()

        assertArrayEquals(jpeg, entries.getValue("watches/a/images/big.jpg"))
    }

    // --- the skip rules --------------------------------------------------------

    @Test
    fun `underscore and dot folders never reach the archive`() {
        watchFolder("real")
        watchFolder("_scratch")
        watchFolder(".hidden")

        val (summary, entries) = export()

        assertEquals(1, summary.watches)
        assertEquals(setOf("watches/real/watch.toml"), entries.keys)
    }

    @Test
    fun `a hidden photograph is left behind too`() {
        watchFolder("a")
        photo("a", "front.jpg", byteArrayOf(1))
        photo("a", ".thumbnail.jpg", byteArrayOf(2))

        val (_, entries) = export()

        assertFalse(entries.keys.any { it.contains(".thumbnail") })
    }

    /**
     * A folder with no `watch.toml` is not silently dropped — hard rule 6. It
     * does not travel, because an entry with no record is not clean data, but
     * it is named in the summary so the owner hears about it.
     */
    @Test
    fun `a folder with no watch toml is skipped by name, not in silence`() {
        watchFolder("good")
        paths.watchDir("empty").mkdirs()

        val (summary, entries) = export()

        assertEquals(1, summary.watches)
        assertEquals(listOf("empty"), summary.skipped)
        assertEquals(setOf("watches/good/watch.toml"), entries.keys)
    }

    /** A photograph belonging to no record is not part of the collection. */
    @Test
    fun `orphan media with no watch folder does not travel`() {
        watchFolder("a")
        photo("ghost", "front.jpg", byteArrayOf(9))

        val (_, entries) = export()

        assertTrue(entries.keys.none { it.contains("ghost") })
    }

    // --- summary and progress --------------------------------------------------

    @Test
    fun `the summary counts watches and photographs separately`() {
        watchFolder("a")
        watchFolder("b")
        photo("a", "1.jpg", byteArrayOf(1))
        photo("a", "2.jpg", byteArrayOf(2))
        photo("b", "1.jpg", byteArrayOf(3))

        val (summary, _) = export()

        assertEquals(2, summary.watches)
        assertEquals(3, summary.images)
    }

    @Test
    fun `progress runs from one to the total and the total never moves`() {
        watchFolder("a")
        watchFolder("b")
        photo("a", "1.jpg", byteArrayOf(1))

        val seen = mutableListOf<Pair<Int, Int>>()
        exportCollection(paths, ByteArrayOutputStream()) { done, total -> seen += done to total }

        // Two watch.toml files and one photograph.
        assertEquals(listOf(1 to 3, 2 to 3, 3 to 3), seen)
    }

    @Test
    fun `an empty collection produces a valid empty archive`() {
        paths.watchesDir.mkdirs()

        val (summary, entries) = export()

        assertEquals(0, summary.watches)
        assertTrue(entries.isEmpty())
    }

    /** No `watches/` at all — a first launch — is not an error either. */
    @Test
    fun `a collection that was never created exports nothing without throwing`() {
        val (summary, entries) = export()

        assertEquals(0, summary.watches)
        assertTrue(entries.isEmpty())
    }

    // --- ordering and naming ---------------------------------------------------

    @Test
    fun `entries are laid down in a stable order`() {
        watchFolder("c")
        watchFolder("a")
        watchFolder("b")

        val (_, entries) = export()

        assertEquals(
            listOf("watches/a/watch.toml", "watches/b/watch.toml", "watches/c/watch.toml"),
            entries.keys.toList(),
        )
    }

    @Test
    fun `the filename is the date, ISO, as the spec writes it`() {
        assertEquals(
            "saat-export-2026-08-03.zip",
            exportFilename(LocalDate.of(2026, 8, 3)),
        )
    }

    // --- the invariant the re-root depends on -----------------------------------

    @Test
    fun `bare filenames pass the images invariant and paths are caught`() {
        assertTrue(
            assertImagesAreBareFilenames(
                listOf(minimalWatch().copy(images = listOf("front.jpg", "back.jpg"))),
            ).isEmpty(),
        )
        assertEquals(
            listOf("images/front.jpg"),
            assertImagesAreBareFilenames(
                listOf(minimalWatch().copy(images = listOf("images/front.jpg"))),
            ),
        )
    }
}

/**
 * The archive, read back as a map of entry path to bytes.
 *
 * A `LinkedHashMap` so the tests can assert the ORDER entries were written in,
 * not only which of them are present.
 */
internal fun ByteArray.unzip(): Map<String, ByteArray> {
    val entries = LinkedHashMap<String, ByteArray>()
    ZipInputStream(inputStream()).use { zip ->
        while (true) {
            val entry = zip.nextEntry ?: break
            if (!entry.isDirectory) entries[entry.name] = zip.readBytes()
            zip.closeEntry()
        }
    }
    return entries
}
