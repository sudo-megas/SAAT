package io.github.sudomegas.saat.storage

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

/**
 * Photographs coming in and going out — SPEC-ANDROID 5.7 items 7 to 9.
 *
 * The claim being tested is narrow and load-bearing: THE BYTES ARE COPIED
 * VERBATIM. That is what makes "EXIF orientation honoured" true without this app
 * ever decoding an image — the tag the camera wrote is still there, Coil applies
 * it at decode and so does the desktop's Pillow. Re-encoding to bake in the
 * rotation would be lossy, would change a file the desktop also reads, and would
 * throw away every other tag in the file.
 */
class WatchImagesTest {

    @get:Rule
    val temp = TemporaryFolder()

    private val paths get() = SaatPaths(temp.root)
    private val images get() = WatchImages(paths)

    private fun source(name: String, bytes: ByteArray): File =
        File(temp.newFolder(), name).apply { writeBytes(bytes) }

    private fun importInto(slug: String, file: File, taken: Set<String> = emptySet()) =
        file.inputStream().use { images.import(slug, it, file.name, taken) }

    private fun mediaFile(slug: String, name: String) = File(paths.watchMedia(slug), name)

    // --- the copy ------------------------------------------------------------

    @Test
    fun `an imported photograph is byte-for-byte what was picked`() {
        val original = jpegWithOrientation(6)
        val name = importInto("seiko-skx007", source("IMG_0001.jpg", original))

        assertEquals("IMG_0001.jpg", name)
        assertArrayEquals(original, mediaFile("seiko-skx007", name).readBytes())
    }

    @Test
    fun `the EXIF orientation tag survives the copy intact`() {
        // The whole of "EXIF orientation honoured on copy so no photo lies on
        // its side": the tag is PRESERVED rather than applied. If this app ever
        // starts re-encoding, this is the test that notices.
        val original = jpegWithOrientation(6)
        val name = importInto("seiko-skx007", source("rotated.jpg", original))
        val copied = mediaFile("seiko-skx007", name).readBytes()

        assertTrue("the APP1/Exif marker is gone", copied.containsSequence(EXIF_MARKER))
        assertTrue("the orientation entry is gone", copied.containsSequence(orientationEntry(6)))
        assertArrayEquals(original, copied)
    }

    @Test
    fun `an import lands in media, never in the record's own folder`() {
        // Hard rule 8 and SPEC-ANDROID 3: watches/ holds records, media/ holds
        // photographs, and the split is what makes the Auto Backup rule
        // expressible at all.
        importInto("seiko-skx007", source("front.jpg", jpegWithOrientation(1)))

        assertTrue(mediaFile("seiko-skx007", "front.jpg").exists())
        assertFalse(File(paths.watchDir("seiko-skx007"), "front.jpg").exists())
        assertFalse(File(File(paths.watchDir("seiko-skx007"), "images"), "front.jpg").exists())
    }

    // --- names ---------------------------------------------------------------

    @Test
    fun `a second photograph of the same name is numbered, not overwritten`() {
        val first = jpegWithOrientation(1)
        val second = jpegWithOrientation(8)

        val a = importInto("seiko-skx007", source("IMG_0001.jpg", first))
        val b = importInto("seiko-skx007", source("IMG_0001.jpg", second))

        assertEquals("IMG_0001.jpg", a)
        assertEquals("IMG_0001-2.jpg", b)
        assertArrayEquals(first, mediaFile("seiko-skx007", a).readBytes())
        assertArrayEquals(second, mediaFile("seiko-skx007", b).readBytes())
    }

    @Test
    fun `names already claimed by this same save are avoided too`() {
        // Two photographs picked in one gesture, both called IMG_0001.jpg —
        // which is exactly what a camera roll produces. Neither is on disk yet
        // when the second is named.
        val name = importInto("seiko-skx007", source("IMG_0001.jpg", jpegWithOrientation(1)))
        val next = importInto(
            "seiko-skx007",
            source("IMG_0001.jpg", jpegWithOrientation(1)),
            taken = setOf(name),
        )

        assertEquals("IMG_0001-2.jpg", next)
    }

    @Test
    fun `collisions are detected case-insensitively`() {
        // Front.JPG beside front.jpg is two files on Linux and one on Windows,
        // and the exported ZIP is opened on both.
        importInto("seiko-skx007", source("front.jpg", jpegWithOrientation(1)))
        val second = importInto("seiko-skx007", source("FRONT.JPG", jpegWithOrientation(1)))

        assertEquals("FRONT-2.JPG", second)
    }

    @Test
    fun `a filename keeps the owner's spelling once it is writable`() {
        // Not slugified: mixed case, spaces and accents are all perfectly
        // writable, and a photograph should keep the name its owner recognises.
        // Every expectation below was read off the desktop's own
        // safe_image_filename() rather than reasoned about, because the two have
        // to agree about a name that travels inside the exported ZIP.
        assertEquals("Züblin Front.jpg", safeImageFilename("Züblin Front.jpg"))
        assertEquals("front.jpg", safeImageFilename("fr<>o:n\"t.jpg"))
        assertEquals("image.jpg", safeImageFilename("???.jpg"))
        assertEquals("con-image.jpg", safeImageFilename("con.jpg"))
        assertEquals("archive.tar.gz", safeImageFilename("archive.tar.gz"))
        // A leading-dot name has no stem, so the whole thing is the stem — and
        // stripping leading dots then leaves `gitkeep`. Matching the desktop
        // matters more here than the answer being pretty.
        assertEquals("gitkeep", safeImageFilename(".gitkeep"))
        assertEquals("escape.jpg", safeImageFilename("../../escape.jpg"))
    }

