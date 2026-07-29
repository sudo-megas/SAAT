package io.github.sudomegas.saat.storage

import java.time.LocalDate

/**
 * The watch record, field-for-field with the desktop's `saat/models.py`.
 *
 * `docs/schema.md` at the repository root is the contract and SPEC.md §4 lists
 * the fields; this is the Kotlin side of it. The mapping is not taken on trust —
 * `WatchTomlTest` encodes a fully-populated watch and `android/tools/
 * parity_check.py` diffs the resulting key set against
 * `dataclasses.fields(saat.models.Watch)` in CI, so a field that is missing,
 * renamed or misspelled here fails the Android build rather than surfacing as an
 * empty row in AM4.
 *
 * ABSENCE IS A VALUE. Every optional field is nullable and none of them default
 * to `0` or `""` — SPEC-ANDROID 4 renders an absent field as a muted em-dash,
 * which the UI can only do if the model can tell "not filled in" from "filled in
 * as zero". A `0.0` diameter is a claim about the watch; a null is an admission
 * that nobody has measured it.
 *
 * Property names are camelCase because every screen from AM3 onward reads them,
 * while the TOML keys stay snake_case. The two vocabularies meet in exactly one
 * place — `WatchToml.kt` — and nowhere else.
 */
data class Watch(
    // --- identity: flat, at the top level of the file --------------------
    val brand: String,
    val model: String,
    val reference: String? = null,
    val nickname: String? = null,
    val serial: String? = null,
    val group: String? = null,
    val style: String? = null,
    /**
     * The one field with a default rather than a null: the desktop writes
     * `status = "Owned"` on every save and reads it as "Owned" when absent, so
     * matching that is parity rather than a design choice of ours.
     */
    val status: String = STATUS_OWNED,
    val storage: String? = null,
    val rating: Int? = null,
    val tags: List<String> = emptyList(),

    // --- grouped attributes ---------------------------------------------
    val movement: Movement = Movement(),
    val case: Case = Case(),
    val dial: Dial = Dial(),
    val straps: List<Strap> = emptyList(),
    val acquisition: Acquisition = Acquisition(),
    val maintenance: Maintenance = Maintenance(),
    val log: List<LogEntry> = emptyList(),
    val worn: List<LocalDate> = emptyList(),
    val timing: List<TimingEntry> = emptyList(),
    val notes: String? = null,

    /**
     * Not in SPEC.md §4's field tables: the gallery order chosen in the images
     * editor, first entry being the primary photo. Bare filenames, never paths —
     * SPEC-ANDROID 3 depends on that, because it is what lets a watch's
     * photographs live in a separate `media/<slug>/` tree on the phone and still
     * re-root into `watches/<slug>/images/` inside the exported ZIP.
     */
    val images: List<String> = emptyList(),
) {
    companion object {
        const val STATUS_OWNED = "Owned"
    }
}

data class Movement(
    val caliber: String? = null,
    val kind: String? = null,
    val powerReserveHours: Double? = null,
    val batteryLifeYears: Double? = null,
    val accuracyMin: Double? = null,
    val accuracyMax: Double? = null,
    val accuracyUnit: String? = null,
    val jewels: Int? = null,
    val bph: Int? = null,
    val hacking: Boolean? = null,
    val handwinding: Boolean? = null,
    val origin: String? = null,
)

data class Case(
    val diameterMm: Double? = null,
    val lugToLugMm: Double? = null,
    val thicknessMm: Double? = null,
    val lugWidthMm: Int? = null,
    val material: String? = null,
    val crystal: String? = null,
    val crown: String? = null,
    val bezel: String? = null,
    val caseback: String? = null,
    /** Metres, always. The form converts bar/atm on entry — SPEC-ANDROID 4. */
    val waterResistanceM: Int? = null,
    val weightG: Double? = null,
)

data class Dial(
    val colour: String? = null,
    val material: String? = null,
    val indices: String? = null,
    val lume: String? = null,
    val complications: List<String> = emptyList(),
)

data class Strap(
    val material: String? = null,
    val colour: String? = null,
    /** Falls back to the owning watch's `case.lugWidthMm` — see SPEC.md §4. */
    val widthMm: Int? = null,
    val clasp: String? = null,
    /**
     * Not nullable, matching the desktop's `fitted: bool = False`: a strap that
     * does not say it is fitted is not fitted, and there is no third state worth
     * rendering as an em-dash.
     */
    val fitted: Boolean = false,
    /** A filename in this watch's photographs, never a path. */
    val image: String? = null,
)

data class Acquisition(
    val date: LocalDate? = null,
    val price: Double? = null,
    val currency: String? = null,
    val seller: String? = null,
    val url: String? = null,
    val condition: String? = null,
    val boxAndPapers: Boolean? = null,
    val warrantyUntil: LocalDate? = null,
    /** What it costs, as distinct from what was paid — never overloaded onto `price`. */
    val targetPrice: Double? = null,
    val targetDate: LocalDate? = null,
)

data class Maintenance(
    val serviceIntervalYears: Double? = null,
    val batteryDue: LocalDate? = null,
)

data class LogEntry(
    val date: LocalDate? = null,
    val kind: String? = null,
    val note: String? = null,
) {
    companion object {
        /** The one `kind` the app reads rather than merely displays — see [nextServiceDue]. */
        const val KIND_SERVICE = "Service"
    }
}

data class TimingEntry(
    val date: LocalDate? = null,
    val deviationSec: Double? = null,
    val position: String? = null,
)

/**
 * At most one strap fitted — SPEC-ANDROID 4 says the app enforces this.
 *
 * A pure function rather than something the writer applies silently. A
 * hand-edited file claiming two fitted straps is a statement the owner made, and
 * rewriting it underneath them on load would be the storage layer overruling the
 * file it exists to serve; the loader records a warning instead. AM5's form calls
 * this when the owner ticks a new strap, which is the moment the rule is actually
 * about.
 *
 * The FIRST fitted strap wins, so ticking a strap means un-ticking the others by
 * passing the newly-fitted one at the front — not that the list order silently
 * decides which of two ticks the owner meant.
 */
fun List<Strap>.withSingleFitted(): List<Strap> {
    var seen = false
    return map { strap ->
        when {
            !strap.fitted -> strap
            seen -> strap.copy(fitted = false)
            else -> { seen = true; strap }
        }
    }
}

/** How many straps claim to be fitted. More than one is a file to warn about. */
fun List<Strap>.fittedCount(): Int = count { it.fitted }
