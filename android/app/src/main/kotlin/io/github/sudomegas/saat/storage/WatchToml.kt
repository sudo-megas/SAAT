package io.github.sudomegas.saat.storage

import dev.eav.tomlkt.Toml
import dev.eav.tomlkt.TomlArray
import dev.eav.tomlkt.TomlElement
import dev.eav.tomlkt.TomlLiteral
import dev.eav.tomlkt.TomlNull
import dev.eav.tomlkt.TomlTable
import dev.eav.tomlkt.buildTomlArray
import dev.eav.tomlkt.buildTomlTable
import dev.eav.tomlkt.element
import dev.eav.tomlkt.toBooleanOrNull
import dev.eav.tomlkt.toDoubleOrNull
import dev.eav.tomlkt.toLocalDateOrNull
import dev.eav.tomlkt.toLocalDateTimeOrNull
import dev.eav.tomlkt.toLongOrNull
import dev.eav.tomlkt.toOffsetDateTimeOrNull
import java.time.LocalDate

/**
 * The one place the snake_case of `watch.toml` meets the camelCase of [Watch].
 *
 * Written against tomlkt's DOCUMENT model — `parseToTomlTable` in, a hand-built
 * `TomlTable` out — rather than against `@Serializable` data classes, for two
 * reasons that both come down to serving files the app did not write:
 *
 *  1. A `watch.toml` is a file the owner is invited to hand-edit; SPEC.md §3
 *     supports copying `_template.toml` into place and filling it in by hand.
 *     kotlinx.serialization's answer to `rating = "4"` is to throw, which would
 *     cost the whole watch over one stray pair of quotes. Reading the document
 *     tree lets a mistyped field cost exactly itself.
 *  2. TOML requires every top-level key to appear before the first table header,
 *     or a bare `worn = [...]` written after `[[log]]` silently becomes
 *     `log[1].worn` and the wear history vanishes. Building the table explicitly
 *     puts that ordering under this file's control rather than under the
 *     declaration order of a data class somebody might tidy up later.
 *
 * COERCION POLICY, applied by the readers below and stated once here:
 *
 *  - **Coerced in silence** when the intent is unambiguous and nothing is lost:
 *    `"4"` for a whole number, `41` where a decimal belongs, `4.0` for a whole
 *    number, `1`/`0` for a boolean, a lone value where a list belongs, a single
 *    `[straps]` table where `[[straps]]` was meant.
 *  - **Warned about and left absent** when the value cannot become the field's
 *    type without inventing something: `"high"` for a number, a group where a
 *    single value belongs, a date nothing can parse. The warning names the field
 *    and quotes what was there, and travels out with the record — hard rule 6,
 *    never a log line and never a silent null.
 *
 * Only two things are fatal, because only two things mean "this is not a watch":
 * TOML that will not parse at all, and a missing `brand` or `model`. Everything
 * else loads, and one bad field costs one field.
 */

/** The file is not a watch record. Carried out as a load error, never thrown past the loader. */
class WatchFormatException(message: String, cause: Throwable? = null) : Exception(message, cause)

/** A watch plus everything the loader had to forgive to produce it. */
data class DecodedWatch(
    val watch: Watch,
    val warnings: List<String> = emptyList(),
)

// explicitNulls = false is required rather than preferred: TOML has no null
// literal, and tomlkt's default emits `key = null` for absent optionals — a file
// no conformant parser will read back, the desktop's tomlkit included. Measured
// in AM1's TomlContractTest, which is where that nearly shipped.
private val toml = Toml {
    ignoreUnknownKeys = true
    explicitNulls = false
}

// ---------------------------------------------------------------------------
// Reading
// ---------------------------------------------------------------------------

/**
 * @throws WatchFormatException if the text will not parse, or has no brand or model.
 */
