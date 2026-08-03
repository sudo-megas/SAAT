package io.github.sudomegas.saat.ui.detail

import androidx.annotation.StringRes
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.storage.LogEntry
import io.github.sudomegas.saat.storage.Movement
import io.github.sudomegas.saat.storage.Strap
import io.github.sudomegas.saat.storage.TimingEntry
import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.WatchRecord
import io.github.sudomegas.saat.storage.effectiveWidthMm
import io.github.sudomegas.saat.storage.frequencyHz
import io.github.sudomegas.saat.ui.formatDate
import io.github.sudomegas.saat.ui.formatMeasurement
import io.github.sudomegas.saat.ui.formatPrice
import io.github.sudomegas.saat.ui.formatSignedMeasurement
import java.io.File
import java.time.LocalDate

/**
 * The detail page as data, built before a composable ever runs.
 *
 * The whole page is a pure function of a [WatchRecord] and the directory its
 * photographs live in — no `Context`, no Compose, no clock read from inside.
 * That is what lets SPEC-ANDROID 5.6's actual rules be tested as plain JUnit:
 * "an absent field renders as a muted em-dash inside a shown group, a WHOLLY
 * empty group is hidden" is a statement about which groups exist and which rows
 * carry null, and asserting it against a rendered `Column` would need a device.
 *
 * Strings that need a resource are carried as [SpecValue.Resource] — a string
 * id plus its arguments — rather than being resolved here, so the model stays
 * translatable and the composable stays free of literals (see
 * `docs/ANDROID-STRINGS.md`). Values that are the owner's own words — a brand, a
 * dial colour, a note — are [SpecValue.Plain] and are never passed through the
 * resource table, because they are data rather than vocabulary.
 */
data class DetailPage(
    val slug: String,
    val brand: String,
    val model: String,
    val nickname: String?,
    /** `Ref. …`, style, group, status, storage, rating — whichever were filled. */
    val meta: List<SpecValue>,
    val tags: List<String>,
    val serial: String?,
    /** `media/<slug>/…`, in the owner's chosen order, primary first. */
    val images: List<File>,
    /** For the placeholder tile a photo-less watch shows, same as the grid's. */
    val diameterMm: Double?,
    val lugWidthMm: Int?,
    val specGroups: List<SpecGroup>,
    val straps: List<StrapCard>,
    val log: List<LogLine>,
    val timing: List<TimingLine>,
    val notes: String?,
)

/**
 * A value on the page.
 *
 * Two cases and no third: text the owner typed, and text the app supplies. The
 * split is the whole of hard rule 7's UI half — an enum value like `Automatic`
 * arrives here as [Plain] because it is what the file says, and AM11 will
 * translate it at display time without ever changing what is stored.
 */
sealed interface SpecValue {
    /** The owner's own words. Never translated, never templated. */
    data class Plain(val text: String) : SpecValue

    /**
     * A string resource and its arguments. `args` is empty for a plain label
     * like Yes or No, which is why there is no separate case for one.
     */
    data class Resource(@StringRes val templateRes: Int, val args: List<String> = emptyList()) :
        SpecValue
}

/** A label and its value. A null [value] is an absent field: a muted em-dash. */
data class SpecRow(@StringRes val labelRes: Int, val value: SpecValue?)

/**
 * A titled block of rows.
 *
 * Only ever constructed through [specGroup], which returns null when every row
 * is absent — SPEC-ANDROID 5.6's "a wholly empty group is hidden, not rendered
 * as dashes". A group that reaches the composable therefore always has
 * something to say.
 */
data class SpecGroup(@StringRes val titleRes: Int, val rows: List<SpecRow>)

/** One strap, as a small card. [image] is null when the strap has no photo. */
data class StrapCard(
    val material: String?,
    val colour: String?,
    /** The strap's own width, or the watch's lug width — SPEC.md §4. */
    val widthMm: Int?,
    val clasp: String?,
    val fitted: Boolean,
    val image: File?,
)

/** One log entry. Dates are already formatted; null is an entry with no date. */
data class LogLine(val date: String?, val kind: String?, val note: String?)

/** One timing reading. [deviation] carries its sign — that is the reading. */
data class TimingLine(val date: String?, val deviation: String?, val position: String?)

