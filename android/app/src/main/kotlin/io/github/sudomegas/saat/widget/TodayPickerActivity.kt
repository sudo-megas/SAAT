package io.github.sudomegas.saat.widget

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.appcompat.app.AppCompatActivity
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import io.github.sudomegas.saat.SaatApplication
import io.github.sudomegas.saat.ui.CalendarViewModel
import io.github.sudomegas.saat.ui.SettingsViewModel
import io.github.sudomegas.saat.ui.screens.DayPicker
import io.github.sudomegas.saat.ui.theme.SaatTheme
import java.time.LocalDate

/**
 * Today's picker, and nothing else — SPEC-ANDROID 5.9.
 *
 * A LIGHTWEIGHT ACTIVITY, not the app shell, and the brief asks for exactly
 * that. The whole point of the widget and the shortcut is that logging today
 * never requires opening the app; dropping the owner on the grid to navigate to
 * a calendar would give that back at the last step.
 *
 * It hosts AM7's own picker sheet rather than a second one. Which watch was on
 * the wrist is the same question here as it is on the calendar, and asking it
 * twice in two places is how the two answers eventually differ.
 *
 * AppCompatActivity for the same reason MainActivity is one: hard rule 7's
 * per-app locale needs this base class and a Theme.AppCompat-descended theme,
 * and an activity that opted out would render in the system language.
 */
class TodayPickerActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            val app = application as SaatApplication
            val settings: SettingsViewModel = viewModel(factory = SettingsViewModel.factory(app))
            val config by settings.config.collectAsStateWithLifecycle()

            val calendar: CalendarViewModel = viewModel(factory = CalendarViewModel.factory(app))
            val watches by calendar.pickerWatches.collectAsStateWithLifecycle()
            val query by calendar.pickerQuery.collectAsStateWithLifecycle()
            val state by calendar.state.collectAsStateWithLifecycle()

            val today = LocalDate.now()

            SaatTheme(mode = config.themeMode, dynamicColor = config.dynamicColor) {
                DayPicker(
                    dates = listOf(today),
                    watches = watches,
                    query = query,
                    currentSlug = state.days[today]?.slug,
                    onQueryChange = calendar::setPickerQuery,
                    // Straight through AM4b's assignWorn, like every other wear
                    // entry point. The activity finishes either way: it exists
                    // to answer one question, and it is answered.
                    onPick = { slug ->
                        calendar.assignToday(slug)
                        finish()
                    },
                    onClear = {
                        calendar.clearToday()
                        finish()
                    },
                    onDismiss = ::finish,
                )
            }
        }
    }
}