fun decodeWatch(text: String): DecodedWatch {
    val root = try {
        toml.parseToTomlTable(text)
    } catch (e: Exception) {
        throw WatchFormatException(e.message ?: "could not be parsed as TOML", e)
    }

    val fields = FieldReader()

    // brand and model are the only required fields in the whole schema
    // (SPEC.md §4), and a file without them is not a record this app can
    // identify, sort or slug. A blank one is as absent as none.
    val brand = fields.string(root, "brand", "brand")?.takeIf { it.isNotBlank() }
        ?: throw WatchFormatException("missing required field: brand")
    val model = fields.string(root, "model", "model")?.takeIf { it.isNotBlank() }
        ?: throw WatchFormatException("missing required field: model")

    val straps = fields.tables(root, "straps", "straps")
        .mapIndexed { i, table -> fields.strap(table, "straps[$i]") }

    if (straps.fittedCount() > 1) {
        // SPEC-ANDROID 4 says at most one strap is fitted, and this file says
        // otherwise. Reported, not corrected — see withSingleFitted().
        fields.warn(
            "straps",
            "${straps.fittedCount()} straps are marked fitted; at most one may be",
        )
    }

    val watch = Watch(
        brand = brand,
        model = model,
        reference = fields.string(root, "reference", "reference"),
        nickname = fields.string(root, "nickname", "nickname"),
        serial = fields.string(root, "serial", "serial"),
        group = fields.string(root, "group", "group"),
        style = fields.string(root, "style", "style"),
        // The desktop reads an absent status as Owned and writes it on every
        // save. Matching that is parity, not a default of ours.
        status = fields.string(root, "status", "status") ?: Watch.STATUS_OWNED,
        storage = fields.string(root, "storage", "storage"),
        rating = fields.int(root, "rating", "rating"),
        tags = fields.stringList(root, "tags", "tags"),

        movement = fields.movement(fields.table(root, "movement", "movement")),
        case = fields.case(fields.table(root, "case", "case")),
        dial = fields.dial(fields.table(root, "dial", "dial")),
        straps = straps,
        acquisition = fields.acquisition(fields.table(root, "acquisition", "acquisition")),
        maintenance = fields.maintenance(fields.table(root, "maintenance", "maintenance")),
        log = fields.tables(root, "log", "log")
            .mapIndexed { i, table -> fields.logEntry(table, "log[$i]") },
        worn = fields.dateList(root, "worn", "worn"),
        timing = fields.tables(root, "timing", "timing")
            .mapIndexed { i, table -> fields.timingEntry(table, "timing[$i]") },
        notes = fields.string(root, "notes", "notes"),
        images = fields.stringList(root, "images", "images"),
    )

    return DecodedWatch(watch, fields.warnings.toList())
}

private class FieldReader {

    val warnings = mutableListOf<String>()

    fun warn(path: String, message: String) {
        warnings += "$path: $message"
    }

    private fun <T> refuse(path: String, message: String): T? {
        warn(path, message)
        return null
    }

    // ---- groups ----------------------------------------------------------

    fun movement(t: TomlTable?) = Movement(
        caliber = string(t, "caliber", "movement.caliber"),
        kind = string(t, "kind", "movement.kind"),
        powerReserveHours = double(t, "power_reserve_hours", "movement.power_reserve_hours"),
        batteryLifeYears = double(t, "battery_life_years", "movement.battery_life_years"),
        accuracyMin = double(t, "accuracy_min", "movement.accuracy_min"),
        accuracyMax = double(t, "accuracy_max", "movement.accuracy_max"),
        accuracyUnit = string(t, "accuracy_unit", "movement.accuracy_unit"),
        jewels = int(t, "jewels", "movement.jewels"),
        bph = int(t, "bph", "movement.bph"),
        hacking = bool(t, "hacking", "movement.hacking"),
        handwinding = bool(t, "handwinding", "movement.handwinding"),
        origin = string(t, "origin", "movement.origin"),
    )

    fun case(t: TomlTable?) = Case(
        diameterMm = double(t, "diameter_mm", "case.diameter_mm"),
        lugToLugMm = double(t, "lug_to_lug_mm", "case.lug_to_lug_mm"),
        thicknessMm = double(t, "thickness_mm", "case.thickness_mm"),
        lugWidthMm = int(t, "lug_width_mm", "case.lug_width_mm"),
        material = string(t, "material", "case.material"),
        crystal = string(t, "crystal", "case.crystal"),
        crown = string(t, "crown", "case.crown"),
        bezel = string(t, "bezel", "case.bezel"),
        caseback = string(t, "caseback", "case.caseback"),
        waterResistanceM = int(t, "water_resistance_m", "case.water_resistance_m"),
        weightG = double(t, "weight_g", "case.weight_g"),
    )