/**
 * Build the page, or null when the record did not load.
 *
 * A failed record has no fields to lay out; the caller shows the load error
 * instead, the same message the grid's notice already names (hard rule 6).
 */
fun detailPage(record: WatchRecord, mediaDir: File): DetailPage? {
    val watch = record.watch ?: return null

    return DetailPage(
        slug = record.slug,
        brand = watch.brand,
        model = watch.model,
        nickname = watch.nickname.orNull(),
        meta = metaParts(watch),
        tags = watch.tags.filter { it.isNotBlank() },
        serial = watch.serial.orNull(),
        // `images` holds BARE FILENAMES (SPEC-ANDROID 3) and the photographs sit
        // in the sibling media/ tree. File(it).name strips any directory part a
        // hand-edited file could have put there, which is also what stops a
        // `../` from reaching outside this watch's own folder.
        images = watch.images.mapNotNull { it.orNull() }.map { File(mediaDir, File(it).name) },
        diameterMm = watch.case.diameterMm,
        lugWidthMm = watch.case.lugWidthMm,
        specGroups = listOfNotNull(
            specGroup(R.string.screen_detail_group_movement, movementRows(watch)),
            specGroup(R.string.screen_detail_group_case, caseRows(watch)),
            specGroup(R.string.screen_detail_group_dial, dialRows(watch)),
            specGroup(R.string.screen_detail_group_acquisition, acquisitionRows(watch)),
            specGroup(R.string.screen_detail_group_maintenance, maintenanceRows(watch)),
        ),
        straps = watch.straps.map { it.toCard(watch, mediaDir) },
        log = watch.log.newestFirst { it.date }.map { it.toLine() },
        timing = watch.timing.newestFirst { it.date }.map { it.toLine() },
        notes = watch.notes.orNull(),
    )
}

// --- groups ----------------------------------------------------------------

/**
 * The rows in the desktop's own order, so a collection reads the same on both
 * screens. `power_reserve_hours` and `battery_life_years` swap by movement kind
 * — SPEC.md §4 says "show one or the other, driven by `kind`".
 *
 * With one addition the desktop does not make: a value that IS recorded is
 * shown whichever kind says. A quartz watch carrying a power reserve figure is
 * either a hand-edited file or a Mecha-quartz the owner classified themselves,
 * and hiding a number somebody typed in is worse than showing a row the kind
 * did not predict.
 */
internal fun movementRows(watch: Watch): List<SpecRow> {
    val movement = watch.movement
    val battery = movement.runsOnBattery()

    return buildList {
        add(SpecRow(R.string.field_caliber, plain(movement.caliber)))
        add(SpecRow(R.string.field_kind, plain(movement.kind)))
        if (!battery || movement.powerReserveHours != null) {
            add(SpecRow(R.string.field_power_reserve, hours(movement.powerReserveHours)))
        }
        if (battery || movement.batteryLifeYears != null) {
            add(SpecRow(R.string.field_battery_life, years(movement.batteryLifeYears)))
        }
        add(SpecRow(R.string.field_accuracy, accuracy(movement)))
        add(SpecRow(R.string.field_jewels, count(movement.jewels)))
        add(SpecRow(R.string.field_frequency, frequency(movement)))
        add(SpecRow(R.string.field_hacking, yesNo(movement.hacking)))
        add(SpecRow(R.string.field_handwinding, yesNo(movement.handwinding)))
        add(SpecRow(R.string.field_origin, plain(movement.origin)))
    }
}

internal fun caseRows(watch: Watch): List<SpecRow> {
    val case = watch.case
    return listOf(
        SpecRow(R.string.field_diameter, millimetres(case.diameterMm)),
        SpecRow(R.string.field_lug_to_lug, millimetres(case.lugToLugMm)),
        SpecRow(R.string.field_thickness, millimetres(case.thicknessMm)),
        SpecRow(R.string.field_lug_width, millimetres(case.lugWidthMm?.toDouble())),
        SpecRow(R.string.field_case_material, plain(case.material)),
        SpecRow(R.string.field_crystal, plain(case.crystal)),
        SpecRow(R.string.field_crown, plain(case.crown)),
        SpecRow(R.string.field_bezel, plain(case.bezel)),
        SpecRow(R.string.field_caseback, plain(case.caseback)),
        SpecRow(R.string.field_water_resistance, waterResistance(case.waterResistanceM)),
        SpecRow(R.string.field_weight, grams(case.weightG)),
    )
}

