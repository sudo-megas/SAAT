package io.github.sudomegas.saat.ui.form

import androidx.annotation.StringRes
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.storage.Watch

/**
 * The `enum*` suggestion lists — SPEC.md §4, ported value for value from the
 * desktop's `watch_form.py` and `list_editors.py`.
 *
 * SUGGESTIONS, NOT CONSTRAINTS. SPEC.md is explicit: "the owner will buy
 * something you did not anticipate", so every one of these feeds an editable
 * dropdown that also accepts free text and also offers whatever the collection
 * already uses. The one exception is [STATUSES], which the desktop treats as a
 * closed set and offers with no blank.
 *
 * THE VALUE AND ITS LABEL ARE DIFFERENT THINGS, and that is hard rule 7 in one
 * data class. [EnumChoice.value] is canonical English and is what reaches
 * `watch.toml`; [EnumChoice.labelRes] is what the owner reads and is what AM11
 * translates. A Turkish build will show a Turkish dropdown and write the same
 * English file the desktop writes.
 *
 * This file and the `enum_*` block in `strings.xml` were generated together from
 * one table, because ninety-nine values across seventeen lists is exactly the
 * size at which two hand-maintained copies drift — and the drift is invisible in
 * English.
 */
data class EnumChoice(
    val value: String,
    /**
     * Null for a value that is not one of the schema's own — something the
     * owner typed, harvested back out of the collection. There is no resource
     * to translate it with and there should not be: it is their word, not the
     * app's vocabulary.
     */
    @StringRes val labelRes: Int? = null,
)

private fun choice(value: String, @StringRes labelRes: Int) = EnumChoice(value, labelRes)

/** `group` — SPEC.md §4. */
val GROUPS: List<EnumChoice> = listOf(
    choice("Seiko Group", R.string.enum_group_seiko_group),
    choice("Casio", R.string.enum_group_casio),
    choice("Swatch Group", R.string.enum_group_swatch_group),
    choice("Citizen Group", R.string.enum_group_citizen_group),
    choice("Micro Brand", R.string.enum_group_micro_brand),
    choice("Independent", R.string.enum_group_independent),
    choice("Other", R.string.enum_group_other),
)

/** `style`. */
val STYLES: List<EnumChoice> = listOf(
    choice("Field", R.string.enum_style_field),
    choice("Pilot", R.string.enum_style_pilot),
    choice("Diver", R.string.enum_style_diver),
    choice("Dress", R.string.enum_style_dress),
    choice("Sport", R.string.enum_style_sport),
    choice("Chronograph", R.string.enum_style_chronograph),
    choice("GMT", R.string.enum_style_gmt),
    choice("Racing", R.string.enum_style_racing),
    choice("Skeleton", R.string.enum_style_skeleton),
    choice("Digital", R.string.enum_style_digital),
    choice("Other", R.string.enum_style_other),
)

/** `status`. The one list that is a real enum rather than a suggestion: the desktop offers no blank and neither does this. */
val STATUSES: List<EnumChoice> = listOf(
    choice("Owned", R.string.enum_status_owned),
    choice("Incoming", R.string.enum_status_incoming),
    choice("Wishlist", R.string.enum_status_wishlist),
    choice("Sold", R.string.enum_status_sold),
    choice("Gifted", R.string.enum_status_gifted),
)

/** `movement.kind`. Drives the power-reserve/battery-life swap — see [runsOnBattery]. */
val MOVEMENT_KINDS: List<EnumChoice> = listOf(
    choice("Automatic", R.string.enum_kind_automatic),
    choice("Manual", R.string.enum_kind_manual),
    choice("Automatic + Handwinding", R.string.enum_kind_automatic_handwinding),
    choice("Quartz", R.string.enum_kind_quartz),
    choice("Solar", R.string.enum_kind_solar),
    choice("Mecha-quartz", R.string.enum_kind_mecha_quartz),
    choice("Kinetic", R.string.enum_kind_kinetic),
)