    fun dial(t: TomlTable?) = Dial(
        colour = string(t, "colour", "dial.colour"),
        material = string(t, "material", "dial.material"),
        indices = string(t, "indices", "dial.indices"),
        lume = string(t, "lume", "dial.lume"),
        complications = stringList(t, "complications", "dial.complications"),
    )

    fun strap(t: TomlTable, path: String) = Strap(
        material = string(t, "material", "$path.material"),
        colour = string(t, "colour", "$path.colour"),
        widthMm = int(t, "width_mm", "$path.width_mm"),
        clasp = string(t, "clasp", "$path.clasp"),
        fitted = bool(t, "fitted", "$path.fitted") ?: false,
        image = string(t, "image", "$path.image"),
    )

    fun acquisition(t: TomlTable?) = Acquisition(
        date = date(t, "date", "acquisition.date"),
        price = double(t, "price", "acquisition.price"),
        currency = string(t, "currency", "acquisition.currency"),
        seller = string(t, "seller", "acquisition.seller"),
        url = string(t, "url", "acquisition.url"),
        condition = string(t, "condition", "acquisition.condition"),
        boxAndPapers = bool(t, "box_and_papers", "acquisition.box_and_papers"),
        warrantyUntil = date(t, "warranty_until", "acquisition.warranty_until"),
        targetPrice = double(t, "target_price", "acquisition.target_price"),
        targetDate = date(t, "target_date", "acquisition.target_date"),
    )

    fun maintenance(t: TomlTable?) = Maintenance(
        serviceIntervalYears = double(t, "service_interval_years", "maintenance.service_interval_years"),
        batteryDue = date(t, "battery_due", "maintenance.battery_due"),
    )

    fun logEntry(t: TomlTable, path: String) = LogEntry(
        date = date(t, "date", "$path.date"),
        kind = string(t, "kind", "$path.kind"),
        note = string(t, "note", "$path.note"),
    )

    fun timingEntry(t: TomlTable, path: String) = TimingEntry(
        date = date(t, "date", "$path.date"),
        deviationSec = double(t, "deviation_sec", "$path.deviation_sec"),
        position = string(t, "position", "$path.position"),
    )

    // ---- shape -----------------------------------------------------------

    private fun element(t: TomlTable?, key: String): TomlElement? =
        t?.get(key)?.takeIf { it !is TomlNull }

    private fun literal(t: TomlTable?, key: String, path: String): TomlLiteral? =
        when (val e = element(t, key)) {
            null -> null
            is TomlLiteral -> e
            else -> refuse(path, "expected a single value, got ${shapeOf(e)}")
        }

    fun table(t: TomlTable?, key: String, path: String): TomlTable? =
        when (val e = element(t, key)) {
            null -> null
            is TomlTable -> e
            else -> refuse(path, "expected a group of settings, got ${shapeOf(e)}")
        }

    /** An array of tables, tolerating a single `[straps]` where `[[straps]]` was meant. */
    fun tables(t: TomlTable?, key: String, path: String): List<TomlTable> =
        when (val e = element(t, key)) {
            null -> emptyList()
            is TomlTable -> listOf(e)
            is TomlArray -> e.mapIndexedNotNull { i, item ->
                item as? TomlTable
                    ?: refuse("$path[$i]", "expected a group of settings, got ${shapeOf(item)}")
            }
            else -> {
                warn(path, "expected a list of entries, got a single value")
                emptyList()
            }
        }

    // ---- single values ---------------------------------------------------

    fun string(t: TomlTable?, key: String, path: String): String? =
        literal(t, key, path)?.let { asString(it) }

    fun int(t: TomlTable?, key: String, path: String): Int? =
        literal(t, key, path)?.let { asInt(it, path) }

    fun double(t: TomlTable?, key: String, path: String): Double? =
        literal(t, key, path)?.let { asDouble(it, path) }

    fun bool(t: TomlTable?, key: String, path: String): Boolean? =
        literal(t, key, path)?.let { asBool(it, path) }

    fun date(t: TomlTable?, key: String, path: String): LocalDate? =
        literal(t, key, path)?.let { asDate(it, path) }