internal fun dialRows(watch: Watch): List<SpecRow> {
    val dial = watch.dial
    return listOf(
        SpecRow(R.string.field_dial_colour, plain(dial.colour)),
        SpecRow(R.string.field_dial_material, plain(dial.material)),
        SpecRow(R.string.field_indices, plain(dial.indices)),
        SpecRow(R.string.field_lume, plain(dial.lume)),
        SpecRow(R.string.field_complications, list(dial.complications)),
    )
}

/**
 * The seller and the URL are plain text here, unlike the desktop, which renders
 * both as clickable hand-offs to the browser.
 *
 * Hard rule 3 would permit it — handing a URL to the system browser on an
 * explicit tap is the one exception it names — but AM4's brief lists the actions
 * this page carries and a link is not among them, and `sellers.toml` is a
 * desktop concept SPEC-ANDROID never adopted. A row that looks tappable and is
 * not would be worse than a row that plainly is not.
 */
internal fun acquisitionRows(watch: Watch): List<SpecRow> {
    val acquisition = watch.acquisition
    return listOf(
        SpecRow(R.string.field_acquired, date(acquisition.date)),
        SpecRow(R.string.field_price, price(acquisition.price, acquisition.currency)),
        SpecRow(R.string.field_target_price, price(acquisition.targetPrice, acquisition.currency)),
        SpecRow(R.string.field_target_date, date(acquisition.targetDate)),
        SpecRow(R.string.field_seller, plain(acquisition.seller)),
        SpecRow(R.string.field_url, plain(acquisition.url)),
        SpecRow(R.string.field_condition, plain(acquisition.condition)),
        SpecRow(R.string.field_box_and_papers, yesNo(acquisition.boxAndPapers)),
        SpecRow(R.string.field_warranty_until, date(acquisition.warrantyUntil)),
    )
}

/**
 * The raw fields only. `nextServiceDue` exists in [io.github.sudomegas.saat
 * .storage] already and AM9 is where it surfaces — AM4's brief defers the
 * due-date line explicitly, and a maintenance notice is the sort of thing that
 * should arrive once, designed, rather than twice.
 */
internal fun maintenanceRows(watch: Watch): List<SpecRow> {
    val maintenance = watch.maintenance
    return listOf(
        SpecRow(R.string.field_service_interval, years(maintenance.serviceIntervalYears)),
        SpecRow(R.string.field_battery_due, date(maintenance.batteryDue)),
    )
}

/**
 * Identity as labelled rows, for AM9's compare screen.
 *
 * The detail page renders identity as [metaParts] — one joined header line above
 * the photograph — and compare cannot: a header line has nothing to align two
 * watches against. So identity exists twice in this file, as two PRESENTATIONS
 * of the same fields, and both go through the same `plain()`/`list()` helpers
 * every other row uses. What must never be duplicated is the field-to-value
 * mapping, and it is not.
 *
 * Ported column for column from the desktop's `columns.py` Identity group, minus
 * its `thumbnail` (whose getter always returns None) and its `name` (which
 * deliberately mirrors `model` for the table's sort and would produce a second
 * identical row here). `serial` is not among them on the desktop either — it
 * identifies one physical object, so two watches never share it and the row
 * would be permanently at full contrast saying nothing.
 */
internal fun identityRows(watch: Watch): List<SpecRow> = listOf(
    SpecRow(R.string.field_brand, plain(watch.brand)),
    SpecRow(R.string.field_model, plain(watch.model)),
    SpecRow(R.string.field_reference, plain(watch.reference)),
    SpecRow(R.string.field_nickname, plain(watch.nickname)),
    SpecRow(R.string.field_group, plain(watch.group)),
    SpecRow(R.string.field_style, plain(watch.style)),
    SpecRow(R.string.field_status, plain(watch.status)),
    SpecRow(R.string.field_storage, plain(watch.storage)),
    SpecRow(R.string.field_rating, count(watch.rating)),
    SpecRow(R.string.field_tags, list(watch.tags)),
)

