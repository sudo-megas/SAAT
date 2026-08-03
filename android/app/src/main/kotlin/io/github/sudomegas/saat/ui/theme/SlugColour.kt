package io.github.sudomegas.saat.ui.theme

import androidx.compose.ui.graphics.Color
import io.github.sudomegas.saat.storage.slugHue

/**
 * A watch's identity colour — the desktop's `slug_color`, saturation and value
 * included.
 *
 * The hue comes from the model layer and is the same on both platforms; only
 * the saturation and value are the theme's business, because they depend on
 * what is underneath. The desktop deepens its chips on a dark plate so every
 * hue clears 3:1 against it, and the two pairs below are its measured ones,
 * rescaled from Qt's 0–255 to Compose's 0–1.
 *
 * IDENTITY, NEVER STATE — SPEC-ANDROID 6. This marks which watch a thing is
 * about. It is not a selection colour, not a status colour, and it never
 * appears on a grid card.
 */
fun slugColour(slug: String, isDark: Boolean): Color {
    val (saturation, value) = if (isDark) DARK_CHIP else LIGHT_CHIP
    return Color.hsv(slugHue(slug).toFloat(), saturation, value)
}

/** Qt's (150, 110) on a light plate — a deep chip against a pale surface. */
private val LIGHT_CHIP = 150f / 255f to 110f / 255f

/** Qt's (100, 255) on a dark plate, retuned by the desktop to clear 3:1. */
private val DARK_CHIP = 100f / 255f to 255f / 255f
