package io.github.sudomegas.saat.ui.form

import io.github.sudomegas.saat.storage.Acquisition
import io.github.sudomegas.saat.storage.Case
import io.github.sudomegas.saat.storage.Dial
import io.github.sudomegas.saat.storage.LogEntry
import io.github.sudomegas.saat.storage.Maintenance
import io.github.sudomegas.saat.storage.Movement
import io.github.sudomegas.saat.storage.Strap
import io.github.sudomegas.saat.storage.TimingEntry
import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.withSingleFitted
import io.github.sudomegas.saat.ui.formatMeasurement
import java.time.LocalDate

/**
 * The add/edit form, as data — SPEC-ANDROID 5.7.
 *
 * EVERY NUMERIC FIELD IS A STRING, and that is the decision the rest of this
 * file follows from. A number being typed passes through states that are not
 * numbers: `4`, `4.`, `4.5`, and `-` on its way to `-5`. A model that held
 * `Double?` would have to either reject those keystrokes or throw the text away
 * and put something else back in the field while the owner is still typing, and
 * both are the kind of input handling people describe as "it fights me".
 * Parsing happens once, at save.
 *
 * Being plain data also makes the two rules AM5 is graded on testable without a
 * device:
 *
 *  - SAVING WITH ONLY BRAND AND MODEL MUST SUCCEED. That is [canSave], and it
 *    is the whole of validation. Nothing else blocks; SPEC-ANDROID 5.7 says
 *    validation "may advise, it may never obstruct".
 *  - Backing out with unsaved changes prompts. That is state inequality against
 *    the state the form opened with — see `FormViewModel.isDirty`.
 *
 * The dirty check compares FORM STATE, not the built watch. Typing a character
 * and deleting it returns to equality and does not prompt, which the desktop's
 * signal-based flag gets wrong; typing something that will not parse stays
 * dirty, which comparing built watches would get wrong.
 */
