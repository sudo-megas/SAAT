package io.github.sudomegas.saat.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import io.github.sudomegas.saat.SaatApplication
import io.github.sudomegas.saat.storage.SaatPaths
import io.github.sudomegas.saat.storage.WatchRepository
import io.github.sudomegas.saat.ui.detail.DetailPage
import io.github.sudomegas.saat.ui.detail.detailPage
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn

/**
 * One watch's page.
 *
 * Three outcomes, deliberately distinguished rather than collapsed into "no
 * page": the watch is there, the watch is there but its file will not parse, or
 * the watch is gone. The third is reachable — AM5 adds delete, and the detail
 * page is where it is invoked from — and showing an empty page for it would be
 * the app going quiet about something it knows.
 */
data class DetailUiState(
    /** Carried so the unreadable-file notice can name the folder it is about. */
    val slug: String = "",
    val page: DetailPage? = null,
    /** The parse error, when the folder exists but its `watch.toml` does not load. */
    val loadError: String? = null,
    /** True once the collection is read and no record carries this slug. */
    val isMissing: Boolean = false,
)

class DetailViewModel(
    repository: WatchRepository,
    paths: SaatPaths,
    private val slug: String,
) : ViewModel() {

    /**
     * Derived from the shared collection rather than from a snapshot taken when
     * the page opened. "Wore this today" writes through the repository, so the
     * wear line and the twelve-month strip refresh from the same edit that
     * reaches the grid — there is no second copy of this watch to keep in step.
     */
    val state: StateFlow<DetailUiState> = repository.state
        .map { collection ->
            val record = collection.records.firstOrNull { it.slug == slug }
            DetailUiState(
                slug = slug,
                page = record?.let { detailPage(it, paths.watchMedia(slug)) },
                loadError = record?.loadError,
                isMissing = collection.isLoaded && record == null,
            )
        }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), DetailUiState(slug = slug))

    companion object {
        fun factory(app: SaatApplication, slug: String): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T =
                    DetailViewModel(
                        repository = app.watchRepository,
                        paths = app.paths,
                        slug = slug,
                    ) as T
            }
    }
}