/** `movement.accuracy_unit`. */
val ACCURACY_UNITS: List<EnumChoice> = listOf(
    choice("sec/day", R.string.enum_accuracy_sec_day),
    choice("sec/month", R.string.enum_accuracy_sec_month),
)

/** `case.material`. */
val CASE_MATERIALS: List<EnumChoice> = listOf(
    choice("Stainless Steel", R.string.enum_material_stainless_steel),
    choice("Titanium", R.string.enum_material_titanium),
    choice("Bronze", R.string.enum_material_bronze),
    choice("Ceramic", R.string.enum_material_ceramic),
    choice("Resin", R.string.enum_material_resin),
    choice("Silicone", R.string.enum_material_silicone),
    choice("Gold-plated", R.string.enum_material_gold_plated),
)

/** `case.crystal`. */
val CRYSTALS: List<EnumChoice> = listOf(
    choice("Sapphire", R.string.enum_crystal_sapphire),
    choice("Mineral", R.string.enum_crystal_mineral),
    choice("Hardlex", R.string.enum_crystal_hardlex),
    choice("Acrylic", R.string.enum_crystal_acrylic),
    choice("Sapphire-coated", R.string.enum_crystal_sapphire_coated),
)

/** `case.crown` — what a water-resistance rating actually depends on. */
val CROWNS: List<EnumChoice> = listOf(
    choice("Screw-down", R.string.enum_crown_screw_down),
    choice("Push-pull", R.string.enum_crown_push_pull),
    choice("Screw-down + guards", R.string.enum_crown_screw_down_guards),
)

/** `case.bezel`. */
val BEZELS: List<EnumChoice> = listOf(
    choice("Fixed", R.string.enum_bezel_fixed),
    choice("Unidirectional", R.string.enum_bezel_unidirectional),
    choice("Bidirectional", R.string.enum_bezel_bidirectional),
    choice("Tachymeter", R.string.enum_bezel_tachymeter),
    choice("GMT", R.string.enum_bezel_gmt),
    choice("None", R.string.enum_bezel_none),
)

/** `case.caseback`. */
val CASEBACKS: List<EnumChoice> = listOf(
    choice("Solid", R.string.enum_caseback_solid),
    choice("Exhibition", R.string.enum_caseback_exhibition),
    choice("Engraved", R.string.enum_caseback_engraved),
)

/** `dial.indices`. */
val INDICES: List<EnumChoice> = listOf(
    choice("Applied", R.string.enum_indices_applied),
    choice("Printed", R.string.enum_indices_printed),
    choice("Arabic", R.string.enum_indices_arabic),
    choice("Roman", R.string.enum_indices_roman),
    choice("Mixed", R.string.enum_indices_mixed),
    choice("Inverted", R.string.enum_indices_inverted),
    choice("None", R.string.enum_indices_none),
)

/** `dial.complications` — a list field, so this feeds a chooser rather than a single dropdown. */
val COMPLICATIONS: List<EnumChoice> = listOf(
    choice("Date", R.string.enum_complication_date),
    choice("Day-Date", R.string.enum_complication_day_date),
    choice("GMT", R.string.enum_complication_gmt),
    choice("Chronograph", R.string.enum_complication_chronograph),
    choice("Power Reserve", R.string.enum_complication_power_reserve),
    choice("Moonphase", R.string.enum_complication_moonphase),
    choice("Open-Heart", R.string.enum_complication_open_heart),
    choice("Small Seconds", R.string.enum_complication_small_seconds),
    choice("Alarm", R.string.enum_complication_alarm),
)