data class WatchFormState(
    // --- identity --------------------------------------------------------
    val brand: String = "",
    val model: String = "",
    val reference: String = "",
    val nickname: String = "",
    val serial: String = "",
    val group: String = "",
    val style: String = "",
    val status: String = Watch.STATUS_OWNED,
    val storage: String = "",
    val rating: String = "",
    val tags: List<String> = emptyList(),

    // --- movement --------------------------------------------------------
    val caliber: String = "",
    val kind: String = "",
    val powerReserveHours: String = "",
    val batteryLifeYears: String = "",
    val accuracyMin: String = "",
    val accuracyMax: String = "",
    val accuracyUnit: String = "",
    val jewels: String = "",
    val bph: String = "",
    val hacking: Boolean? = null,
    val handwinding: Boolean? = null,
    val origin: String = "",

    // --- case ------------------------------------------------------------
    val diameterMm: String = "",
    val lugToLugMm: String = "",
    val thicknessMm: String = "",
    val lugWidthMm: String = "",
    val caseMaterial: String = "",
    val crystal: String = "",
    val crown: String = "",
    val bezel: String = "",
    val caseback: String = "",
    /** As typed, in [waterResistanceUnit]. Stored in metres — see [toWatch]. */
    val waterResistance: String = "",
    val waterResistanceUnit: String = UNIT_METRES,
    val weightG: String = "",

    // --- dial ------------------------------------------------------------
    val dialColour: String = "",
    val dialMaterial: String = "",
    val indices: String = "",
    val lume: String = "",
    val complications: List<String> = emptyList(),

    // --- lists -----------------------------------------------------------
    val straps: List<StrapFormState> = emptyList(),
    val log: List<LogFormState> = emptyList(),
    val timing: List<TimingFormState> = emptyList(),

    // --- acquisition -----------------------------------------------------
    val acquiredOn: LocalDate? = null,
    val price: String = "",
    val targetPrice: String = "",
    val targetDate: LocalDate? = null,
    val currency: String = "",
    val seller: String = "",
    val url: String = "",
    val condition: String = "",
    val boxAndPapers: Boolean? = null,
    val warrantyUntil: LocalDate? = null,

    // --- maintenance -----------------------------------------------------
    val serviceIntervalYears: String = "",
    val batteryDue: LocalDate? = null,

    val notes: String = "",

    /**
     * Bare filenames, primary first — the order becomes `Watch.images`. AM5b
     * fills this from the picker and the camera; AM5a only carries it through
     * an edit so a save cannot drop a watch's photographs.
     */
    val images: List<String> = emptyList(),
) {
    /**
     * The one rule that blocks a save, and the only one there will ever be.
     *
     * SPEC-ANDROID 5.7: "SAVING WITH ONLY BRAND AND MODEL FILLED MUST SUCCEED.
     * Validation blocks nothing else." The collection is always partly
     * incomplete — that is what a hobby record looks like — and a form that
     * argued about it would simply not get used.
     */
    val canSave: Boolean get() = brand.isNotBlank() && model.isNotBlank()

    /**
     * Quartz and Solar swap power reserve for battery life, per SPEC-ANDROID
     * 5.7 and SPEC.md §4.
     */
    val usesBattery: Boolean get() = runsOnBattery(kind)

    companion object {
        const val UNIT_METRES = "m"
        const val UNIT_BAR = "bar"
        const val UNIT_ATM = "atm"

        /** The units the water-resistance field accepts. Never translated. */
        val WATER_RESISTANCE_UNITS = listOf(UNIT_METRES, UNIT_BAR, UNIT_ATM)

        /**
         * 1 bar and 1 atm are both taken as 10 m — SPEC-ANDROID 4's own figure.
         * They are not equal in physics (1 atm is 1.01325 bar) and the
         * difference is 13 cm of water, which is below the precision of every
         * rating ever stamped on a caseback. The desktop uses the same two
         * tens, and agreeing with it matters more than the third decimal.
         */
        val UNIT_FACTORS = mapOf(UNIT_METRES to 1, UNIT_BAR to 10, UNIT_ATM to 10)

        /** TRY, per SPEC.md §4 — for a NEW watch only. See [from]. */
        const val DEFAULT_CURRENCY = "TRY"

        /** A blank form, for adding. */
        fun empty(): WatchFormState = WatchFormState(currency = DEFAULT_CURRENCY)

        /**
         * The form as it opens on an existing watch.
         *
         * Round-trips: `from(toWatch(from(w))) == from(w)`, which is what makes
         * the dirty check trustworthy — opening a watch and changing nothing
         * must not report unsaved changes. Numbers are rendered through
         * [formatMeasurement] for that reason, so a stored `41.0` comes back as
         * `41` and does not re-render as `41.0` on the next open.
         *
         * The currency default is NOT applied here. A watch whose file names no
         * currency has not said TRY; writing one in on open would make an edit
         * to some unrelated field silently add a claim about what was paid.
         */
        fun from(watch: Watch): WatchFormState = WatchFormState(
            brand = watch.brand,
            model = watch.model,
            reference = watch.reference.orBlank(),
            nickname = watch.nickname.orBlank(),
            serial = watch.serial.orBlank(),
            group = watch.group.orBlank(),
            style = watch.style.orBlank(),
            status = watch.status,
            storage = watch.storage.orBlank(),
            rating = watch.rating?.toString().orEmpty(),
            tags = watch.tags,

            caliber = watch.movement.caliber.orBlank(),
            kind = watch.movement.kind.orBlank(),
            powerReserveHours = watch.movement.powerReserveHours.text(),
            batteryLifeYears = watch.movement.batteryLifeYears.text(),
            accuracyMin = watch.movement.accuracyMin.text(),
            accuracyMax = watch.movement.accuracyMax.text(),
            accuracyUnit = watch.movement.accuracyUnit.orBlank(),
            jewels = watch.movement.jewels?.toString().orEmpty(),
            bph = watch.movement.bph?.toString().orEmpty(),
            hacking = watch.movement.hacking,
            handwinding = watch.movement.handwinding,
            origin = watch.movement.origin.orBlank(),

            diameterMm = watch.case.diameterMm.text(),
            lugToLugMm = watch.case.lugToLugMm.text(),
            thicknessMm = watch.case.thicknessMm.text(),
            lugWidthMm = watch.case.lugWidthMm?.toString().orEmpty(),
            caseMaterial = watch.case.material.orBlank(),
            crystal = watch.case.crystal.orBlank(),
            crown = watch.case.crown.orBlank(),
            bezel = watch.case.bezel.orBlank(),
            caseback = watch.case.caseback.orBlank(),
            // Always shown in metres, whatever unit it was entered in: metres
            // are what is stored, and re-offering "bar" would invite a second
            // conversion of an already-converted figure.
            waterResistance = watch.case.waterResistanceM?.toString().orEmpty(),
            waterResistanceUnit = UNIT_METRES,
            weightG = watch.case.weightG.text(),

            dialColour = watch.dial.colour.orBlank(),
            dialMaterial = watch.dial.material.orBlank(),
            indices = watch.dial.indices.orBlank(),
            lume = watch.dial.lume.orBlank(),
            complications = watch.dial.complications,

            straps = watch.straps.map(StrapFormState::from),
            log = watch.log.map(LogFormState::from),
            timing = watch.timing.map(TimingFormState::from),

            acquiredOn = watch.acquisition.date,
            price = watch.acquisition.price.text(),
            targetPrice = watch.acquisition.targetPrice.text(),
            targetDate = watch.acquisition.targetDate,
            currency = watch.acquisition.currency.orBlank(),
            seller = watch.acquisition.seller.orBlank(),
            url = watch.acquisition.url.orBlank(),
            condition = watch.acquisition.condition.orBlank(),
            boxAndPapers = watch.acquisition.boxAndPapers,
            warrantyUntil = watch.acquisition.warrantyUntil,

            serviceIntervalYears = watch.maintenance.serviceIntervalYears.text(),
            batteryDue = watch.maintenance.batteryDue,

            notes = watch.notes.orBlank(),
            images = watch.images,
        )
    }
}

