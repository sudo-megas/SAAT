package io.github.sudomegas.saat.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import io.github.sudomegas.saat.SaatApplication
import io.github.sudomegas.saat.storage.CollectionSummary
import io.github.sudomegas.saat.storage.Facet
import io.github.sudomegas.saat.storage.FacetKind
import io.github.sudomegas.saat.storage.WatchFilter
import io.github.sudomegas.saat.storage.WatchRepository
import io.github.sudomegas.saat.storage.facets
import io.github.sudomegas.saat.storage.matches
import io.github.sudomegas.saat.storage.summarise
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import java.time.LocalDate

data class FiltersUiState(
    val filter: WatchFilter = WatchFilter(),
    val facets: List<Facet> = emptyList(),
    val summary: CollectionSummary = CollectionSummary(0, emptyList(), emptyList()),
)

/**
 * The filter sheet, shared by the Grid and the Specs list.
 *
 * ONE ViewModel for the sheet rather than one per screen, because there is one
 * filter and one collection to count against. Two would be two places for the
 * facet arithmetic to drift, which is what this milestone's brief means by not
 * implementing filters twice.
 *
 * The summary is computed over the FILTERED collection, not the whole one: it
 * is the footer of the sheet doing the filtering, and a total that ignored the
 * facets above it would be answering a question nobody asked.
 */
class FiltersViewModel(
    repository: WatchRepository,
    private val filterState: FilterState,
) : ViewModel() {

    val state: StateFlow<FiltersUiState> =
        combine(repository.state, filterState.filter) { collection, filter ->
            val today = LocalDate.now()
            val watches = collection.watches.mapNotNull { it.watch }

            FiltersUiState(
                filter = filter,
                facets = watches.facets(filter, today),
                summary = watches.filter { it.matches(filter, today) }.summarise(),
            )
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), FiltersUiState())

    fun toggle(kind: FacetKind, value: String) = filterState.toggle(kind, value)

    fun remove(kind: FacetKind, value: String) = filterState.remove(kind, value)

    fun clear() = filterState.clear()

    companion object {
        fun factory(app: SaatApplication): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T =
                    FiltersViewModel(
                        repository = app.watchRepository,
                        filterState = app.filterState,
                    ) as T
            }
    }
}