/** `straps[].material`. */
val STRAP_MATERIALS: List<EnumChoice> = listOf(
    choice("Leather", R.string.enum_strapmaterial_leather),
    choice("Calf Leather", R.string.enum_strapmaterial_calf_leather),
    choice("Nylon", R.string.enum_strapmaterial_nylon),
    choice("NATO", R.string.enum_strapmaterial_nato),
    choice("Silicone", R.string.enum_strapmaterial_silicone),
    choice("Rubber", R.string.enum_strapmaterial_rubber),
    choice("FKM", R.string.enum_strapmaterial_fkm),
    choice("Canvas", R.string.enum_strapmaterial_canvas),
    choice("Steel Bracelet", R.string.enum_strapmaterial_steel_bracelet),
    choice("Mesh", R.string.enum_strapmaterial_mesh),
)

/** `straps[].clasp`. */
val CLASPS: List<EnumChoice> = listOf(
    choice("Pin Buckle", R.string.enum_clasp_pin_buckle),
    choice("Deployant", R.string.enum_clasp_deployant),
    choice("Butterfly", R.string.enum_clasp_butterfly),
    choice("Ratcheting", R.string.enum_clasp_ratcheting),
)

/** `acquisition.condition`. */
val CONDITIONS: List<EnumChoice> = listOf(
    choice("New", R.string.enum_condition_new),
    choice("Pre-owned", R.string.enum_condition_pre_owned),
)

/** `log[].kind`. `Service` is the one the app reads rather than merely displays — see `nextServiceDue`. */
val LOG_KINDS: List<EnumChoice> = listOf(
    choice("Service", R.string.enum_logkind_service),
    choice("Battery", R.string.enum_logkind_battery),
    choice("Regulation", R.string.enum_logkind_regulation),
    choice("Strap Swap", R.string.enum_logkind_strap_swap),
    choice("Note", R.string.enum_logkind_note),
)

/** `timing[].position`. */
val TIMING_POSITIONS: List<EnumChoice> = listOf(
    choice("Dial Up", R.string.enum_position_dial_up),
    choice("Dial Down", R.string.enum_position_dial_down),
    choice("Crown Up", R.string.enum_position_crown_up),
    choice("Crown Down", R.string.enum_position_crown_down),
    choice("Crown Left", R.string.enum_position_crown_left),
    choice("Worn", R.string.enum_position_worn),
)

/**
 * Every value this collection already uses for one field, canonical and sorted.
 *
 * The second half of SPEC.md §4's rule: the dropdown offers "the listed values
 * plus every value already used elsewhere in the collection". Read straight off
 * the loaded watches, never translated — these came from disk and go back to
 * disk unchanged.
 */
fun existingValues(watches: List<Watch>, of: (Watch) -> String?): List<String> =
    watches.mapNotNull { of(it)?.trim()?.takeIf(String::isNotEmpty) }
        .distinct()
        .sorted()

/** The same, for a field that is itself a list. */
fun existingListValues(watches: List<Watch>, of: (Watch) -> List<String>): List<String> =
    watches.flatMap(of).mapNotNull { it.trim().takeIf(String::isNotEmpty) }
        .distinct()
        .sorted()

/**
 * Suggestions first, then whatever the collection adds that is not already
 * among them — the order `suggested_combo` builds, and the reason it is that
 * order: the schema's own vocabulary should be the first thing offered, and a
 * one-off value the owner typed last year should not push it down the list.
 *
 * Compared case-insensitively so a collection carrying `stainless steel` does
 * not offer it a second time beside `Stainless Steel`.
 */
fun List<EnumChoice>.plusExisting(existing: List<String>): List<EnumChoice> {
    val known = mapTo(mutableSetOf()) { it.value.lowercase() }
    return this + existing.filterNot { it.lowercase() in known }.map { EnumChoice(it) }
}

/**
 * Quartz and Solar, and nothing else guessed at — the desktop's
 * `QUARTZ_LIKE_KINDS`, compared against the canonical value.
 *
 * Mecha-quartz and Kinetic carry a battery too, but they also have a mainspring
 * or a rotor, and which figure their owner tracks is theirs to say. Trimmed and
 * case-folded because `kind` is free text: this list suggests, it does not
 * constrain.
 */
fun runsOnBattery(kind: String?): Boolean =
    kind?.trim()?.lowercase() in setOf("quartz", "solar")