data class StrapFormState(
    val material: String = "",
    val colour: String = "",
    val widthMm: String = "",
    val clasp: String = "",
    val fitted: Boolean = false,
    /** A filename among this watch's photographs, or blank for none. */
    val image: String = "",
) {
    companion object {
        fun from(strap: Strap) = StrapFormState(
            material = strap.material.orBlank(),
            colour = strap.colour.orBlank(),
            widthMm = strap.widthMm?.toString().orEmpty(),
            clasp = strap.clasp.orBlank(),
            fitted = strap.fitted,
            image = strap.image.orBlank(),
        )
    }
}

data class LogFormState(
    val date: LocalDate? = null,
    val kind: String = "",
    val note: String = "",
) {
    companion object {
        fun from(entry: LogEntry) = LogFormState(
            date = entry.date,
            kind = entry.kind.orBlank(),
            note = entry.note.orBlank(),
        )
    }
}

data class TimingFormState(
    val date: LocalDate? = null,
    val deviationSec: String = "",
    val position: String = "",
) {
    companion object {
        fun from(entry: TimingEntry) = TimingFormState(
            date = entry.date,
            deviationSec = entry.deviationSec.text(),
            position = entry.position.orBlank(),
        )
    }
}

/**
 * The form as a watch, ready to save.
 *
 * [preservedWorn] is threaded through rather than edited: `worn` is the
 * calendar's field and the wear button's, never the form's, and rebuilding a
 * watch without it would delete a wear history on every edit. The desktop
 * carries the same `preserved_worn` for the same reason.
 *
 * BLANK IS ABSENT, everywhere. A cleared field becomes null, `WatchToml` then
 * omits the key entirely, and the file loses the line rather than gaining an
 * empty string — which is also what the desktop's storage layer does when it
 * deletes a key for a `None`.
 *
 * A number that does not parse is treated as absent rather than as a reason to
 * refuse the save. Validation may advise and may never obstruct; the field is
 * still on screen with what was typed in it, and the owner can see it did not
 * take.
 */
