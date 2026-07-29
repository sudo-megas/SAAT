package io.github.sudomegas.saat

import android.app.Application
import android.app.UiModeManager
import android.os.Build
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
     * Keeps the XML layer in step with the Compose theme — in both of the two
     * places that matter, which are not the same place.
     *
     * `AppCompatDelegate` drives resource resolution inside the process, so
     * `Theme.AppCompat.DayNight` picks the right `values-night/`. That is
     * necessary but not sufficient: the system draws the launch window BEFORE
     * this process exists, resolving `android:windowBackground` against the
     * DEVICE's night mode, which knows nothing about a preference stored in
     * config.toml. Measured on a real phone: with the app set to Dark on a
     * light-mode device, cold start showed the light plate for about 570 ms
     * before Compose painted dark.
     *
     * `UiModeManager.setApplicationNightMode` exists for exactly this. It tells
     * the system the app's own night mode, so the launch window is resolved
     * correctly before a line of app code runs. API 31+, hence the pair: the
     * delegate call is what works on 26-30 and still drives resources
     * everywhere.
     */
    fun applyNightMode(mode: ThemeMode) {
        AppCompatDelegate.setDefaultNightMode(
            when (mode) {
                ThemeMode.SYSTEM -> AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM
                ThemeMode.LIGHT -> AppCompatDelegate.MODE_NIGHT_NO
                ThemeMode.DARK -> AppCompatDelegate.MODE_NIGHT_YES
            }
        )

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            getSystemService(UiModeManager::class.java)?.setApplicationNightMode(
                when (mode) {
                    ThemeMode.SYSTEM -> UiModeManager.MODE_NIGHT_AUTO
                    ThemeMode.LIGHT -> UiModeManager.MODE_NIGHT_NO
                    ThemeMode.DARK -> UiModeManager.MODE_NIGHT_YES
                }
            )
        }
    }
}