    // ---- lists -----------------------------------------------------------

    fun stringList(t: TomlTable?, key: String, path: String): List<String> =
        list(t, key, path) { lit, _ -> asString(lit) }

    fun dateList(t: TomlTable?, key: String, path: String): List<LocalDate> =
        list(t, key, path) { lit, itemPath -> asDate(lit, itemPath) }

    /**
     * Shared list walking. A lone value where a list belongs reads as a
     * one-element list — `tags = "diver"` is unambiguous — and an element that
     * cannot be read costs itself rather than the list.
     */
    private fun <T : Any> list(
        t: TomlTable?,
        key: String,
        path: String,
        read: (TomlLiteral, String) -> T?,
    ): List<T> = when (val e = element(t, key)) {
        null -> emptyList()
        is TomlLiteral -> listOfNotNull(read(e, path))
        is TomlArray -> e.mapIndexedNotNull { i, item ->
            when (item) {
                is TomlLiteral -> read(item, "$path[$i]")
                else -> refuse<T>("$path[$i]", "expected a single value, got ${shapeOf(item)}")
            }
        }
        else -> {
            warn(path, "expected a list, got ${shapeOf(e)}")
            emptyList()
        }
    }

    // ---- coercion, one literal at a time ---------------------------------

    /** Every literal has a text form, so anything single-valued reads as a string. */
    private fun asString(lit: TomlLiteral): String = lit.content

    private fun asInt(lit: TomlLiteral, path: String): Int? = when (lit.type) {
        TomlLiteral.Type.Integer ->
            lit.toLongOrNull()?.let { narrow(it, path) }
                ?: refuse(path, "expected a whole number, got ${quote(lit.content)}")

        TomlLiteral.Type.Float ->
            lit.toDoubleOrNull()?.let { whole(it, path) }
                ?: refuse(path, "expected a whole number, got ${quote(lit.content)}")

        TomlLiteral.Type.String -> {
            val text = lit.content.trim()
            text.toLongOrNull()?.let { narrow(it, path) }
                ?: text.toDoubleOrNull()?.let { whole(it, path) }
                ?: refuse(path, "expected a whole number, got ${quote(lit.content)}")
        }

        else -> refuse(path, "expected a whole number, got ${describe(lit)}")
    }

    private fun asDouble(lit: TomlLiteral, path: String): Double? = when (lit.type) {
        // `diameter_mm = 41` rather than `41.0` is the single most likely
        // hand-edit in the whole schema. It reads as 41.0 in silence.
        TomlLiteral.Type.Float, TomlLiteral.Type.Integer ->
            lit.toDoubleOrNull()
                ?: refuse(path, "expected a number, got ${quote(lit.content)}")

        TomlLiteral.Type.String ->
            lit.content.trim().toDoubleOrNull()
                ?: refuse(path, "expected a number, got ${quote(lit.content)}")

        else -> refuse(path, "expected a number, got ${describe(lit)}")
    }

    private fun asBool(lit: TomlLiteral, path: String): Boolean? = when (lit.type) {
        TomlLiteral.Type.Boolean ->
            lit.toBooleanOrNull()
                ?: refuse(path, "expected true or false, got ${quote(lit.content)}")

        // 1 and 0 are unambiguous, and a file that says `hacking = 1` means it.
        // Anything else is a guess this refuses to make.
        TomlLiteral.Type.Integer -> when (lit.toLongOrNull()) {
            1L -> true
            0L -> false
            else -> refuse(path, "expected true or false, got ${quote(lit.content)}")
        }

        TomlLiteral.Type.String -> when (lit.content.trim().lowercase()) {
            "true" -> true
            "false" -> false
            else -> refuse(path, "expected true or false, got ${quote(lit.content)}")
        }

        else -> refuse(path, "expected true or false, got ${describe(lit)}")
    }

