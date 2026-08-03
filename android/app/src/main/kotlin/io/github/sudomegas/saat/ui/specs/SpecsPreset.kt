package io.github.sudomegas.saat.ui.specs

import androidx.annotation.StringRes
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.effectiveWidthMm
import io.github.sudomegas.saat.ui.detail.SpecRow
import io.github.sudomegas.saat.ui.detail.SpecValue
import io.github.sudomegas.saat.ui.detail.acquisitionRows
import io.github.sudomegas.saat.ui.detail.caseRows
import io.github.sudomegas.saat.ui.detail.dialRows
import io.github.sudomegas.saat.ui.detail.movementRows

/**
 * The Specs list's preset switcher — SPEC-ANDROID 5.3.
 *
 * The desktop's dense table cannot survive a six-inch portrait screen, so the
 * columns become one family of attributes at a time. The point of the table
 * survives even though its shape did not: studying the whole collection against
 * one set of fields, rather than one watch against all of them.
 *
 * EVERY CELL IS BUILT BY AM4'S OWN ROW BUILDERS. A preset is a SELECTION from
 * `movementRows`, `caseRows`, `dialRows` and `acquisitionRows` — not a second
 * set of field definitions. So the em-dash for an absent value, the metres-and-
 * bar water resistance, the derived hertz and the Quartz/Solar swap all behave
 * here exactly as they do on the detail page, because they are the same code.
 * Two implementations of "how do you render a lug width" is precisely the drift
 * this milestone's brief warns about.
 *
 * [token] is what reaches `config.toml`, so renaming a constant cannot silently
 * invalidate a stored preference — the same contract `WatchSort` keeps.
 */
enum class SpecsPreset(val token: String, @param:StringRes val labelRes: Int) {
    IDENTITY("identity", R.string.screen_specs_preset_identity),
    MOVEMENT("movement", R.string.screen_specs_preset_movement),
    CASE("case", R.string.screen_specs_preset_case),
    DIAL("dial", R.string.screen_specs_preset_dial),
    STRAPS("straps", R.string.screen_specs_preset_straps),
    ACQUISITION("acquisition", R.string.screen_specs_preset_acquisition),
    ;

    companion object {
        val DEFAULT: SpecsPreset = IDENTITY

        /** Unknown tokens fall back rather than throwing — see `WatchSort.fromToken`. */
        fun fromToken(token: String?): SpecsPreset =
            entries.firstOrNull { it.token == token } ?: DEFAULT
    }
}

/**
 * The fields one preset shows, in order.
 *
 * Chosen for a phone rather than lifted wholesale from the schema group: four
 * or five cells is what fits across a 360dp screen without any of them becoming
 * an ellipsis, and each preset keeps the fields that actually distinguish
 * watches from one another when you read down a column.
 *
 *  - IDENTITY — reference, style, group, status. The filing fields, and the
 *    only preset with no figures in it; it is first because it is the one that
 *    answers "which watch is this" rather than "what is it like".
 *  - MOVEMENT — kind, caliber, the reserve/battery figure, frequency. Jewels and
 *    origin were cut: interesting on a page, not what anyone scans a list for.
 *  - CASE — diameter, lug-to-lug, thickness, lug width, water resistance. Five
 *    figures, all in the same units, which is the preset the tabular alignment
 *    exists for: this is the one an owner reads down to decide what fits.
 *  - DIAL — colour, indices, lume, complications.
 *  - STRAPS — what is fitted, its width, and how many straps the watch has. The
 *    only preset whose fields are not a schema group, because straps are a list
 *    and a list does not have "the" value; see [strapCells].
 *  - ACQUISITION — date, price, condition, warranty. What a collection is worth
 *    and when it arrived.
 */
private val PRESET_FIELDS: Map<SpecsPreset, List<List<Int>>> = mapOf(
    SpecsPreset.MOVEMENT to listOf(
        listOf(R.string.field_kind),
        listOf(R.string.field_caliber),
        // ONE COLUMN, two possible fields. `movementRows` normally emits
        // whichever the movement kind calls for — but it emits BOTH when a
        // watch records both, which is legitimate for a Spring Drive or a
        // Mecha-quartz and would make this row a cell wider than its
        // neighbours. A column that is five wide on one row and four on the
        // next is exactly the misalignment the preset exists to prevent, so
        // this slot takes the first of the two that is present.
        listOf(R.string.field_power_reserve, R.string.field_battery_life),
        listOf(R.string.field_frequency),
    ),
    SpecsPreset.CASE to listOf(
        listOf(R.string.field_diameter),
        listOf(R.string.field_lug_to_lug),
        listOf(R.string.field_thickness),
        listOf(R.string.field_lug_width),
        listOf(R.string.field_water_resistance),
    ),
    SpecsPreset.DIAL to listOf(
        listOf(R.string.field_dial_colour),
        listOf(R.string.field_indices),
        listOf(R.string.field_lume),
        listOf(R.string.field_complications),
    ),
    SpecsPreset.ACQUISITION to listOf(
        listOf(R.string.field_acquired),
        listOf(R.string.field_price),
        listOf(R.string.field_condition),
        listOf(R.string.field_warranty_until),
    ),
)

