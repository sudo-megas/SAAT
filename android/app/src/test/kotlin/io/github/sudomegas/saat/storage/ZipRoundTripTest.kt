package io.github.sudomegas.saat.storage

/*
 * THIS IS THE RELEASE GATE FOR v1.0.
 *
 * SPEC-ANDROID 3.2 and AM10's brief both say it in so many words: an app that
 * cannot move its data in and out of the desktop app does not get released. The
 * ZIP is not a backup feature — it is the contract that the phone and the
 * desktop hold the same collection, and the proof that the owner's records are
 * never trapped in either.
 *
 * If this test is failing, the version is not shippable. Do not tag around it,
 * do not @Ignore it, do not weaken an assertion to make it pass. The only
 * correct response to a red run here is to fix the import or the export.
 */

import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/**
 * A desktop-shaped tree imports, exports, and comes back identical.
 *
 * The fixture is built in a temp directory at runtime and deleted afterwards —
 * hard rule 1 applies to test assets exactly as it applies to shipped code, so
 * nothing here is committed to the repository.
 */
class ZipRoundTripTest {

    private lateinit var phone: File
    private lateinit var paths: SaatPaths

    @Before
    fun setUp() {
        phone = tempDir("saat-roundtrip-phone")
        paths = SaatPaths(phone)
    }

    @After
    fun tearDown() {
        phone.deleteRecursively()
    }

    private fun tempDir(prefix: String): File = File.createTempFile(prefix, "").let {
        it.delete()
        it.mkdirs()
        it
    }

    /**
     * A watch.toml with FULL SCHEMA COVERAGE, written the way a desktop user's
     * file actually looks — including a hand-written comment, which is the whole
     * reason byte preservation exists.
     *
     * Not generated from `encodeWatch`: a fixture produced by the code under
     * test would agree with it by construction and prove nothing. This is text.
     */
    private fun desktopToml(brand: String, model: String) = """
        # Bought in Kadıköy, spring 2019. Do not reformat this file.
        brand = "$brand"
        model = "$model"
        reference = "SARB033"
        nickname = "Snowflake"
        serial = "D1234567"
        group = "Seiko Group"
        style = "Dress"
        status = "Owned"
        storage = "Winder slot 2"
        rating = 4
        tags = ["daily", "grail", "İzmir"]
        worn = [2024-01-01, 2024-01-02, 2024-03-15]
        notes = "A daily beater."
        images = ["front.jpg", "back.jpg"]

        [movement]
        caliber = "6R15"
        kind = "Automatic"
        power_reserve_hours = 50.0
        accuracy_min = -15.0
        accuracy_max = 25.0
        accuracy_unit = "sec/day"
        jewels = 23
        bph = 21600
        hacking = true
        handwinding = true
        origin = "Japan"

        [case]
        diameter_mm = 38.0
        lug_to_lug_mm = 46.0
        thickness_mm = 11.5
        lug_width_mm = 20
        material = "Stainless Steel"
        crystal = "Sapphire"
        crown = "Screw-down"
        bezel = "Fixed"
        caseback = "Exhibition"
        water_resistance_m = 100
        weight_g = 145.5

        [dial]
        colour = "Black"
        material = "Sunburst"
        indices = "Applied"
        lume = "LumiBrite"
        complications = ["Date"]

        [[straps]]
        material = "Leather"
        colour = "Brown"
        width_mm = 20
        clasp = "Pin Buckle"
        fitted = true
        image = "strap.jpg"

        [[straps]]
        material = "Steel Bracelet"
        fitted = false

        [acquisition]
        date = 2019-04-01
        price = 450.0
        currency = "TRY"
        target_price = 400.0
        target_date = 2019-01-01
        seller = "Chrono24"
        url = "https://example.invalid/listing"
        condition = "Pre-owned"
        box_and_papers = true
        warranty_until = 2022-04-01

        [maintenance]
        service_interval_years = 5.0
        battery_due = 2027-01-01

        [[log]]
        date = 2023-06-01
        kind = "Service"
        note = "Full service"

        [[log]]
        date = 2024-02-02
        kind = "Regulation"
        note = "+3 s/d"

        [[timing]]
        date = 2024-01-01
        deviation_sec = 3.0
        position = "Dial Up"

        [[timing]]
        date = 2024-02-01
        deviation_sec = -2.0
        position = "Crown Down"

        [[timing]]
        date = 2024-03-01
        deviation_sec = 1.0
        position = "Worn"
    """.trimIndent() + "\n"

    /** Two watches, one photograph each plus a strap photo, in desktop layout. */
    private fun desktopArchive(): Pair<ByteArray, Map<String, ByteArray>> {
        val files = linkedMapOf(
            "watches/seiko-sarb033/watch.toml" to desktopToml("Seiko", "SARB033").toByteArray(),
            "watches/seiko-sarb033/images/front.jpg" to jpeg(seed = 7, size = 4096),
            "watches/seiko-sarb033/images/back.jpg" to jpeg(seed = 11, size = 2048),
            "watches/seiko-sarb033/images/strap.jpg" to jpeg(seed = 13, size = 512),
            // A second watch whose brand is not ASCII, so the UTF-8 path
            // survives both a zip write and a zip read.
            "watches/zublin-vintage/watch.toml" to desktopToml("Züblin", "Vintage").toByteArray(),
            "watches/zublin-vintage/images/front.jpg" to jpeg(seed = 29, size = 8192),
        )

        val buffer = ByteArrayOutputStream()
        ZipOutputStream(buffer).use { zip ->
            files.forEach { (name, bytes) ->
                zip.putNextEntry(ZipEntry(name))
                zip.write(bytes)
                zip.closeEntry()
            }
        }
        return buffer.toByteArray() to files
    }

