package io.github.sudomegas.saat.ui.theme

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color

/**
 * Maps the desktop's seven roles onto Material 3's much larger role set.
 *
 * Five choices here are load-bearing and should not be "tidied" later:
 *
 *  - **onPrimary and onError are both `plate`**, not white and not black. Every
 *    accent-filled surface on the desktop puts the base background colour on
 *    top of it — the primary button, the destructive button, and every list and
 *    menu selection highlight. This is the most identity-defining line in the
 *    mapping.
 *  - **secondary and tertiary alias gilt.** The desktop has exactly one accent.
 *    Inventing a second hue for Android would be a new identity, not a port.
 *  - **primaryContainer is gilt**, because M3's FloatingActionButton defaults to
 *    primaryContainer/onPrimaryContainer and the Add-watch FAB is, per
 *    SPEC-ANDROID 5.1, the one primary-weight control in the app. Setting the
 *    container makes it correct by default rather than by an override every call
 *    site has to remember.
 *  - **outline is textMuted, not rule.** M3's `outline` is the *interactive*
 *    border — OutlinedTextField, OutlinedButton — and needs 3:1 to be visible.
 *    `rule` measures 1.39:1 against plate and would ship invisible text fields.
 *    `rule` belongs on `outlineVariant`: dividers and decoration, no contrast
 *    bar, which is exactly how the desktop treats it.
 *  - **surfaceTint equals surface.** M3 composites surfaceTint onto elevated
 *    surfaces at increasing alpha. With plate and plateHigh already defined as
 *    the two literal steps, a gilt tint on top would drift painted surfaces away
 *    from the constants ThemeContrastTest checks.
 */
fun SaatRoles.toColorScheme(dark: Boolean): ColorScheme {
    val base = if (dark) darkColorScheme() else lightColorScheme()
    return base.copy(
        primary = gilt,
        onPrimary = plate,
        primaryContainer = gilt,
        onPrimaryContainer = plate,
        inversePrimary = gilt,

        secondary = gilt,
        onSecondary = plate,
        secondaryContainer = gilt,
        onSecondaryContainer = plate,

        tertiary = gilt,
        onTertiary = plate,
        tertiaryContainer = gilt,
        onTertiaryContainer = plate,

        error = ruby,
        onError = plate,
        errorContainer = ruby,
        onErrorContainer = plate,

        background = plate,
        onBackground = text,
        surface = plate,
        onSurface = text,
        surfaceVariant = plateHigh,
        onSurfaceVariant = textMuted,

        surfaceContainerLowest = plate,
        surfaceContainerLow = plate,
        surfaceContainer = plateHigh,
        surfaceContainerHigh = plateHigh,
        surfaceContainerHighest = plateHigh,
        surfaceDim = plate,
        surfaceBright = plateHigh,
        surfaceTint = plate,

        outline = textMuted,
        outlineVariant = rule,

        inverseSurface = text,
        inverseOnSurface = plate,
        scrim = Color.Black,
    )
}
