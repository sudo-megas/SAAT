package io.github.sudomegas.saat.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import io.github.sudomegas.saat.SaatApplication
import io.github.sudomegas.saat.storage.SaatPaths
import io.github.sudomegas.saat.storage.WatchRepository
import io.github.sudomegas.saat.ui.compare.ComparePage
import io.github.sudomegas.saat.ui.compare.comparePage
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn

/**
 * Two watches, read from the shared collection.
 *
 * [isMissing] rather than a blank screen, for the same reason `DetailUiState`
 * distinguishes it: either watch can be deleted while this page sits on the back
 * stack, and an empty comparison would be the app going quiet about something it
 * knows. One flag covers both sides — which of the two vanished does not change
 * what the owner can do about it, which is go back.
 */
data class CompareUiState(
    val page: ComparePage? = null,
    val isMissing: Boolean = false,
)

class CompareViewModel(
    repository: WatchRepository,
    paths: SaatPaths,
    private val leftSlug: String,
    private val rightSlug: String,
) : ViewModel() {

    val state: StateFlow<CompareUiState> = repository.state
        .map { collection ->
            val left = collection.records.firstOrNull { it.slug == leftSlug }
            val right = collection.records.firstOrNull { it.slug == rightSlug }

            CompareUiState(
                page = if (left == null || right == null) {
                    null
                } else {
                    comparePage(
                        left = left,
                        leftMedia = paths.watchMedia(leftSlug),
                        right = right,
                        rightMedia = paths.watchMedia(rightSlug),
                    )
                },
                // Only once the collection has actually been read. Before that,
                // "not found" means "not looked yet" and the screen shows
                // nothing rather than claiming the watches are gone.
                isMissing = collection.isLoaded && (left == null || right == null),
            )
        }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), CompareUiState())

    companion object {
        fun factory(
            app: SaatApplication,
            leftSlug: String,
            rightSlug: String,
        ): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T =
                    CompareViewModel(
                        repository = app.watchRepository,
                        paths = app.paths,
                        leftSlug = leftSlug,
                        rightSlug = rightSlug,
                    ) as T
            }
    }
}
