package io.github.sudomegas.saat.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import io.github.sudomegas.saat.SaatApplication
import io.github.sudomegas.saat.config.AppConfig
import io.github.sudomegas.saat.config.ConfigState
import io.github.sudomegas.saat.config.ThemeMode
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/**
 * Holds the settings that AM1 ships, and writes them through to `config.toml`.
 *
 * A ViewModel rather than activity state so the choice survives rotation
 * without `android:configChanges` — the manifest deliberately does not suppress
 * recreation, because suppressing it would make the rotation-survival guarantee
 * a lie rather than a fact.
 *
 * Since AM3 this no longer holds its own copy of the config. `ConfigState` owns
 * it, because the grid's sort choice made a second writer and two snapshots of
 * a whole-file write silently overwrite each other's keys.
 */
class SettingsViewModel(
    private val configState: ConfigState,
    private val onThemeModeChanged: (ThemeMode) -> Unit,
    private val onLanguageChanged: (String) -> Unit,
) : ViewModel() {

    val config: StateFlow<AppConfig> = configState.config

    /**
     * Seeded with whatever the process-start load reported, because
     * `ConfigState` is built from that load — so a `config.toml` that could not
     * be read still reaches the shell's snackbar without a second channel.
     */
    val error: StateFlow<String?> = configState.error

    fun setThemeMode(mode: ThemeMode) {
        // Applied to the XML/AppCompat layer BEFORE it is persisted, so the
        // launch window and the Compose theme cannot disagree even briefly.
        onThemeModeChanged(mode)
        persist { it.copy(themeMode = mode) }
    }

    fun setDynamicColor(enabled: Boolean) = persist { it.copy(dynamicColor = enabled) }

    /**
     * The ONLY thing that changes the app's language — SPEC-ANDROID hard rule 7.
     *
     * Applied before it is persisted, for the same reason the theme is: the
     * apply is what the owner sees happen, and a write that failed should not
     * be able to hold the interface back. The code is a bare language tag
     * (`en`, `tr`) and reaches `AppCompatDelegate.setApplicationLocales`, which
     * is the only per-app locale mechanism that covers the whole minSdk 26
     * range — the framework's own LocaleManager is API 33+.
     *
     * Nothing here touches storage. Enum values in `watch.toml` stay canonical
     * English whatever this is set to; the Turkish build shows a Turkish label
     * for `Automatic` and still writes `Automatic`.
     */
    fun setLanguage(code: String) {
        onLanguageChanged(code)
        persist { it.copy(language = code) }
    }

    fun clearError() = configState.clearError()

    private fun persist(transform: (AppConfig) -> AppConfig) {
        viewModelScope.launch { configState.update(transform) }
    }

    companion object {
        fun factory(app: SaatApplication): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T =
                    SettingsViewModel(
                        configState = app.configState,
                        onThemeModeChanged = app::applyNightMode,
                        onLanguageChanged = app::applyLanguage,
                    ) as T
            }
    }
}
