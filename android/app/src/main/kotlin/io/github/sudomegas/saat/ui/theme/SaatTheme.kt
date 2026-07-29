package io.github.sudomegas.saat.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext
import io.github.sudomegas.saat.config.ThemeMode

/** True when this device can derive a palette from the user's wallpaper. */
val dynamicColorAvailable: Boolean
    get() = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S

@Composable
fun SaatTheme(
    mode: ThemeMode,
    dynamicColor: Boolean,
    content: @Composable () -> Unit,
) {
    // Reading the system dark-mode setting is deliberate and is NOT a breach of
    // SPEC-ANDROID hard rule 7. That rule governs LANGUAGE — the app must never
    // pick its UI language from the system locale. Theme is explicitly a
    // System/Light/Dark choice per SPEC-ANDROID 5.10, and "System" has to mean
    // something.
    val dark = when (mode) {
        ThemeMode.SYSTEM -> isSystemInDarkTheme()
        ThemeMode.LIGHT -> false
        ThemeMode.DARK -> true
    }

    val context = LocalContext.current
    val scheme = when {
        dynamicColor && dynamicColorAvailable ->
            if (dark) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        dark -> DefaultDark.toColorScheme(dark = true)
        else -> DefaultLight.toColorScheme(dark = false)
    }

    MaterialTheme(colorScheme = scheme, content = content)
}