/**
 * One row's worth of cells for the active preset.
 *
 * A cell with a null value is an ABSENT field and renders as the muted em-dash.
 * It is never dropped: SPEC-ANDROID 5.3's list is a table in spirit, and a row
 * that quietly grew shorter because a watch is missing a thickness would break
 * the alignment the preset exists to provide — which is also this milestone's
 * "a row never collapses or hides because a value is missing".
 */
fun specsCells(watch: Watch, preset: SpecsPreset): List<SpecRow> = when (preset) {
    SpecsPreset.IDENTITY -> identityCells(watch)
    SpecsPreset.STRAPS -> strapCells(watch)
    SpecsPreset.MOVEMENT -> movementRows(watch).select(preset)
    SpecsPreset.CASE -> caseRows(watch).select(preset)
    SpecsPreset.DIAL -> dialRows(watch).select(preset)
    SpecsPreset.ACQUISITION -> acquisitionRows(watch).select(preset)
}

/**
 * The preset's columns, in the preset's order, taken from a full row list.
 *
 * ONE CELL PER COLUMN, ALWAYS — that is what keeps every row the same width and
 * the figures aligned down the list. A column names one field or a short list of
 * alternatives; the first alternative the row list actually emitted wins, and if
 * it emitted none the column is still there, carrying null, which renders as the
 * muted em-dash.
 */
private fun List<SpecRow>.select(preset: SpecsPreset): List<SpecRow> {
    val byLabel = associateBy { it.labelRes }
    return PRESET_FIELDS.getValue(preset).map { alternatives ->
        alternatives.firstNotNullOfOrNull { byLabel[it] } ?: SpecRow(alternatives.first(), null)
    }
}

/**
 * Identity has no row builder on the detail page — it is a header line there,
 * not a labelled group — so this is the one preset whose cells are built here.
 * The values are the owner's own words throughout, which is why every one of
 * them is [SpecValue.Plain].
 */
private fun identityCells(watch: Watch): List<SpecRow> = listOf(
    SpecRow(R.string.field_reference, watch.reference.plainOrNull()),
    SpecRow(R.string.field_style, watch.style.plainOrNull()),
    SpecRow(R.string.field_group, watch.group.plainOrNull()),
    SpecRow(R.string.field_status, watch.status.plainOrNull()),
)

/**
 * Straps are a list, so there is no single strap to show — the cells answer the
 * three questions a list can answer at a glance.
 *
 * "Fitted" is the strap currently on the watch, which is the one the owner is
 * actually looking at; its width falls back to the case's lug width exactly as
 * `effectiveWidthMm` does everywhere else. The count is the whole point of the
 * column when reading down a collection: it is how you notice which watches you
 * have never bought a second strap for.
 */
private fun strapCells(watch: Watch): List<SpecRow> {
    val fitted = watch.straps.firstOrNull { it.fitted }
    val description = listOfNotNull(fitted?.material, fitted?.colour)
        .mapNotNull { it.trim().takeIf(String::isNotEmpty) }

    return listOf(
        SpecRow(
            R.string.field_strap_fitted,
            description.takeIf { it.isNotEmpty() }?.let { SpecValue.Plain(it.joinToString(" · ")) },
        ),
        SpecRow(
            R.string.field_strap_width,
            fitted?.effectiveWidthMm(watch)?.let {
                SpecValue.Resource(R.string.field_value_mm, listOf(it.toString()))
            },
        ),
        SpecRow(
            R.string.field_strap_count,
            // Zero is a value here, not an absence: "this watch has no straps
            // recorded" is exactly what the column is for.
            SpecValue.Plain(watch.straps.size.toString()),
        ),
    )
}

private fun String?.plainOrNull(): SpecValue? =
    this?.trim()?.takeIf { it.isNotEmpty() }?.let(SpecValue::Plain)
