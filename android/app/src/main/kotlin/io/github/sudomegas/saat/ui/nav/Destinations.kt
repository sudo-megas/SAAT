package io.github.sudomegas.saat.ui.nav

import androidx.annotation.StringRes
import io.github.sudomegas.saat.R
import kotlinx.serialization.Serializable

/**
 * The four bottom-navigation destinations, per SPEC-ANDROID 5.1.
 *
 * Type-safe navigation routes: each is a @Serializable object rather than a
 * string, so a typo is a compile error instead of a silent no-op at runtime.
 */
@Serializable
object GridRoute

@Serializable
object SpecsRoute

@Serializable
object CalendarRoute

@Serializable
object SettingsRoute

enum class TopLevelDestination(
    val route: Any,
    @param:StringRes val labelRes: Int,
) {
    GRID(GridRoute, R.string.nav_grid),
    SPECS(SpecsRoute, R.string.nav_specs),
    CALENDAR(CalendarRoute, R.string.nav_calendar),
    SETTINGS(SettingsRoute, R.string.nav_settings),
}
