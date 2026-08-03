package io.github.sudomegas.saat

import android.app.Application
import android.app.UiModeManager
import android.os.Build
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat
import coil3.ImageLoader
import coil3.PlatformContext
import coil3.SingletonImageLoader
import coil3.disk.DiskCache
import io.github.sudomegas.saat.config.AppConfig
import io.github.sudomegas.saat.config.ConfigState
import io.github.sudomegas.saat.config.ConfigStore
import io.github.sudomegas.saat.config.ThemeMode
import io.github.sudomegas.saat.storage.SaatPaths
import io.github.sudomegas.saat.storage.WatchRepository
import io.github.sudomegas.saat.storage.WatchStore
import io.github.sudomegas.saat.ui.FilterState
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import okio.Path.Companion.toOkioPath

class SaatApplication : Application(), SingletonImageLoader.Factory {

    lateinit var configStore: ConfigStore
        private set

    /**
     * The single owner of `config.toml` while the app runs.
     *
     * AM3 gave the grid a sort preference, making a second writer. Since
     * `ConfigStore.save` writes the whole file from one `AppConfig`, two holders
     * of two snapshots would silently overwrite each other's keys — so both
     * ViewModels share this instead.
     */
    lateinit var configState: ConfigState
        private set

    /**
     * Where everything on disk lives, held rather than derived twice.
     *
     * The grid needs it to turn a watch's bare image filename into a real file
     * under `media/<slug>/`, and the repository deliberately keeps its store
     * private — a screen has no business reaching the writing layer through it.
     * So the paths are a field the same way `configStore` is, handed to the
     * ViewModel by its factory.
     */
    lateinit var paths: SaatPaths
        private set

    /**
     * The one filter, shared by the Grid, the Specs list and — from AM7 — the
     * calendar's picker. Held here for the same reason the collection is: it
     * belongs to the app, not to whichever screen happens to be on top.
     */
    val filterState: FilterState = FilterState()

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
        configState = ConfigState(configStore, loaded)

        applyLanguage(loaded.config.language)
        applyNightMode(loaded.config.themeMode)

        paths = SaatPaths(filesDir)
        watchRepository = WatchRepository(WatchStore(paths))

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
     * SPEC-ANDROID hard rule 8: no derived files inside `watches/`.
     *
     * Coil's default disk cache already lands in `cacheDir`, but a rule this
     * load-bearing should not be satisfied by inheriting a library default that
     * a future version is free to change. Naming the directory says the app
     * decided it. `cacheDir` is disposable at any moment, never backed up
     * (`backup_rules.xml` includes `watches` and `config.toml` and nothing
     * else) and never exported, which is exactly what a thumbnail deserves.
     *
     * No network component is configured because there is nothing to fetch:
     * every model handed to Coil is a local `File` under `media/<slug>/`.
     */
    override fun newImageLoader(context: PlatformContext): ImageLoader =
        ImageLoader.Builder(context)
            .diskCache {
                DiskCache.Builder()
                    .directory(cacheDir.resolve("image_cache").toOkioPath())
                    .build()
            }
            .build()

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
