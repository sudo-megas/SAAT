package io.github.sudomegas.saat

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import io.github.sudomegas.saat.ui.SaatApp
import io.github.sudomegas.saat.ui.SettingsViewModel
import io.github.sudomegas.saat.ui.theme.SaatTheme

/**
 * AppCompatActivity, not ComponentActivity.
 *
 * The reason is SPEC-ANDROID hard rule 7 — the app must never take its language
 * from the system locale — and the only supported way to hold a per-app locale
 * across the whole minSdk 26 range is AppCompatDelegate.setApplicationLocales,
 * which requires this base class and a Theme.AppCompat-descended XML theme. The
 * framework's own LocaleManager is API 33+ and would leave 26-32 unserved.
 *
 * Decided in AM1 rather than AM11 because changing the base class and theme
 * parent once every screen exists is a refactor, and AM11 is the public-release
 * milestone with no slack behind it.
 */
class MainActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)

        setContent {
            val app = application as SaatApplication
            val viewModel: SettingsViewModel = viewModel(
                factory = SettingsViewModel.factory(app)
            )
            val config by viewModel.config.collectAsStateWithLifecycle()

            SaatTheme(mode = config.themeMode, dynamicColor = config.dynamicColor) {
                SaatApp(
                    app = app,
                    viewModel = viewModel,
                    // AM8: the filled widget and the "Add watch" shortcut both
                    // open the app already pointed somewhere. Read from the
                    // intent rather than held in a ViewModel so a cold start
                    // and a warm one behave the same.
                    openSlug = intent?.getStringExtra(EXTRA_WATCH_SLUG),
                    openAddWatch = intent?.action == ACTION_ADD_WATCH,
                )
            }
        }
    }

    companion object {
        /** A watch to open on launch — the widget's filled tap. */
        const val EXTRA_WATCH_SLUG = "io.github.sudomegas.saat.WATCH_SLUG"

        /** Open the add form on launch — the launcher shortcut. */
        const val ACTION_ADD_WATCH = "io.github.sudomegas.saat.ADD_WATCH"
    }
}
