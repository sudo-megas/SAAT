package io.github.sudomegas.saat

import android.app.Application
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat
import io.github.sudomegas.saat.config.AppConfig
import io.github.sudomegas.saat.config.ConfigStore
import io.github.sudomegas.saat.config.ThemeMode

class SaatApplication : Application() {

    lateinit var configStore: ConfigStore
        private set

    /** Non-null when config.toml existed but could not be read (hard rule 6). */
    var startupError: String? = null
        private set

    override fun onCreate() {
        super.onCreate()
        configStore = ConfigStore(filesDir)

        val loaded = configStore.load()
        startupError = loaded.error

        applyLanguage(loaded.config.language)
        applyNightMode(loaded.config.themeMode)
    }

    /**
     * SPEC-ANDROID hard rule 7: the app never reads the system locale to choose
     * its language.
     *
     * On Android that is not something you get by doing nothing. Resource
     * resolution follows the system locale automatically the moment a
     * `values-tr/` directory exists, so the English default has to be ASSERTED
     * — explicitly, on every process start, before the first composition.
     * Doing it from AM1 means AM11 adds a picker rather than a behaviour.
     */
    fun applyLanguage(code: String) {
        AppCompatDelegate.setApplicationLocales(
            LocaleListCompat.forLanguageTags(code.ifBlank { AppConfig.DEFAULT_LANGUAGE })
        )
    }

    /**
     * Keeps the XML layer in step with the Compose theme.
     *
     * `Theme.AppCompat.DayNight` resolves `values-night/` from AppCompatDelegate's
     * night mode, not from the Compose theme. If the two disagree,
     * `android:windowBackground` resolves light while Compose paints dark, and
     * the cold-start window flashes white before the first frame.
     */
    fun applyNightMode(mode: ThemeMode) {
        AppCompatDelegate.setDefaultNightMode(
            when (mode) {
                ThemeMode.SYSTEM -> AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM
                ThemeMode.LIGHT -> AppCompatDelegate.MODE_NIGHT_NO
                ThemeMode.DARK -> AppCompatDelegate.MODE_NIGHT_YES
            }
        )
    }
}
