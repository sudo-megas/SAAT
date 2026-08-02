package io.github.sudomegas.saat.config

import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/**
 * The one owner of `config.toml` in the running app.
 *
 * Until AM3 there was exactly one writer — the settings screen — and holding the
 * whole config in that ViewModel was harmless. The grid's sort choice makes a
 * second writer, and that turns a snapshot into a bug: `ConfigStore.save` writes
 * the WHOLE file from whatever `AppConfig` it is handed, so two holders of two
 * snapshots overwrite each other's keys. Change the sort, then change the theme,
 * and the sort silently reverts.
 *
 * This is the same lost-update the repository's own `Mutex` exists to prevent
 * for watches (see `WatchRepository`), arriving by the same route: a
 * read-modify-write with a suspension point in the middle. The fix is the same
 * shape — one shared state, one mutex, one error channel — and the reason to
 * write it now rather than after AM6 adds a third writer is that the bug is
 * invisible. Nothing throws; a setting just quietly goes back to what it was.
 *
 * Held by `SaatApplication`, so both ViewModels read the same flow and neither
 * has to re-read the file. That also removes a smaller oddity: the settings
 * ViewModel used to load `config.toml` from disk again on every rotation, on top
 * of the load `onCreate` had already done.
 */
class ConfigState(
    private val store: ConfigStore,
    initial: ConfigLoad,
    private val io: CoroutineDispatcher = Dispatchers.IO,
) {

    private val _config = MutableStateFlow(initial.config)
    val config: StateFlow<AppConfig> = _config.asStateFlow()

    private val _error = MutableStateFlow(initial.error)
    val error: StateFlow<String?> = _error.asStateFlow()

    /**
     * Serialises read-modify-write. Without it, two concurrent updates both read
     * the same starting config and the second overwrites the first's key.
     */
    private val writeLock = Mutex()

    /**
     * Applies [transform] and persists the result.
     *
     * Memory first, disk immediately after — the same write-through the
     * repository uses. On failure the new value STAYS in memory and the message
     * goes to [error]: the owner asked for dark mode, and refusing to show it
     * because a file could not be written would be a second failure on top of
     * the first. Hard rule 6 is satisfied by surfacing the message, not by
     * reverting the intent.
     */
    suspend fun update(transform: (AppConfig) -> AppConfig) {
        writeLock.withLock {
            val current = _config.value
            val updated = transform(current)
            if (updated == current) return@withLock

            _config.value = updated
            try {
                withContext(io) { store.save(updated) }
            } catch (e: Exception) {
                _error.value = "${ConfigStore.FILE_NAME}: ${e.message ?: e::class.simpleName}"
            }
        }
    }

    fun clearError() {
        _error.value = null
    }
}