/**
 * The FITTED strap's own fields, for compare — the desktop's Straps columns.
 *
 * One strap, not the list. Comparing "3 straps" against "1 strap" tells the
 * owner nothing they want to know; comparing what is actually on the two
 * wrists does. A watch with no fitted strap contributes no values here and the
 * rows drop out by the ordinary all-absent rule.
 *
 * Width falls back to the watch's own lug width via [effectiveWidthMm], the
 * same rule the detail page's strap cards use — SPEC.md §4.
 */
internal fun strapRows(watch: Watch): List<SpecRow> {
    val fitted = watch.straps.firstOrNull { it.fitted }
    return listOf(
        SpecRow(R.string.field_strap_material, plain(fitted?.material)),
        SpecRow(R.string.field_strap_colour, plain(fitted?.colour)),
        SpecRow(R.string.field_strap_width, millimetres(fitted?.effectiveWidthMm(watch)?.toDouble())),
        SpecRow(R.string.field_strap_clasp, plain(fitted?.clasp)),
    )
}

/** The group, or null when not one row in it carries a value. */
internal fun specGroup(@StringRes titleRes: Int, rows: List<SpecRow>): SpecGroup? =
    if (rows.none { it.value != null }) null else SpecGroup(titleRes, rows)

// --- the header's meta line -------------------------------------------------

/**
 * `Ref. SARB033 · Dress · Seiko Group · Owned · Storage: box 2 · ★★★★☆`.
 *
 * Status is always present — the model defaults it to Owned and the desktop
 * prints it unconditionally — so the line is never empty. Everything else joins
 * only when the owner filled it in.
 */
internal fun metaParts(watch: Watch): List<SpecValue> = buildList {
    watch.reference.orNull()?.let {
        add(SpecValue.Resource(R.string.screen_detail_reference, listOf(it)))
    }
    watch.style.orNull()?.let { add(SpecValue.Plain(it)) }
    watch.group.orNull()?.let { add(SpecValue.Plain(it)) }
    add(SpecValue.Plain(watch.status))
    watch.storage.orNull()?.let {
        add(SpecValue.Resource(R.string.screen_detail_storage, listOf(it)))
    }
    // Stars rather than "4/5": the field is a personal mark, not a score, and
    // SPEC.md §4 is explicit that it is "not a review score". Clamped because a
    // hand-edited file can say 9, and `"★".repeat(-1)` throws.
    watch.rating?.coerceIn(0, MAX_RATING)?.let {
        add(SpecValue.Plain("★".repeat(it) + "☆".repeat(MAX_RATING - it)))
    }
}

private const val MAX_RATING = 5

// --- rows within the list-shaped groups -------------------------------------

private fun Strap.toCard(owner: Watch, mediaDir: File) = StrapCard(
    material = material.orNull(),
    colour = colour.orNull(),
    widthMm = effectiveWidthMm(owner),
    clasp = clasp.orNull(),
    fitted = fitted,
    image = image.orNull()?.let { File(mediaDir, File(it).name) },
)

private fun LogEntry.toLine() = LogLine(
    date = date?.let(::formatDate),
    kind = kind.orNull(),
    note = note.orNull(),
)

private fun TimingEntry.toLine() = TimingLine(
    date = date?.let(::formatDate),
    deviation = deviationSec?.let(::formatSignedMeasurement),
    position = position.orNull(),
)

/**
 * Newest first, with undated entries last.
 *
 * The desktop sorts on `date or date.min` descending, which puts undated
 * entries at the bottom; `LocalDate.MIN` does the same here. Stable, so two
 * entries recorded on one day keep the order the file lists them in rather than
 * swapping about between recompositions.
 */
private fun <T> List<T>.newestFirst(date: (T) -> LocalDate?): List<T> =
    sortedByDescending { date(it) ?: LocalDate.MIN }

// --- value builders ---------------------------------------------------------

/**
 * Quartz and Solar are what SPEC.md §4 names, and nothing else is guessed at.
 *
 * Mecha-quartz and Kinetic both carry a battery too, but they also have a
 * mainspring or a rotor, and which figure their owner tracks is theirs to say —
 * the rule above shows whichever value is actually recorded, so neither is lost.
 * Case-insensitive because `kind` is free text: the dropdown suggests these
 * values, it does not constrain them.
 */
