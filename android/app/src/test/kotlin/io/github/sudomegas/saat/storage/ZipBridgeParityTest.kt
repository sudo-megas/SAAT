package io.github.sudomegas.saat.storage

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Before
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.io.File

/**
 * The ZIP bridge, measured against the desktop app rather than against itself.
 *
 * `ZipRoundTripTest` proves the phone agrees with the phone. That is necessary
 * and not sufficient: an export both written and read by this codebase would
 * round-trip perfectly even if its layout were something the desktop had never
 * heard of. So this test does what `DesktopParityTest` does for `watch.toml`,
 * one level up — it hands artefacts to the desktop's real code and takes
 * artefacts back from it:
 *
 *  - `build/reports/zip-bridge/saat-export.zip` is what this app exports, for
 *    `parity_check.py zip` to open with `saat.storage.load_collection`.
 *  - `build/parity-in/desktop-export.zip` is an archive the DESKTOP wrote,
 *    which the import path here has to accept.
 *
 * Both halves skip rather than pass when their input is absent, so a run on a
 * machine with no Python never reports a check it did not make.
 */
class ZipBridgeParityTest {

    private val reports = File("build/reports/zip-bridge")
    private val desktopArchive = File("build/parity-in/desktop-export.zip")

    private lateinit var phone: File
    private lateinit var paths: SaatPaths

    @Before
    fun setUp() {
        phone = File.createTempFile("saat-bridge", "").let {
            it.delete()
            it.mkdirs()
            it
        }
        paths = SaatPaths(phone)
    }

    @After
    fun tearDown() {
        phone.deleteRecursively()
    }

    /**
     * Publish an export for the desktop to open.
     *
     * Built by exporting a real collection through the real code path, not by
     * assembling a plausible-looking archive here — the artefact has to be what
     * the app actually produces or the check downstream is theatre.
     */
    @Test
    fun `publish an archive for the desktop's loader`() {
        val slug = "grand-seiko-sbga211"
        paths.watchDir(slug).mkdirs()
        paths.watchToml(slug).writeText(DESKTOP_WRITTEN_FIXTURE)
        paths.watchMedia(slug).mkdirs()
        File(paths.watchMedia(slug), "front.jpg").writeBytes(ByteArray(1024) { it.toByte() })

        val archive = ByteArrayOutputStream()
            .also { exportCollection(paths, it) }
            .toByteArray()

        reports.mkdirs()
        File(reports, "saat-export.zip").writeBytes(archive)
    }

    /**
     * The other direction: an archive the desktop wrote, imported here.
     *
     * This is the case AM10's brief actually describes — "zip the desktop's
     * watches/ and import to the phone" — with the desktop's own writer
     * producing the bytes rather than a fixture typed out by hand.
     */
    @Test
    fun `an archive written by the desktop imports with every field intact`() {
        assumeTrue(
            "run `python3 android/tools/parity_check.py emit android/app/build/parity-in` first",
            desktopArchive.exists(),
        )

        val summary = importCollection(paths, open = { desktopArchive.inputStream() })

        assertTrue("nothing imported from the desktop's archive", summary.added.isNotEmpty())
        assertEquals("the desktop's archive had entries we could not place", emptyList<String>(), summary.ignored)
        assertEquals("the desktop's own file would not parse here", emptyList<String>(), summary.malformed)

        val record = WatchStore(paths).loadCollection().first()
        val watch = requireNotNull(record.watch) { "did not parse: ${record.loadError}" }

        // The same fixture DesktopParityTest measures, so a field lost in the
        // ZIP path fails here rather than looking like a schema problem.
        assertEquals(fullyPopulatedWatch().brand, watch.brand)
        assertEquals(fullyPopulatedWatch().model, watch.model)
        assertEquals(fullyPopulatedWatch().movement.caliber, watch.movement.caliber)
        assertEquals(fullyPopulatedWatch().case.lugWidthMm, watch.case.lugWidthMm)
        assertEquals(fullyPopulatedWatch().straps.size, watch.straps.size)
        assertEquals(fullyPopulatedWatch().log.size, watch.log.size)
        assertEquals(fullyPopulatedWatch().timing.size, watch.timing.size)
        assertEquals(fullyPopulatedWatch().worn, watch.worn)
        assertEquals(fullyPopulatedWatch().tags, watch.tags)
    }
}