    private fun asDate(lit: TomlLiteral, path: String): LocalDate? {
        val parsed = when (lit.type) {
            TomlLiteral.Type.LocalDate -> lit.toLocalDateOrNull()

            // A hand-typed timestamp where a plain day belongs. SPEC-ANDROID 4:
            // worn entries and every other date are local calendar days with no
            // time and no zone, so the time is dropped rather than the value.
            TomlLiteral.Type.LocalDateTime -> lit.toLocalDateTimeOrNull()?.toLocalDate()
            TomlLiteral.Type.OffsetDateTime -> lit.toOffsetDateTimeOrNull()?.toLocalDate()

            TomlLiteral.Type.String ->
                runCatching { LocalDate.parse(lit.content.trim()) }.getOrNull()

            else -> null
        }
        return parsed
            ?: refuse(path, "expected a date such as 2024-01-31, got ${quote(lit.content)}")
    }

    // ---- helpers ---------------------------------------------------------

    private fun narrow(value: Long, path: String): Int? =
        if (value in Int.MIN_VALUE.toLong()..Int.MAX_VALUE.toLong()) value.toInt()
        else refuse(path, "whole number $value is too large to store")

    private fun whole(value: Double, path: String): Int? = when {
        value % 1.0 != 0.0 -> refuse(path, "expected a whole number, got ${trimZero(value)}")
        value < Int.MIN_VALUE.toDouble() || value > Int.MAX_VALUE.toDouble() ->
            refuse(path, "whole number ${trimZero(value)} is too large to store")
        else -> value.toInt()
    }

    private fun trimZero(value: Double) =
        if (value % 1.0 == 0.0 && value.isFinite()) value.toLong().toString() else value.toString()

    private fun quote(text: String) = "\"$text\""

    private fun describe(lit: TomlLiteral) = when (lit.type) {
        TomlLiteral.Type.Boolean -> "true or false"
        TomlLiteral.Type.Integer, TomlLiteral.Type.Float -> "a number"
        TomlLiteral.Type.String -> quote(lit.content)
        else -> "a date or time"
    }

    private fun shapeOf(e: TomlElement) = when (e) {
        is TomlTable -> "a group of settings"
        is TomlArray -> "a list"
        else -> "a single value"
    }
}

// ---------------------------------------------------------------------------
// Writing
// ---------------------------------------------------------------------------

/**
 * The model as TOML, in the order docs/schema.md presents it.
 *
 * Absent means omitted: a null field and an empty list are simply not written,
 * and a group with nothing in it produces no `[table]` header at all. A watch
 * carrying only a brand and a model is therefore a three-line file, which is
 * what SPEC-ANDROID 5.7 promises when it says saving with only those two must
 * succeed. The desktop writes empty `[case]` and `[dial]` headers instead;
 * either file loads identically on either side, so this takes the quieter one.
 *
 * `status` and each strap's `fitted` are always written, because they are the
 * two fields whose absence would be read as a value rather than as a silence.
 */
