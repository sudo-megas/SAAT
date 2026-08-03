package io.github.sudomegas.saat.devtools

import io.github.sudomegas.saat.storage.SaatPaths
import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.WatchRepository
import io.github.sudomegas.saat.storage.WatchStore
import io.github.sudomegas.saat.ui.form.ACCURACY_UNITS
import io.github.sudomegas.saat.ui.form.BEZELS
import io.github.sudomegas.saat.ui.form.CASEBACKS
import io.github.sudomegas.saat.ui.form.CASE_MATERIALS
import io.github.sudomegas.saat.ui.form.CLASPS
import io.github.sudomegas.saat.ui.form.COMPLICATIONS
import io.github.sudomegas.saat.ui.form.CONDITIONS
import io.github.sudomegas.saat.ui.form.CROWNS
import io.github.sudomegas.saat.ui.form.CRYSTALS
import io.github.sudomegas.saat.ui.form.GROUPS
import io.github.sudomegas.saat.ui.form.INDICES
import io.github.sudomegas.saat.ui.form.LOG_KINDS
import io.github.sudomegas.saat.ui.form.MOVEMENT_KINDS
import io.github.sudomegas.saat.ui.form.STATUSES
import io.github.sudomegas.saat.ui.form.STRAP_MATERIALS
import io.github.sudomegas.saat.ui.form.STYLES
import io.github.sudomegas.saat.ui.form.TIMING_POSITIONS
import java.time.LocalDate
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

/**
 * The sanctioned debug fixture, and the properties AM3 relies on it having.
 *
 * This test lives in `src/test`, which compiles against the DEBUG variant — so
 * the fact that it compiles at all is itself a guard: if the generator is ever
 * moved out of `src/debug`, or renamed, this file stops building. The
 * complementary claim, that none of it reaches a release build, is not testable
 * from here at all (AGP does not create a release unit-test variant) and is
 * asserted by `verifyReleaseDemoFixturePolicy` instead.
 *
 * Everything is built in a temp directory and deleted afterwards — hard rule 1.
 */
class DemoWatchesTest {

    @get:Rule
    val temp = TemporaryFolder()

    private val paths get() = SaatPaths(temp.root)

    private fun repository() = WatchRepository(WatchStore(paths), Dispatchers.Unconfined)

    private val today = LocalDate.of(2026, 3, 14)

    @Test
    fun `the marker the release check looks for is the brand both watches carry`() {
        // buildSrc's DemoFixtureScanner searches compiled classes for this exact
        // string. If the brand is renamed and the scanner is not, the release
        // check keeps passing while proving nothing — so pin them together.
        assertEquals("SAAT Demo", DemoWatches.DEMO_BRAND)
        assertEquals(DemoWatches.DEMO_BRAND, DemoWatches.mechanical(today).brand)
        assertEquals(DemoWatches.DEMO_BRAND, DemoWatches.quartz().brand)
    }

    @Test
    fun `neither demo watch has a photograph`() {
        // The whole point of the pair: with no images, both exercise the grid's
        // placeholder tile, which is the thing that cannot otherwise be seen
        // until AM5 can import a picture.
        assertEquals(emptyList<String>(), DemoWatches.mechanical(today).images)
        assertEquals(emptyList<String>(), DemoWatches.quartz().images)
        assertTrue(DemoWatches.mechanical(today).straps.all { it.image == null })
    }

    @Test
    fun `the mechanical watch fills the fields the later milestones read`() {
        val watch = DemoWatches.mechanical(today)

        assertEquals("Automatic", watch.movement.kind)
        // Both measurements set, so its tile shows real numbers.
        assertNotNull(watch.case.diameterMm)
        assertNotNull(watch.case.lugWidthMm)
        // Exactly one fitted strap — the invariant AM5's form enforces.
        assertEquals(1, watch.straps.count { it.fitted })
        assertTrue(watch.straps.size > 1)
        // A Service entry AND an interval: nextServiceDue() needs both or it
        // stays silent, and AM4's maintenance line would have nothing to show.
        assertTrue(watch.log.any { it.kind == "Service" })
        assertNotNull(watch.maintenance.serviceIntervalYears)
        // A consecutive run, so longestStreak() is more than 1.
        assertTrue(watch.worn.size >= 5)
        // AM9 draws a sparkline at three readings.
        assertTrue(watch.timing.size >= 3)
    }

