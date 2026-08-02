package io.github.sudomegas.saat.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import io.github.sudomegas.saat.SaatApplication
import io.github.sudomegas.saat.storage.SaatPaths
import io.github.sudomegas.saat.storage.WatchRecord
import io.github.sudomegas.saat.storage.WatchRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import java.io.File

/**
 * One card's worth of a watch, already resolved.
 *
 * The grid is handed files and strings, never a `Watch` and never `SaatPaths`.
 * That keeps path arithmetic — which knows about the `media/` split and about
 * `images` holding bare filenames — in one place that a plain JVM test can
 * reach, instead of scattered through composables that would need a device.
 */
data class WatchCard(
    val slug: String,
    val brand: String,
    val model: String,
    val style: String?,
    val movementKind: String?,
    val diameterMm: Double?,
    val lugWidthMm: Int?,
    /** `media/<slug>/<first image>`, or null when the watch has no photographs. */
    val image: File?,
)

/**
 * A file the loader could not read, ready to name in the notice.
 *
 * [slug] is null for the one record that is not a watch at all: when `watches/`
 * itself exists but will not list, `WatchStore` produces a record standing for
 * the whole collection. It carries the directory's own name, so a naive UI
 * would announce a watch called "watches".
 */
data class LoadFailure(
    val key: String,
    val slug: String?,
    val message: String,
)

data class GridUiState(
    val cards: List<WatchCard> = emptyList(),
    val isLoaded: Boolean = false,
    val isCollectionEmpty: Boolean = false,
    val failures: List<LoadFailure> = emptyList(),
)

class GridViewModel(
    private val repository: WatchRepository,
    private val paths: SaatPaths,
) : ViewModel() {

    /**
     * Keys of notices the owner has waved away.
     *
     * Keyed by slug AND message, so re-reading the collection keeps a dismissed
     * error dismissed while a NEW error on the same file appears again. Held in
     * the ViewModel, so it survives rotation but not process death — a notice
     * about a file that is still broken is worth showing again on a fresh
     * launch, and pretending otherwise would need somewhere to persist it that
     * hard rule 4 does not give us.
     */
    private val _dismissed = MutableStateFlow<Set<String>>(emptySet())

    val state: StateFlow<GridUiState> =
        combine(repository.state, _dismissed) { collection, dismissed ->
            // watches/failures are uncached get() filters over records
            // (WatchRepository), so each is read exactly once per emission.
            val loaded = collection.watches
            val broken = collection.failures

            GridUiState(
                cards = loaded.mapNotNull { it.toCard(paths) },
                isLoaded = collection.isLoaded,
                // Empty means empty, not "nothing readable". A collection of
                // three malformed files is not an invitation to add your first
                // watch — it is three problems, and the notice says so.
                isCollectionEmpty = collection.isLoaded && collection.records.isEmpty(),
                failures = broken.map { it.toFailure(paths) }
                    .filterNot { it.key in dismissed },
            )
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), GridUiState())

    fun dismissFailures() {
        _dismissed.value = _dismissed.value + state.value.failures.map { it.key }
    }

    companion object {
        fun factory(app: SaatApplication): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T =
                    GridViewModel(
                        repository = app.watchRepository,
                        paths = app.paths,
                    ) as T
            }
    }
}

private fun WatchRecord.toCard(paths: SaatPaths): WatchCard? {
    val loaded = watch ?: return null
    return WatchCard(
        slug = slug,
        brand = loaded.brand,
        model = loaded.model,
        style = loaded.style,
        movementKind = loaded.movement.kind,
        diameterMm = loaded.case.diameterMm,
        lugWidthMm = loaded.case.lugWidthMm,
        // images holds BARE FILENAMES (SPEC-ANDROID 3) and photographs live in
        // the sibling media/ tree, not in the record's own directory. File(it).name
        // strips any directory part a hand-edited file could have put there.
        //
        // Deliberately not stat-ed: checking existence here would be disk I/O per
        // card on the main thread, on every emission. A missing file simply fails
        // to decode and the card falls back to the placeholder tile.
        image = loaded.images.firstOrNull()
            ?.let { File(paths.watchMedia(slug), File(it).name) },
    )
}

private fun WatchRecord.toFailure(paths: SaatPaths): LoadFailure {
    // Compared as a directory, not by the string "watches": slugify("Watches",…)
    // can legitimately produce the slug `watches` for a real watch, and a string
    // test would one day suppress a genuine error.
    val isCollectionFolder = dir == paths.watchesDir
    return LoadFailure(
        key = "$slug|$loadError",
        slug = if (isCollectionFolder) null else slug,
        message = loadError.orEmpty(),
    )
}