    private fun jpeg(seed: Int, size: Int) = ByteArray(size) { ((it * seed) % 251).toByte() }

    // --- THE GATE -------------------------------------------------------------

    /**
     * Import a desktop tree, export it again, and assert the archive that comes
     * out is the archive that went in — every `watch.toml` and every photograph
     * byte-identical, not merely semantically equal.
     *
     * Byte-identity of the FILES, not of the archive: zip entry order, directory
     * entries and per-entry timestamps are properties of the container rather
     * than of the collection, and asserting on them would make this test fail
     * for reasons that have nothing to do with the owner's data.
     */
    @Test
    fun `a desktop tree survives import and export byte for byte`() {
        val (archive, original) = desktopArchive()

        val summary = importCollection(paths, open = { ByteArrayInputStream(archive) })
        assertEquals(listOf("seiko-sarb033", "zublin-vintage"), summary.added)
        assertTrue(summary.malformed.isEmpty())
        assertTrue(summary.ignored.isEmpty())

        val exported = ByteArrayOutputStream()
            .also { exportCollection(paths, it) }
            .toByteArray()
            .unzip()

        assertEquals(
            "the exported archive holds exactly the entries that arrived",
            original.keys,
            exported.keys,
        )
        original.forEach { (name, bytes) ->
            assertArrayEquals("$name changed on the way through", bytes, exported.getValue(name))
        }
    }

    /**
     * The semantic half: every field the schema defines arrives, with its type,
     * and is still there after the round trip.
     *
     * Byte-identity alone would pass even if the app could not read a single
     * field of what it was faithfully copying — a very thorough way of storing
     * an opaque blob. This asserts the collection was actually understood.
     */
    @Test
    fun `every field of a full record is readable after the round trip`() {
        val (archive, _) = desktopArchive()
        importCollection(paths, open = { ByteArrayInputStream(archive) })

        val record = WatchStore(paths).loadCollection().first { it.slug == "seiko-sarb033" }
        val watch = requireNotNull(record.watch) { "the imported watch did not parse: ${record.loadError}" }

        assertEquals("Seiko", watch.brand)
        assertEquals("SARB033", watch.model)
        assertEquals("Snowflake", watch.nickname)
        assertEquals(listOf("daily", "grail", "İzmir"), watch.tags)
        assertEquals(4, watch.rating)
        assertEquals(3, watch.worn.size)
        assertEquals("6R15", watch.movement.caliber)
        assertEquals(21600, watch.movement.bph)
        assertEquals(20, watch.case.lugWidthMm)
        assertEquals(100, watch.case.waterResistanceM)
        assertEquals(2, watch.straps.size)
        assertEquals(1, watch.straps.count { it.fitted })
        assertEquals(2, watch.log.size)
        assertEquals(3, watch.timing.size)
        assertEquals(5.0, watch.maintenance.serviceIntervalYears!!, 0.0001)
        assertEquals("A daily beater.", watch.notes)
        assertEquals(listOf("front.jpg", "back.jpg"), watch.images)
    }

    /**
     * The hand-written comment is the reason byte preservation is a rule at all.
     * A round trip that silently reformatted the file would still pass a
     * field-by-field comparison and would still have destroyed something the
     * owner wrote.
     */
    @Test
    fun `a hand-written comment survives the whole journey`() {
        val (archive, _) = desktopArchive()
        importCollection(paths, open = { ByteArrayInputStream(archive) })

        val onDisk = paths.watchToml("seiko-sarb033").readText()

        assertTrue(
            "the comment is gone — something re-serialised the file",
            onDisk.startsWith("# Bought in Kadıköy, spring 2019."),
        )
    }

    /**
     * The invariant the re-root depends on: `images` holds bare filenames.
     * SPEC-ANDROID 3 says it "must continue to", and this is where that stops
     * being a comment and becomes a build failure.
     */
    @Test
    fun `imported records hold bare image filenames, never paths`() {
        val (archive, _) = desktopArchive()
        importCollection(paths, open = { ByteArrayInputStream(archive) })

        val watches = WatchStore(paths).loadCollection().mapNotNull { it.watch }

        assertEquals(emptyList<String>(), assertImagesAreBareFilenames(watches))
    }

    /**
     * The other direction, which is what the owner will actually do second:
     * export from the phone and hand the archive back to it. Nothing is
     * duplicated, because every slug is already here.
     */
    @Test
    fun `re-importing our own export adds nothing and changes nothing`() {
        val (archive, _) = desktopArchive()
        importCollection(paths, open = { ByteArrayInputStream(archive) })

        val before = snapshot()
        val exported = ByteArrayOutputStream().also { exportCollection(paths, it) }.toByteArray()

        val summary = importCollection(paths, open = { ByteArrayInputStream(exported) })

        assertTrue("nothing new should be added", summary.added.isEmpty())
        assertEquals(listOf("seiko-sarb033", "zublin-vintage"), summary.skipped)
        assertEquals("the collection was modified by a no-op import", before, snapshot())
    }

    /** Every file under the phone's root, by path, with its bytes. */
    private fun snapshot(): Map<String, String> = phone.walkTopDown()
        .filter { it.isFile }
        .associate { it.relativeTo(phone).path to it.readBytes().joinToString(",") }
}
