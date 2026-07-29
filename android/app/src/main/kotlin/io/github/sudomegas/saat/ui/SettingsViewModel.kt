package io.github.sudomegas.saat.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import io.github.sudomegas.saat.SaatApplication
import io.github.sudomegas.saat.config.AppConfig
import io.github.sudomegas.saat.config.ConfigStore
import io.github.sudomegas.saat.config.ThemeMode
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * Holds the settings that AM1 ships, and writes them through to `config.toml`.
 *
 * A ViewModel rather than activity state so the choice survives rotation
 * without `android:configChanges` — the manifest deliberately does not suppress
 * recreation, because suppressing it would make the rotation-survival guarantee
 * a lie rather than a fact.
 */
class SettingsViewModel(
    private val store: ConfigStore,
    private val onThemeModeChanged: (ThemeMode) -> Unit,
    initial: AppConfig,
    startupError: String?,
) : ViewModel() {

    private val _config = MutableStateFlow(initial)
    val config: StateFlow<AppConfig> = _config.asStateFlow()

    private val _error = MutableStateFlow(startupError)
    val error: StateFlow<String?> = _error.asStateFlow()

    fun setThemeMode(mode: ThemeMode) {
        onThemeModeChanged(mode)
        persist { it.copy(themeMode = mode) }
    }

    fun setDynamicColor(enabled: Boolean) = persist { it.copy(dynamicColor = enabled) }

    fun clearError() {
        _error.value = null
    }

    private fun persist(transform: (AppConfig) -> AppConfig) {
        val updated = transform(_config.value)
        _config.value = updated
        viewModelScope.launch(Dispatchers.IO) {
            try {
                store.save(updated)
            } catch (e: Exception) {
                // Hard rule 6: the message reaches the UI intact. A settings
                // write that fails silently would leave the app disagreeing
                // with its own config file on the next launch.
                _error.update { "${ConfigStore.FILE_NAME}: ${e.message ?: e::class.simpleName}" }
            }
        }
    }

    companion object {
        fun factory(app: SaatApplication): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T {
                    val loaded = app.configStore.load()
                    return SettingsViewModel(
                        store = app.configStore,
                        onThemeModeChanged = app::applyNightMode,
                        initial = loaded.config,
                        startupError = app.startupError ?: loaded.error,
                    ) as T
                }
            }
    }
}
