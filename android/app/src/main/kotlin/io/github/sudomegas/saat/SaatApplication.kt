package io.github.sudomegas.saat

import android.app.Application
import android.app.UiModeManager
import android.os.Build
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat
import io.github.sudomegas.saat.config.AppConfig
import io.github.sudomegas.saat.config.ConfigStore
import io.github.sudomegas.saat.config.ThemeMode
import io.github.sudomegas.saat.storage.SaatPaths
import io.github.sudomegas.saat.storage.WatchRepository
import io.github.sudomegas.saat.storage.WatchStore
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class SaatApplication : Application() {

    lateinit var configStore: ConfigStore
        private set

    /**
     * The collection, read once here and shared by every screen from AM3 onward.
     *
     * Owned by the Application rather than by a ViewModel because the widget
     * (AM8) and the app shortcuts (AM9) need the same collection without an
     * Activity existing, and because re-reading the whole of `watches/` on every
     * rotation would be work with no purpose.
     */
    lateinit var watchRepository: WatchRepository
        private set

    /** Non-null when config.toml existed but could not be read (hard rule 6). */
    var startupError: String? = null
        private set

    /**
     * Lives as long as the process. SupervisorJob so that a failure in one
     * launched job cannot cancel the scope and silently stop the others.
     */
    private val applicationScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    override fun onCreate() {
        super.onCreate()
        configStore = ConfigStore(filesDir)

        val loaded = configStore.load()
        startupError = loaded.error

        applyLanguage(loaded.config.language)
        applyNightMode(loaded.config.themeMode)

        watchRepository = WatchRepository(WatchStore(SaatPaths(filesDir)))

        // Started here and not awaited: onCreate runs before the first frame, so
        // reading every watch.toml inline would put file I/O directly in front
        // of the launch window. The repository does its reading on the I/O
        // dispatcher and publishes when it is done; until then the collection is
        // simply not loaded yet, which is a state the UI has to handle anyway
        // because an empty collection and an unread one look different
        // (SPEC-ANDROID 5.8).
        applicationScope.launch { watchRepository.load() }
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
