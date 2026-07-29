package io.github.sudomegas.saat.storage

import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.withContext

/**
 * The whole collection, as the rest of the app sees it.
 *
 * Failed files are IN [records] rather than filtered out of it, carrying their
 * [WatchRecord.loadError]. A watch that will not parse is still a folder the
 * owner has, and the grid is going to show it with an error badge — dropping it
 * from the list here would be the silent skip SPEC-ANDROID 3 forbids.
 */
data class CollectionState(
    val records: List<WatchRecord> = emptyList(),
    val isLoading: Boolean = false,
    /** True once a load has finished, so the empty state can tell "none" from "not yet". */
    val isLoaded: Boolean = false,
    /** Non-null when a write failed. Hard rule 6: it reaches the UI intact. */
    val writeError: String? = null,
) {
    /** The watches that loaded — what every screen from AM3 onward actually renders. */
    val watches: List<WatchRecord> get() = records.filter { it.watch != null }

    /** The files that did not load, for the notice naming each one and its error. */
    val failures: List<WatchRecord> get() = records.filter { it.loadError != null }

    /** Fields the loader had to forgive, each prefixed with the watch it came from. */
    val warnings: List<String>
        get() = records.flatMap { record -> record.warnings.map { "${record.slug}: $it" } }
}

/**
 * The in-memory index SPEC-ANDROID hard rule 4 describes: the TOML files are the
 * truth, parsed once at launch into memory, with no database, no ORM and no
 * cache layer in between. A hobby collection fits in RAM hundreds of times over,
 * and the alternative — a second copy of the data that can disagree with the
 * files — is the thing the whole storage format exists to avoid.
 *
 * Edits are WRITE-THROUGH: memory first, disk immediately after, and the error
 * surfaced if the disk write fails.
 *
 * When a write does fail, the edit STAYS in memory. Losing what the owner just
 * typed would be a second failure on top of the first, and because the record
 * keeps its old on-disk snapshot it remains [WatchRecord.isDirty] — so a later
 * successful save still writes it. Deletion is deliberately the other way round:
 * a failed delete puts the watch back in the list, because there is nothing the
 * owner typed to lose and a watch missing from the grid while still on disk
 * would be the app lying about what it has.
 */
class WatchRepository(
    private val store: WatchStore,
    private val io: CoroutineDispatcher = Dispatchers.IO,
) {

    private val _state = MutableStateFlow(CollectionState())
    val state: StateFlow<CollectionState> = _state.asStateFlow()

    /**
     * Read the whole collection. Called once at process start, off the main
     * thread; reading a few hundred small files is fast but it is still I/O and
     * it still happens while the launch window is on screen.
     */
    suspend fun load() {
        _state.update { it.copy(isLoading = true) }
        val records = withContext(io) { store.loadCollection() }
        _state.value = CollectionState(records = records, isLoaded = true)
    }

    fun record(slug: String): WatchRecord? = _state.value.records.firstOrNull { it.slug == slug }

    /**
     * Add a watch. Disk first here, unlike an edit, because the store is what
     * assigns the slug — there is no identity to put in memory until it has.
     *
     * Returns null when the write failed; the error is in [CollectionState.writeError].
     */
    suspend fun create(watch: Watch): WatchRecord? = try {
        val created = withContext(io) { store.create(watch) }
        _state.update { it.copy(records = (it.records + created).sortedBy(WatchRecord::slug)) }
        created
    } catch (e: Exception) {
        _state.update { it.copy(writeError = describe("could not create", watch.brand, e)) }
        null
    }

    /**
     * Edit a watch in place.
     *
     * A transform that changes nothing writes nothing and does not even touch
     * the state — the byte preservation rule reaches all the way up here, not
     * only into [WatchStore.save].
     *
     * [backup] is false for a wear-date toggle, which can touch many watches in
     * one calendar gesture; see [WatchStore.save].
     */
    suspend fun update(
        slug: String,
        backup: Boolean = true,
        transform: (Watch) -> Watch,
    ): WatchRecord? {
        val current = record(slug) ?: return null
        val watch = current.watch ?: return null

        val edited = current.copy(watch = transform(watch))
        if (!edited.isDirty) return current

        replace(edited)

        return try {
            val saved = withContext(io) { store.save(edited, backup) }
            replace(saved)
            saved
        } catch (e: Exception) {
            _state.update { it.copy(writeError = describe("could not save", slug, e)) }
            edited
        }
    }

    /** Move a watch into `backups/deleted/`. See [WatchStore.delete]. */
    suspend fun delete(slug: String): Boolean {
        val record = record(slug) ?: return false

        _state.update { it.copy(records = it.records.filterNot { r -> r.slug == slug }) }

        return try {
            withContext(io) { store.delete(record) }
            true
        } catch (e: Exception) {
            _state.update {
                it.copy(
                    records = (it.records + record).sortedBy(WatchRecord::slug),
                    writeError = describe("could not delete", slug, e),
                )
            }
            false
        }
    }

    /** Dismiss the notice, once the owner has seen it. */
    fun clearWriteError() {
        _state.update { it.copy(writeError = null) }
    }

    private fun replace(record: WatchRecord) {
        _state.update { state ->
            state.copy(records = state.records.map { if (it.slug == record.slug) record else it })
        }
    }

    // The message is carried, not swallowed and not reduced to "an error
    // occurred" — hard rule 6. A storage failure on a phone is nearly always
    // "no space left on device", which is actionable only if it is said.
    private fun describe(what: String, subject: String, e: Exception) =
        "$what $subject: ${e.message ?: e::class.simpleName}"
}
