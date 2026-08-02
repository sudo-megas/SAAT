package io.github.sudomegas.saat.devtools

import io.github.sudomegas.saat.storage.Acquisition
import io.github.sudomegas.saat.storage.Case
import io.github.sudomegas.saat.storage.Dial
import io.github.sudomegas.saat.storage.LogEntry
import io.github.sudomegas.saat.storage.Maintenance
import io.github.sudomegas.saat.storage.Movement
import io.github.sudomegas.saat.storage.Strap
import io.github.sudomegas.saat.storage.TimingEntry
import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.WatchRepository
import java.time.LocalDate

/**
 * The one sanctioned exception to hard rule 1, and the only reason it exists is
 * that the app cannot yet add a watch.
 *
 * SPEC-ANDROID 2 rule 1 forbids seed data, demo watches and sample collections
 * outright — release APKs ship empty, always — and then carves out exactly this:
 * a developer action, present in DEBUG BUILDS ONLY, generating exactly two
 * watches IN CODE at tap time. Nothing here is committed as data, nothing is
 * bundled as an asset, and this whole file lives in `src/debug` so it is absent
 * from the release build rather than merely disabled in it. That distinction is
 * load-bearing: `release { isMinifyEnabled = false }`, so anything guarded by a
 * `BuildConfig.DEBUG` flag would still ship in the release DEX.
 *
 * `verifyReleaseDemoFixturePolicy` asserts the absence on every `check`.
 *
 * The two watches are chosen to exercise opposite ends of the model. The
 * mechanical one fills nearly everything, so AM4's wear stats, timing sparkline
 * and maintenance line all have something to read. The quartz one carries
 * brand, model and movement kind and nothing else — no case dimensions at all,
 * which is what makes the grid's placeholder tile render two em-dashes and prove
 * it still looks deliberate. NEITHER HAS PHOTOGRAPHS, so both exercise the tile.
 *
 * Generation goes through `WatchRepository.create`, not through the filesystem
 * directly, so slug collision handling, atomic writes and backups are the real
 * code paths rather than a second implementation that could drift.
 */
object DemoWatches {

    /**
     * Marks a record as generated. Used to identify what "clear" removes, and
     * as the string the release-absence scanner looks for in compiled classes.
     */
    const val DEMO_BRAND = "SAAT Demo"

    fun mechanical(today: LocalDate): Watch = Watch(
        brand = DEMO_BRAND,
        model = "Field Automatic",
        reference = "SD-3820",
        style = "Field",
        tags = listOf("daily", "demo"),
        rating = 4,
        movement = Movement(
            caliber = "SW200-1",
            kind = "Automatic",
            powerReserveHours = 38.0,
            accuracyMin = -5.0,
            accuracyMax = 8.0,
            accuracyUnit = "sec/day",
            jewels = 26,
            bph = 28800,
            hacking = true,
            handwinding = true,
            origin = "Switzerland",
        ),
        // Both measurements present, so the no-photo tile has something to show.
        case = Case(
            diameterMm = 38.0,
            lugToLugMm = 46.5,
            thicknessMm = 11.2,
            lugWidthMm = 20,
            material = "Stainless steel",
            crystal = "Sapphire",
            waterResistanceM = 100,
            weightG = 78.0,
        ),
        dial = Dial(
            colour = "Black",
            indices = "Applied",
            lume = "Super-LumiNova",
            complications = listOf("Date"),
        ),
        // Exactly one fitted, which is the invariant AM5's form will enforce.
        straps = listOf(
            Strap(material = "Steel", colour = "Brushed", widthMm = 20, fitted = true),
            Strap(material = "Leather", colour = "Brown", widthMm = 20, clasp = "Pin buckle"),
        ),
        acquisition = Acquisition(
            date = today.minusDays(420),
            price = 850.0,
            currency = "TRY",
            condition = "New",
            boxAndPapers = true,
        ),
        // A Service entry plus an interval is what nextServiceDue() needs; without
        // both it stays silent, and AM4's maintenance line would have nothing.
        maintenance = Maintenance(serviceIntervalYears = 5.0),
        log = listOf(
            LogEntry(date = today.minusDays(400), kind = "Note", note = "Arrived."),
            LogEntry(date = today.minusDays(90), kind = LogEntry.KIND_SERVICE, note = "Full service"),
        ),
        // A consecutive run plus scattered days, so longestStreak and
        // timesWornThisYear both return something more interesting than 1.
        worn = buildList {
            repeat(5) { add(today.minusDays(it.toLong())) }
            add(today.minusDays(11))
            add(today.minusDays(24))
            add(today.minusDays(38))
        },
        // Three readings is the threshold at which AM9 draws a sparkline.
        timing = listOf(
            TimingEntry(today.minusDays(60), 3.5, "Dial Up"),
            TimingEntry(today.minusDays(30), 2.0, "Crown Down"),
            TimingEntry(today.minusDays(2), 4.25, "Dial Down"),
        ),
        notes = "Generated by the debug developer action. Not real.",
    )

    /**
     * The other end of the range: what SPEC-ANDROID 5.7 promises must be
     * saveable, plus the movement kind so the card metadata line has one half of
     * its pair. No case dimensions, so the placeholder tile shows two em-dashes.
     * No worn days, so it sorts first under "Least worn".
     */
    fun quartz(): Watch = Watch(
        brand = DEMO_BRAND,
        model = "Quartz Minimal",
        movement = Movement(kind = "Quartz"),
    )

    suspend fun generate(repository: WatchRepository, today: LocalDate = LocalDate.now()) {
        repository.create(mechanical(today))
        repository.create(quartz())
    }

    /**
     * Removes only what this object generated, identified by [DEMO_BRAND].
     *
     * Deletion goes through the repository, which MOVES the record to
     * `backups/deleted/` rather than erasing it. A debug convenience has no
     * business inventing a harder-deleting path than the app's own.
     */
    suspend fun clear(repository: WatchRepository): Int {
        val demo = repository.state.value.records
            .filter { it.watch?.brand == DEMO_BRAND }
            .map { it.slug }
        return demo.count { repository.delete(it) }
    }
}
