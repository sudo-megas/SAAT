package io.github.sudomegas.saat.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import io.github.sudomegas.saat.SaatApplication
import io.github.sudomegas.saat.config.ConfigState
import io.github.sudomegas.saat.storage.SaatPaths
import io.github.sudomegas.saat.storage.WatchRecord
import io.github.sudomegas.saat.storage.WatchRepository
import io.github.sudomegas.saat.storage.WatchFilter
import io.github.sudomegas.saat.storage.WatchSort
import io.github.sudomegas.saat.storage.filtered
import io.github.sudomegas.saat.ui.detail.SpecRow
import io.github.sudomegas.saat.ui.specs.SpecsPreset
import io.github.sudomegas.saat.ui.specs.specsCells
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.io.File
import java.time.LocalDate

/** One watch as a row in the Specs list, already resolved. */
data class SpecsRow(
    val slug: String,
    val brand: String,
    val model: String,
    /** `media/<slug>/<first image>`, or null when the watch has no photographs. */
    val image: File?,
    /** The active preset's fields, in its order. A null value is an em-dash. */
    val cells: List<SpecRow>,
)

data class SpecsUiState(
    val rows: List<SpecsRow> = emptyList(),
    val filter: WatchFilter = WatchFilter(),
    val preset: SpecsPreset = SpecsPreset.DEFAULT,
    val isLoaded: Boolean = false,
    val isCollectionEmpty: Boolean = false,
    val query: String = "",
    val sort: WatchSort = WatchSort.DEFAULT,
) {
    /** The collection has watches, but none match what was typed. Same rule as the grid's. */
    val hasNoMatches: Boolean
        get() = isLoaded && !isCollectionEmpty && rows.isEmpty() &&
            (query.isNotBlank() || !filter.isEmpty)
}

/**
 * The Specs list — SPEC-ANDROID 5.3.
 *
 * SORT AND SEARCH ARE AM3'S, unchanged: the same `query()` over the same
 * comparators and the same fuzzy matcher, which is why they were built in the
 * repository layer rather than in the grid's composable. This milestone's brief
 * asks for one implementation and this is it being reused, not re-derived.
 *
 * The query is per-screen and not shared with the grid, deliberately. A search
 * is a question you are asking on the screen you are looking at; carrying it
 * across a tab switch would make the other tab appear to have lost watches.
 */
class SpecsViewModel(
    repository: WatchRepository,
    private val configState: ConfigState,
    filterState: FilterState,
    private val paths: SaatPaths,
) : ViewModel() {

    private val _query = MutableStateFlow("")

    val state: StateFlow<SpecsUiState> =
        combine(
            repository.state,
            configState.config,
            _query,
            filterState.filter,
        ) { collection, config, query, filter ->
            val today = LocalDate.now()
            SpecsUiState(
                rows = collection.watches
                    .filtered(filter, query, config.sort, today)
                    .mapNotNull { it.toRow(config.specsPreset) },
                preset = config.specsPreset,
                isLoaded = collection.isLoaded,
                isCollectionEmpty = collection.isLoaded && collection.records.isEmpty(),
                query = query,
                sort = config.sort,
                filter = filter,
            )
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), SpecsUiState())

    fun setQuery(query: String) {
        _query.value = query
    }

    fun setSort(sort: WatchSort) {
        viewModelScope.launch { configState.update { it.copy(sort = sort) } }
    }

    fun setPreset(preset: SpecsPreset) {
        viewModelScope.launch { configState.update { it.copy(specsPreset = preset) } }
    }

    private fun WatchRecord.toRow(preset: SpecsPreset): SpecsRow? {
        val watch = watch ?: return null
        return SpecsRow(
            slug = slug,
            brand = watch.brand,
            model = watch.model,
            // Bare filenames in a sibling media/ tree — the same arithmetic the
            // grid card does, and for the same reasons.
            image = watch.images.firstOrNull()
                ?.let { File(paths.watchMedia(slug), File(it).name) },
            cells = specsCells(watch, preset),
        )
    }

    companion object {
        fun factory(app: SaatApplication): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T =
                    SpecsViewModel(
                        repository = app.watchRepository,
                        configState = app.configState,
                        filterState = app.filterState,
                        paths = app.paths,
                    ) as T
            }
    }
}
