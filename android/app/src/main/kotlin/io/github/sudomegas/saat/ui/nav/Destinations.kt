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

/**
 * The first destination that carries an argument, hence a `data class` rather
 * than an `object` — navigation-compose's type-safe API builds its route from
 * the serializer either way, and the argument is read back with
 * `backStackEntry.toRoute<DetailRoute>()`.
 *
 * Not a member of [TopLevelDestination]: SPEC-ANDROID 5.1 pushes detail, form
 * and compare above the tabs as full screens, so this has no bottom-bar entry
 * and the bar is hidden entirely while it is on top.
 */
@Serializable
data class DetailRoute(val slug: String)

/**
 * The add/edit form — SPEC-ANDROID 5.7's "the same screen serves add and edit".
 *
 * [slug] null is ADD. That is why it is nullable rather than two routes: two
 * routes would be two places to keep the argument list right, and the screen
 * itself differs only in where its initial state comes from.
 */
@Serializable
data class FormRoute(val slug: String? = null)

enum class TopLevelDestination(
    val route: Any,
    @param:StringRes val labelRes: Int,
) {
    GRID(GridRoute, R.string.nav_grid),
    SPECS(SpecsRoute, R.string.nav_specs),
    CALENDAR(CalendarRoute, R.string.nav_calendar),
    SETTINGS(SettingsRoute, R.string.nav_settings),
}