fun WatchFormState.toWatch(preservedWorn: List<LocalDate> = emptyList()): Watch = Watch(
    brand = brand.trim(),
    model = model.trim(),
    reference = reference.orNull(),
    nickname = nickname.orNull(),
    serial = serial.orNull(),
    group = group.orNull(),
    style = style.orNull(),
    status = status.orNull() ?: Watch.STATUS_OWNED,
    storage = storage.orNull(),
    rating = rating.intOrNull(),
    tags = tags.mapNotNull { it.orNull() },

    movement = Movement(
        caliber = caliber.orNull(),
        kind = kind.orNull(),
        powerReserveHours = powerReserveHours.doubleOrNull(),
        batteryLifeYears = batteryLifeYears.doubleOrNull(),
        accuracyMin = accuracyMin.doubleOrNull(),
        accuracyMax = accuracyMax.doubleOrNull(),
        accuracyUnit = accuracyUnit.orNull(),
        jewels = jewels.intOrNull(),
        bph = bph.intOrNull(),
        hacking = hacking,
        handwinding = handwinding,
        origin = origin.orNull(),
    ),
    case = Case(
        diameterMm = diameterMm.doubleOrNull(),
        lugToLugMm = lugToLugMm.doubleOrNull(),
        thicknessMm = thicknessMm.doubleOrNull(),
        lugWidthMm = lugWidthMm.intOrNull(),
        material = caseMaterial.orNull(),
        crystal = crystal.orNull(),
        crown = crown.orNull(),
        bezel = bezel.orNull(),
        caseback = caseback.orNull(),
        waterResistanceM = waterResistanceMetres(),
        weightG = weightG.doubleOrNull(),
    ),
    dial = Dial(
        colour = dialColour.orNull(),
        material = dialMaterial.orNull(),
        indices = indices.orNull(),
        lume = lume.orNull(),
        complications = complications.mapNotNull { it.orNull() },
    ),
    // At most one fitted, enforced on the way out as well as in the editor —
    // SPEC-ANDROID 4 says the app enforces it, and a rule held in only one
    // place is a rule the next caller gets to skip.
    straps = straps.map { it.toStrap() }.withSingleFitted(),
    acquisition = Acquisition(
        date = acquiredOn,
        price = price.doubleOrNull(),
        currency = currency.orNull(),
        seller = seller.orNull(),
        url = url.orNull(),
        condition = condition.orNull(),
        boxAndPapers = boxAndPapers,
        warrantyUntil = warrantyUntil,
        targetPrice = targetPrice.doubleOrNull(),
        targetDate = targetDate,
    ),
    maintenance = Maintenance(
        serviceIntervalYears = serviceIntervalYears.doubleOrNull(),
        batteryDue = batteryDue,
    ),
    // A wholly blank row is dropped rather than written as an entry of three
    // nulls: "Add log entry" then changing your mind should leave no trace.
    log = log.filterNot { it.isBlank }.map { it.toEntry() },
    worn = preservedWorn,
    timing = timing.filterNot { it.isBlank }.map { it.toEntry() },
    notes = notes.orNull(),
    images = images,
)

/**
 * Metres, whatever unit was typed — SPEC-ANDROID 4: "stored in metres, always".
 *
 * Integer arithmetic, matching the desktop's `UNIT_FACTORS` multiply exactly. A
 * fractional figure is floored to a whole metre first, because
 * `water_resistance_m` is an `Int` on both sides and 30.5 m is not a rating
 * anybody stamps.
 */
internal fun WatchFormState.waterResistanceMetres(): Int? {
    val entered = waterResistance.trim().toDoubleOrNull() ?: return null
    val factor = WatchFormState.UNIT_FACTORS[waterResistanceUnit] ?: 1
    return (entered * factor).toInt()
}

private fun StrapFormState.toStrap() = Strap(
    material = material.orNull(),
    colour = colour.orNull(),
    widthMm = widthMm.intOrNull(),
    clasp = clasp.orNull(),
    fitted = fitted,
    image = image.orNull(),
)

private val LogFormState.isBlank: Boolean
    get() = date == null && kind.isBlank() && note.isBlank()

private fun LogFormState.toEntry() = LogEntry(date = date, kind = kind.orNull(), note = note.orNull())

private val TimingFormState.isBlank: Boolean
    get() = date == null && deviationSec.isBlank() && position.isBlank()

private fun TimingFormState.toEntry() =
    TimingEntry(date = date, deviationSec = deviationSec.doubleOrNull(), position = position.orNull())

// --- text and value, in both directions -------------------------------------

private fun String?.orBlank(): String = this ?: ""

private fun String.orNull(): String? = trim().takeIf { it.isNotEmpty() }

/**
 * `41.0` renders as `41`, so reopening a watch and saving it again writes the
 * same file. Without this the round trip would turn every stored integer-valued
 * double into a dirty form the moment it opened.
 */
private fun Double?.text(): String = this?.let(::formatMeasurement).orEmpty()

private fun String.intOrNull(): Int? = trim().takeIf { it.isNotEmpty() }?.toIntOrNull()

private fun String.doubleOrNull(): Double? = trim().takeIf { it.isNotEmpty() }?.toDoubleOrNull()