    @Test
    fun `the quartz watch is bare enough to exercise the empty tile`() {
        val watch = DemoWatches.quartz()

        assertEquals("Quartz", watch.movement.kind)
        // No dimensions at all: the tile must render two em-dashes and still
        // look deliberate.
        assertNull(watch.case.diameterMm)
        assertNull(watch.case.lugWidthMm)
        // Never worn, so it sorts first under "Least worn".
        assertEquals(emptyList<LocalDate>(), watch.worn)
    }

    @Test
    fun `generate writes exactly two watches through the repository`() = runBlocking {
        val repository = repository()
        repository.load()

        DemoWatches.generate(repository, today)

        val brands = repository.state.value.watches.mapNotNull { it.watch?.brand }
        assertEquals(listOf(DemoWatches.DEMO_BRAND, DemoWatches.DEMO_BRAND), brands)
        // Written through create(), so the real slug and atomic-write paths ran.
        assertTrue(paths.watchesDir.listFiles()!!.size == 2)
    }

    @Test
    fun `clear removes the generated watches and leaves a real one alone`() = runBlocking {
        val repository = repository()
        repository.load()
        repository.create(Watch(brand = "Seiko", model = "SKX007"))
        DemoWatches.generate(repository, today)
        assertEquals(3, repository.state.value.watches.size)

        val removed = DemoWatches.clear(repository)

        assertEquals(2, removed)
        val remaining = repository.state.value.watches.mapNotNull { it.watch }
        assertEquals(listOf("Seiko"), remaining.map { it.brand })
    }

    @Test
    fun `clear moves the demo watches to the grave rather than erasing them`() = runBlocking {
        val repository = repository()
        repository.load()
        DemoWatches.generate(repository, today)

        DemoWatches.clear(repository)

        // The repository's own delete() moves a watch to backups/deleted/. A
        // debug convenience has no business inventing a harder-deleting path.
        assertTrue(paths.deletedDir.exists())
        assertEquals(2, paths.deletedDir.listFiles()!!.size)
    }

    /**
     * Every `enum*` value the fixture writes is one the schema actually lists.
     *
     * It wrote three that were not: `Stainless steel` for the case (the schema
     * says `Stainless Steel`), `Steel` for a strap (`Steel Bracelet`) and `Pin
     * buckle` for its clasp (`Pin Buckle`). Nothing broke — an unrecognised
     * value is legal, because SPEC.md §4 promises the owner can type a word
     * nobody anticipated, and it is shown exactly as written.
     *
     * Which is precisely why this needed a test. The fixture is not the owner:
     * it is the app demonstrating its own schema, and a value off by one letter
     * of case is indistinguishable from a deliberate free-text entry. It simply
     * never acquires a Turkish label, never matches the form's dropdown, and
     * never lines up with the desktop's — all silently, in the two watches every
     * new owner is told to generate first.
     */
    @Test
    fun `the fixture writes only enum values the schema knows`() {
        val watches = listOf(DemoWatches.mechanical(today), DemoWatches.quartz())

        val offenders = watches.flatMap { watch ->
            buildList {
                add(Triple("style", watch.style, STYLES))
                add(Triple("movement.kind", watch.movement.kind, MOVEMENT_KINDS))
                add(Triple("case.material", watch.case.material, CASE_MATERIALS))
                add(Triple("case.crystal", watch.case.crystal, CRYSTALS))
                add(Triple("dial.indices", watch.dial.indices, INDICES))
                add(Triple("acquisition.condition", watch.acquisition.condition, CONDITIONS))
                add(Triple("status", watch.status, STATUSES))
                add(Triple("group", watch.group, GROUPS))
                add(Triple("case.crown", watch.case.crown, CROWNS))
                add(Triple("case.bezel", watch.case.bezel, BEZELS))
                add(Triple("case.caseback", watch.case.caseback, CASEBACKS))
                add(Triple("movement.accuracyUnit", watch.movement.accuracyUnit, ACCURACY_UNITS))
                watch.dial.complications.forEach {
                    add(Triple("dial.complications", it, COMPLICATIONS))
                }
                watch.straps.forEach {
                    add(Triple("strap.material", it.material, STRAP_MATERIALS))
                    add(Triple("strap.clasp", it.clasp, CLASPS))
                }
                watch.log.forEach { add(Triple("log.kind", it.kind, LOG_KINDS)) }
                watch.timing.forEach {
                    add(Triple("timing.position", it.position, TIMING_POSITIONS))
                }
            }
        }.filter { (_, value, choices) ->
            !value.isNullOrBlank() && choices.none { it.value == value }
        }.map { (field, value, _) -> "$field = \"$value\"" }

        assertEquals(
            "the demo fixture writes values the schema does not list:\n" +
                offenders.joinToString("\n"),
            emptyList<String>(),
            offenders,
        )
    }
}