fun encodeWatch(watch: Watch): String {
    val table = watchTable {
        // TOML demands every bare key precede the first table header, or a
        // `worn = [...]` written after `[[log]]` silently becomes log[1].worn.
        // tomlkt's emitter hoists bare keys regardless of insertion order —
        // measured, not assumed, and WatchTomlTest asserts it on every write —
        // but they are written first anyway, so the file reads in schema order
        // and so a change of emitter cannot quietly cost the wear history.
        str("brand", watch.brand)
        str("model", watch.model)
        str("reference", watch.reference)
        str("nickname", watch.nickname)
        str("serial", watch.serial)
        str("group", watch.group)
        str("style", watch.style)
        str("status", watch.status)
        str("storage", watch.storage)
        int("rating", watch.rating)
        strings("tags", watch.tags)
        dates("worn", watch.worn)
        str("notes", watch.notes)
        strings("images", watch.images)

        group("movement") {
            str("caliber", watch.movement.caliber)
            str("kind", watch.movement.kind)
            dbl("power_reserve_hours", watch.movement.powerReserveHours)
            dbl("battery_life_years", watch.movement.batteryLifeYears)
            dbl("accuracy_min", watch.movement.accuracyMin)
            dbl("accuracy_max", watch.movement.accuracyMax)
            str("accuracy_unit", watch.movement.accuracyUnit)
            int("jewels", watch.movement.jewels)
            int("bph", watch.movement.bph)
            bool("hacking", watch.movement.hacking)
            bool("handwinding", watch.movement.handwinding)
            str("origin", watch.movement.origin)
        }

        group("case") {
            dbl("diameter_mm", watch.case.diameterMm)
            dbl("lug_to_lug_mm", watch.case.lugToLugMm)
            dbl("thickness_mm", watch.case.thicknessMm)
            int("lug_width_mm", watch.case.lugWidthMm)
            str("material", watch.case.material)
            str("crystal", watch.case.crystal)
            str("crown", watch.case.crown)
            str("bezel", watch.case.bezel)
            str("caseback", watch.case.caseback)
            int("water_resistance_m", watch.case.waterResistanceM)
            dbl("weight_g", watch.case.weightG)
        }

        group("dial") {
            str("colour", watch.dial.colour)
            str("material", watch.dial.material)
            str("indices", watch.dial.indices)
            str("lume", watch.dial.lume)
            strings("complications", watch.dial.complications)
        }

        group("acquisition") {
            date("date", watch.acquisition.date)
            dbl("price", watch.acquisition.price)
            str("currency", watch.acquisition.currency)
            str("seller", watch.acquisition.seller)
            str("url", watch.acquisition.url)
            str("condition", watch.acquisition.condition)
            bool("box_and_papers", watch.acquisition.boxAndPapers)
            date("warranty_until", watch.acquisition.warrantyUntil)
            dbl("target_price", watch.acquisition.targetPrice)
            date("target_date", watch.acquisition.targetDate)
        }

        group("maintenance") {
            dbl("service_interval_years", watch.maintenance.serviceIntervalYears)
            date("battery_due", watch.maintenance.batteryDue)
        }

        entries("straps", watch.straps) { strap ->
            str("material", strap.material)
            str("colour", strap.colour)
            int("width_mm", strap.widthMm)
            str("clasp", strap.clasp)
            bool("fitted", strap.fitted)
            str("image", strap.image)
        }

        entries("log", watch.log) { entry ->
            date("date", entry.date)
            str("kind", entry.kind)
            str("note", entry.note)
        }

        entries("timing", watch.timing) { entry ->
            date("date", entry.date)
            dbl("deviation_sec", entry.deviationSec)
            str("position", entry.position)
        }
    }

    val text = toml.encodeToString(TomlTable.serializer(), table)
    return if (text.endsWith("\n")) text else "$text\n"
}

/**
 * A group of key-value pairs on the way to becoming a TOML table.
 *
 * Collected into a map first so that "did anything get written?" is answerable
 * before the table is built — an all-absent group must produce no header rather
 * than an empty one.
 */
private class TableScope {
    private val values = LinkedHashMap<String, TomlElement>()

    val isEmpty: Boolean get() = values.isEmpty()

    fun str(key: String, value: String?) {
        if (value != null) values[key] = TomlLiteral(value)
    }

    fun int(key: String, value: Int?) {
        if (value != null) values[key] = TomlLiteral(value.toLong())
    }

    fun dbl(key: String, value: Double?) {
        if (value != null) values[key] = TomlLiteral(value)
    }

    fun bool(key: String, value: Boolean?) {
        if (value != null) values[key] = TomlLiteral(value)
    }

    fun date(key: String, value: LocalDate?) {
        if (value != null) values[key] = TomlLiteral(value)
    }

    fun strings(key: String, items: List<String>) {
        if (items.isEmpty()) return
        values[key] = buildTomlArray { items.forEach { element(TomlLiteral(it)) } }
    }

    fun dates(key: String, items: List<LocalDate>) {
        if (items.isEmpty()) return
        values[key] = buildTomlArray { items.forEach { element(TomlLiteral(it)) } }
    }

    /** A `[name]` table, written only if the block put something in it. */
    fun group(key: String, block: TableScope.() -> Unit) {
        val scope = TableScope().apply(block)
        if (!scope.isEmpty) values[key] = scope.build()
    }

    /** A `[[name]]` array of tables, written only if the list has entries. */
    fun <T> entries(key: String, items: List<T>, block: TableScope.(T) -> Unit) {
        if (items.isEmpty()) return
        values[key] = buildTomlArray {
            items.forEach { item -> element(TableScope().apply { block(item) }.build()) }
        }
    }

    fun build(): TomlTable = buildTomlTable {
        values.forEach { (key, value) -> element(key, value) }
    }
}

private fun watchTable(block: TableScope.() -> Unit): TomlTable = TableScope().apply(block).build()
