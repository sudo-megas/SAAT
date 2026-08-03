package io.github.sudomegas.saat.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import io.github.sudomegas.saat.SaatApplication
import io.github.sudomegas.saat.storage.SaatPaths
import io.github.sudomegas.saat.storage.WatchRepository
import io.github.sudomegas.saat.ui.detail.CompatibleStrapCard
import io.github.sudomegas.saat.ui.detail.DetailPage
import io.github.sudomegas.saat.ui.detail.MaintenanceNotice
import io.github.sudomegas.saat.ui.detail.WearStats
import io.github.sudomegas.saat.ui.detail.compatibleStrapCards
import io.github.sudomegas.saat.ui.detail.detailPage
import io.github.sudomegas.saat.ui.detail.maintenanceNotices
import io.github.sudomegas.saat.ui.detail.wearStats
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.time.LocalDate

/**
 * One watch's page.
 *
 * Three outcomes, deliberately distinguished rather than collapsed into "no
 * page": the watch is there, the watch is there but its file will not parse, or
 * the watch is gone. The third is reachable — AM5 adds delete, and this page is
 * where it is invoked from — and showing an empty page for it would be the app
 * going quiet about something it knows.
 */
data class DetailUiState(
    /** Carried so the unreadable-file notice can name the folder it is about. */
    val slug: String = "",
    val page: DetailPage? = null,
    /** Null for a watch that has never been worn — the line and strip are hidden together. */
    val wear: WearStats? = null,
    /** Empty for the great majority of watches — AM9b's silence is the default. */
    val maintenance: List<MaintenanceNotice> = emptyList(),
    /** Straps on OTHER watches that fit this one — AM9c. Empty hides the section. */
    val compatibleStraps: List<CompatibleStrapCard> = emptyList(),
    /** The parse error, when the folder exists but its `watch.toml` does not load. */
    val loadError: String? = null,
    /** True once the collection is read and no record carries this slug. */
    val isMissing: Boolean = false,
)

/**
 * What to say after a tap on "Wore this today".
 *
 * A second tap the same day is a VISIBLE no-op — SPEC-ANDROID 5.6 asks for
 * exactly that, and a button that silently did nothing would be
 * indistinguishable from a button that did not work.
 */
sealed interface WearMessage {
    data object Recorded : WearMessage
    data object AlreadyRecorded : WearMessage

    /**
     * The one-watch-per-day rule moved today off another watch. The MOVE is
     * silent — no prompt, no confirmation, matching the desktop — but saying so
     * afterwards is not the same as asking permission first, and a day
     * disappearing from another watch with no word at all is how an owner comes
     * to distrust their own records.
     */
    data class Moved(val from: String) : WearMessage
}

class DetailViewModel(
    private val repository: WatchRepository,
    paths: SaatPaths,
    private val slug: String,
    /**
     * Injected rather than called inline, the convention `Derived` set: every
     * wear figure is a question about a date, and a clock read from inside is a
     * test that is true only on the day it was written.
     */
    private val today: () -> LocalDate = LocalDate::now,
) : ViewModel() {

    private val _message = MutableStateFlow<WearMessage?>(null)

    /** Shown once, then cleared by the screen. Same shape as `SettingsViewModel.error`. */
    val message: StateFlow<WearMessage?> = _message.asStateFlow()

    /**
     * Derived from the shared collection rather than from a snapshot taken when
     * the page opened. "Wore this today" writes through the repository, so the
     * wear line and the twelve-month strip refresh from the same edit that
     * reaches the grid — there is no second copy of this watch to keep in step.
     */
    val state: StateFlow<DetailUiState> = repository.state
        .map { collection ->
            val record = collection.records.firstOrNull { it.slug == slug }
            val watch = record?.watch
            // One clock read for the whole emission, so the wear line and the
            // maintenance line can never disagree about what day it is.
            val now = today()
            DetailUiState(
                slug = slug,
                page = record?.let { detailPage(it, paths.watchMedia(slug)) },
                wear = watch?.let { wearStats(it, now) },
                maintenance = watch?.let { maintenanceNotices(it, now) }.orEmpty(),
                // Over every record, because the answer is about the collection
                // rather than about this watch — the one thing on this page a
                // single record cannot supply.
                compatibleStraps = record?.let {
                    compatibleStrapCards(it, collection.records, paths::watchMedia)
                }.orEmpty(),
                loadError = record?.loadError,
                isMissing = collection.isLoaded && record == null,
            )
        }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), DetailUiState(slug = slug))

    /**
     * Record today for this watch, through the repository's single wear path.
     *
     * The date is read HERE and handed down, so the whole operation refers to
     * one calendar day even if it straddles midnight — reading the clock again
     * inside the repository could strip a day from another watch and add a
     * different one to this.
     */
    fun woreToday() {
        viewModelScope.launch {
            val assignment = repository.assignWorn(slug, listOf(today())) ?: return@launch
            val movedFrom = assignment.takenFrom.keys.firstOrNull()

            _message.value = when {
                movedFrom != null -> WearMessage.Moved(displayName(movedFrom))
                assignment.changedNothing -> WearMessage.AlreadyRecorded
                else -> WearMessage.Recorded
            }
        }
    }

    fun clearMessage() {
        _message.value = null
    }

    /**
     * Move this watch to `backups/deleted/` — SPEC-ANDROID 5.7 item 10.
     *
     * ITS WEAR HISTORY GOES WITH IT, and that needs no code at all: `worn` lives
     * in the watch's own file and nowhere else, so a watch folder is already a
     * complete record. That is the desktop rule the brief cites, and it is the
     * payoff for never having centralised a date-to-watch index anywhere.
     *
     * [onDeleted] runs only on success. A failed delete puts the watch back in
     * the collection and its reason on the state, where the shell's snackbar
     * shows it — so the page must not navigate away from a delete that did not
     * happen.
     */
    fun delete(onDeleted: () -> Unit) {
        viewModelScope.launch {
            if (repository.delete(slug)) onDeleted()
        }
    }

    /** `Seiko SARB033` for a slug, falling back to the slug when it is unreadable. */
    private fun displayName(slug: String): String {
        val watch = repository.record(slug)?.watch ?: return slug
        return "${watch.brand} ${watch.model}"
    }

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