    @Test
    fun `a path in a picked filename cannot escape the media folder`() {
        val name = importInto("seiko-skx007", source("photo.jpg", jpegWithOrientation(1)).let {
            // A provider that answers a display name with separators in it.
            File(it.parentFile, "photo.jpg")
        })
        val escaping = images.import(
            "seiko-skx007",
            jpegWithOrientation(1).inputStream(),
            "../../escape.jpg",
            setOf(name),
        )

        assertFalse(escaping.contains('/'))
        assertTrue(mediaFile("seiko-skx007", escaping).exists())
        assertEquals(paths.watchMedia("seiko-skx007"), mediaFile("seiko-skx007", escaping).parentFile)
    }

    // --- removal -------------------------------------------------------------

    @Test
    fun `a removed photograph moves to the grave rather than being erased`() {
        // SPEC-ANDROID 5.7 item 9, and the same shape a deleted watch takes:
        // backups/deleted/<slug>/images/<name>. A photograph has no second copy
        // anywhere, so "delete" has to mean what it means for a whole watch.
        val original = jpegWithOrientation(3)
        val name = importInto("seiko-skx007", source("front.jpg", original))

        images.delete("seiko-skx007", name)

        assertFalse(mediaFile("seiko-skx007", name).exists())
        val grave = File(File(File(paths.deletedDir, "seiko-skx007"), "images"), name)
        assertTrue(grave.exists())
        assertArrayEquals(original, grave.readBytes())
    }

    @Test
    fun `two photographs of one name never overwrite each other in the grave`() {
        // After a delete this IS the only copy there was, which makes it the one
        // place in the app where overwriting a file is unrecoverable.
        val first = jpegWithOrientation(1)
        val second = jpegWithOrientation(8)

        importInto("seiko-skx007", source("front.jpg", first))
        images.delete("seiko-skx007", "front.jpg")
        importInto("seiko-skx007", source("front.jpg", second))
        images.delete("seiko-skx007", "front.jpg")

        val grave = File(File(paths.deletedDir, "seiko-skx007"), "images")
        assertEquals(setOf("front.jpg", "front-2.jpg"), grave.listFiles().orEmpty().map { it.name }.toSet())
        assertArrayEquals(first, File(grave, "front.jpg").readBytes())
        assertArrayEquals(second, File(grave, "front-2.jpg").readBytes())
    }

    @Test
    fun `removing a photograph that is not there is silent`() {
        images.delete("seiko-skx007", "never-existed.jpg")
    }

    @Test
    fun `existing lists what is actually on disk`() {
        assertEquals(emptyList<String>(), images.existing("seiko-skx007"))

        importInto("seiko-skx007", source("front.jpg", jpegWithOrientation(1)))
        importInto("seiko-skx007", source("back.jpg", jpegWithOrientation(1)))

        assertEquals(setOf("front.jpg", "back.jpg"), images.existing("seiko-skx007").toSet())
    }

    // --- a JPEG, built in code -----------------------------------------------

    /**
     * The smallest thing that is really a JPEG carrying a real EXIF orientation:
     * SOI, an APP1 segment holding a one-entry TIFF IFD, EOI.
     *
     * Built here rather than committed as a fixture — hard rule 1 applies to
     * test assets exactly as it applies to shipped code, and a checked-in photo
     * would be a binary nobody can review.
     */
    private fun jpegWithOrientation(orientation: Int): ByteArray {
        val tiff = byteArrayOf(
            0x4D, 0x4D, // "MM": big-endian
            0x00, 0x2A, // 42, the TIFF magic
            0x00, 0x00, 0x00, 0x08, // first IFD at offset 8
            0x00, 0x01, // one entry
        ) + orientationEntry(orientation) + byteArrayOf(
            0x00, 0x00, 0x00, 0x00, // no next IFD
        )

        val payload = EXIF_MARKER + tiff
        val length = payload.size + 2
        return byteArrayOf(
            0xFF.toByte(), 0xD8.toByte(), // SOI
            0xFF.toByte(), 0xE1.toByte(), // APP1
            (length shr 8).toByte(), (length and 0xFF).toByte(),
        ) + payload + byteArrayOf(0xFF.toByte(), 0xD9.toByte()) // EOI
    }

    /** Tag 0x0112 Orientation, SHORT, count 1, value in the high half-word. */
    private fun orientationEntry(orientation: Int) = byteArrayOf(
        0x01, 0x12,
        0x00, 0x03,
        0x00, 0x00, 0x00, 0x01,
        0x00, orientation.toByte(), 0x00, 0x00,
    )

    private fun ByteArray.containsSequence(needle: ByteArray): Boolean =
        (0..size - needle.size).any { start ->
            needle.indices.all { this[start + it] == needle[it] }
        }

    private companion object {
        /** `Exif\0\0`, the APP1 payload header. */
        val EXIF_MARKER = byteArrayOf(0x45, 0x78, 0x69, 0x66, 0x00, 0x00)
    }
}
