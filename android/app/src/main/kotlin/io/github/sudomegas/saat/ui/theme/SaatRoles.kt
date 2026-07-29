package io.github.sudomegas.saat.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * The desktop app's seven colour roles, ported verbatim.
 *
 * The desktop defines these as TOML files under `saat/resources/palettes/` and
 * the metaphor is a watch movement plate — grey nickel and warm brass, punctuated
 * by red ruby jewels. Deliberately not "near-black with a bright acid accent".
 *
 * Held in Kotlin rather than `colors.xml` for the same reason the desktop keeps
 * `tests/contrast.py` as a shared module: one implementation, so the contrast
 * test reads the exact values the app paints with. Reading them back through
 * `Resources` would need Robolectric and would let the two drift.
 * `PaletteXmlParityTest` guards the handful of values that must also exist in
 * XML.
 */
data class SaatRoles(
    /** Base background. Dark: warm-shifted charcoal, not blue-black. */
    val plate: Color,
    /** Elevated surfaces — cards, sheets, dialogs. */
    val plateHigh: Color,
    /** Hairlines, borders, dividers. Never a text background. */
    val rule: Color,
    /** Primary text. */
    val text: Color,
    /** Labels, units, absent values. */
    val textMuted: Color,
    /** The primary accent: primary buttons, active filters, focus, today. */
    val gilt: Color,
    /** Danger only: delete, unsaved-changes warning. */
    val ruby: Color,
)

/**
 * Default Light, from `saat/resources/palettes/default-light.toml`.
 *
 * `plate` and `plateHigh` sit about 2% apart, so elevation is nearly invisible
 * and the hairlines carry the structure. That is deliberate — the desktop
 * nudged `plate` from #F1EEE6 to #FAF8F5 in July 2026 because the older cream
 * read as a different colour next to the true-white elevated surfaces. Do not
 * "fix" the closeness.
 */
val DefaultLight = SaatRoles(
    plate = Color(0xFFFAF8F5),
    plateHigh = Color(0xFFFFFFFF),
    rule = Color(0xFFDAD4C5),
    text = Color(0xFF2B2822),
    textMuted = Color(0xFF70695E),
    gilt = Color(0xFF8A6A16),
    ruby = Color(0xFFA82F24),
)

/** Default Dark, from `saat/resources/palettes/default-dark.toml`. */
val DefaultDark = SaatRoles(
    plate = Color(0xFF1C1B19),
    plateHigh = Color(0xFF262421),
    rule = Color(0xFF38352F),
    text = Color(0xFFE8E4DC),
    textMuted = Color(0xFF938C81),
    gilt = Color(0xFFC9A227),
    ruby = Color(0xFFCF3931),
)