private fun Movement.runsOnBattery(): Boolean =
    kind?.trim()?.lowercase() in setOf("quartz", "solar")

private fun String?.orNull(): String? = this?.trim()?.takeIf { it.isNotEmpty() }

private fun plain(value: String?): SpecValue? = value.orNull()?.let(SpecValue::Plain)

private fun list(values: List<String>): SpecValue? = values
    .mapNotNull { it.orNull() }
    .takeIf { it.isNotEmpty() }
    ?.let { SpecValue.Plain(it.joinToString(", ")) }

private fun millimetres(value: Double?): SpecValue? = unit(R.string.field_value_mm, value)

private fun grams(value: Double?): SpecValue? = unit(R.string.field_value_grams, value)

private fun hours(value: Double?): SpecValue? = unit(R.string.field_value_hours, value)

private fun years(value: Double?): SpecValue? = unit(R.string.field_value_years, value)

private fun unit(@StringRes templateRes: Int, value: Double?): SpecValue? =
    value?.let { SpecValue.Resource(templateRes, listOf(formatMeasurement(it))) }

private fun count(value: Int?): SpecValue? = value?.let { SpecValue.Plain(it.toString()) }

private fun date(value: LocalDate?): SpecValue? = value?.let { SpecValue.Plain(formatDate(it)) }

private fun yesNo(value: Boolean?): SpecValue? = value?.let {
    SpecValue.Resource(if (it) R.string.field_value_yes else R.string.field_value_no)
}

/**
 * `850.00 TRY`, or `850.00` when the file names no currency.
 *
 * The currency is NOT defaulted to TRY here. SPEC.md §4 makes TRY the form's
 * default for a new entry; printing it beside a figure that never said so would
 * be the display layer inventing a fact about what somebody paid.
 */
private fun price(value: Double?, currency: String?): SpecValue? {
    if (value == null) return null
    val amount = formatPrice(value)
    val symbol = currency.orNull() ?: return SpecValue.Plain(amount)
    return SpecValue.Resource(R.string.field_value_price, listOf(amount, symbol))
}

/**
 * `100 m (10 bar)` — SPEC-ANDROID 4: metres always, bar in parentheses.
 *
 * `Math.rint` rather than `Math.round`, matching the desktop's `round()`, which
 * is half-to-even. It shows on 5 m and 15 m: Python answers 0 bar and 2 bar, and
 * a half-up rounding would answer 1 and 2. Half a bar is not a rating anybody
 * prints, but the two apps agreeing beats either being independently sensible.
 */
private fun waterResistance(metres: Int?): SpecValue? = metres?.let {
    SpecValue.Resource(
        R.string.field_value_water_resistance,
        listOf(it.toString(), Math.rint(it / BAR_IN_METRES).toInt().toString()),
    )
}

private const val BAR_IN_METRES = 10.0

/** `28800 bph (4 Hz)`. Null for every quartz watch, which has no beat rate. */
private fun frequency(movement: Movement): SpecValue? {
    val bph = movement.bph ?: return null
    val hz = movement.frequencyHz() ?: return null
    return SpecValue.Resource(
        R.string.field_value_frequency,
        listOf(bph.toString(), formatMeasurement(hz)),
    )
}

/**
 * `-5/+8 sec/day`, and `?` for whichever half the owner left out — a movement
 * specified only on its slow side is still worth showing, and an em-dash for
 * the whole row would throw away the half that IS known.
 *
 * The unit falls back to sec/day, which is what the desktop assumes and what
 * every mechanical spec sheet quotes.
 */
private fun accuracy(movement: Movement): SpecValue? {
    if (movement.accuracyMin == null && movement.accuracyMax == null) return null
    return SpecValue.Resource(
        R.string.field_value_accuracy,
        listOf(
            movement.accuracyMin?.let(::formatSignedMeasurement) ?: ACCURACY_UNKNOWN,
            movement.accuracyMax?.let(::formatSignedMeasurement) ?: ACCURACY_UNKNOWN,
            movement.accuracyUnit.orNull() ?: DEFAULT_ACCURACY_UNIT,
        ),
    )
}

private const val ACCURACY_UNKNOWN = "?"

/** Canonical English, stored and displayed — hard rule 7. AM11 translates it. */
private const val DEFAULT_ACCURACY_UNIT = "sec/day"
