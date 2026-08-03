package io.github.sudomegas.saat.ui

import io.github.sudomegas.saat.storage.FacetKind
import io.github.sudomegas.saat.storage.WatchFilter
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

/**
 * The one filter, shared by every screen that narrows the collection.
 *
 * Owned by the Application rather than by a ViewModel, and that is this
 * milestone's "do not implement filters twice" made structural: the Grid and the
 * Specs list read the SAME flow, so a facet picked on one is already picked on
 * the other, and AM7's calendar picker joins by reading it too rather than by
 * growing a filter of its own. The same shape `ConfigState` already has, for the
 * same reason — one writer, one truth.
 *
 * NOT PERSISTED, deliberately. SPEC-ANDROID 3 lists what `config.toml` holds and
 * a filter is not among it. It is also the same judgement AM3 made about the
 * search query: a sort is a preference, but a filter is a question you are
 * asking right now, and reopening the app to a narrowed collection you do not
 * remember narrowing is how a grid appears to have lost watches. The active
 * chips under the top bar exist so the state is never invisible while it lasts.
 */
class FilterState {

    private val _filter = MutableStateFlow(WatchFilter())
    val filter: StateFlow<WatchFilter> = _filter.asStateFlow()

    fun toggle(kind: FacetKind, value: String) {
        _filter.update { it.toggle(kind, value) }
    }

    /** What a dismissible chip does. */
    fun remove(kind: FacetKind, value: String) {
        _filter.update { it.without(kind, value) }
    }

    fun clear() {
        _filter.value = WatchFilter()
    }
}
