package io.github.sudomegas.saat.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import io.github.sudomegas.saat.SaatApplication
import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.WatchRepository
import io.github.sudomegas.saat.ui.form.WatchFormState
import io.github.sudomegas.saat.ui.form.toWatch
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * The add/edit form's state holder — SPEC-ANDROID 5.7.
 *
 * A ViewModel rather than `remember`, and that is a requirement rather than a
 * habit: this milestone's brief asks that rotating the phone mid-edit lose
 * nothing, and a form this size cannot be threaded through `rememberSaveable`
 * field by field without one of them being forgotten. One state object, held
 * across configuration changes, is the version that cannot be partly right.
 *
 * [slug] null means ADD; anything else means edit that watch. The same screen
 * serves both, as the brief requires, and the only differences are where the
 * initial state comes from and whether saving creates or updates.
 */
class FormViewModel(
    private val repository: WatchRepository,
    private val slug: String?,
) : ViewModel() {

    /**
     * The state the form opened with, and the whole of the unsaved-changes
     * check. Reassigned on a successful save so that saving and then backing
     * out does not prompt about changes that are already on disk.
     */
    private var initial: WatchFormState = WatchFormState.empty()

    private val _state = MutableStateFlow(initial)
    val state: StateFlow<WatchFormState> = _state.asStateFlow()

    /** True when this form is editing an existing watch rather than adding one. */
    val isEditing: Boolean = slug != null

    /** False until an edit's watch has been read, so the form cannot save a blank over it. */
    private val _isReady = MutableStateFlow(slug == null)
    val isReady: StateFlow<Boolean> = _isReady.asStateFlow()

    /**
     * Every value the collection already uses, for the enum* dropdowns —
     * SPEC.md §4's "plus every value already used elsewhere in the collection".
     */
    val collection: StateFlow<List<Watch>> = repository.state
        .map { state -> state.watches.mapNotNull { it.watch } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    /**
     * Backing out with this true prompts — SPEC-ANDROID 5.7.
     *
     * Structural inequality against the opening state, not a flag set by an
     * edit signal. Typing a character and deleting it comes back equal and asks
     * nothing, which the desktop's signal-based version gets wrong and which is
     * the difference between a prompt that means something and one people learn
     * to dismiss.
     */
    val isDirty: Boolean get() = _state.value != initial

    init {
        if (slug != null) {
            viewModelScope.launch {
                // Waits for the load rather than reading whatever is in memory
                // now: the form can be opened from a cold start, before the
                // collection has finished being read, and seeding from an empty
                // collection would put a blank form over a real watch.
                val collection = repository.state.first { it.isLoaded }
                val watch = collection.records.firstOrNull { it.slug == slug }?.watch
                if (watch != null) {
                    initial = WatchFormState.from(watch)
                    _state.value = initial
                }
                // Ready either way. A watch that will not parse leaves the form
                // blank, and the screen says so rather than spinning forever.
                _isReady.value = true
            }
        }
    }

    fun update(transform: (WatchFormState) -> WatchFormState) {
        _state.update(transform)
    }

    /**
     * Write the watch. Returns its slug, or null when the write failed.
     *
     * `worn` is taken from the record being edited rather than from the form,
     * which does not carry it: wear is the calendar's field and the detail
     * button's, and rebuilding a watch without it would delete a wear history on
     * every edit of an unrelated field.
     */
    suspend fun save(): String? {
        val form = _state.value
        if (!form.canSave) return null

        val saved = if (slug == null) {
            repository.create(form.toWatch())
        } else {
            repository.update(slug) { existing -> form.toWatch(preservedWorn = existing.worn) }
        } ?: return null

        // What is on disk is now what is on screen, so backing out is not a
        // discard. Anything typed after this point is dirty again.
        initial = form
        return saved.slug
    }

    companion object {
        fun factory(app: SaatApplication, slug: String?): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T =
                    FormViewModel(repository = app.watchRepository, slug = slug) as T
            }
    }
}
