package io.github.sudomegas.saat.storage

import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
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

    /**
     * The in-memory version of [slug] when it holds an edit that is not on disk
     * yet, and null otherwise. See [WatchRepository.load].
     */
    internal fun unsaved(slug: String): WatchRecord? =
        records.firstOrNull { it.slug == slug && it.isDirty }
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
     * Serialises every read-modify-write of the collection.
     *
     * Each mutation below reads the current state, transforms it and writes both
     * memory and disk, with a suspension point in the middle. Without this lock
     * two of them running at once would both read the same starting record and
     * the second would overwrite the first — a lost edit, on disk, silently.
     *
     * That is not hypothetical after AM8: "wore this today" exists on the detail
     * page, on the home-screen widget and on an app shortcut, all three driving
     * the same collection, and a widget tap while the app is open is an ordinary
     * thing to do. A single mutex is enough because the whole collection is one
     * in-memory object; there is nothing to gain from finer granularity and a
     * per-slug lock would still not protect the shared record list.
     */
    private val writeLock = Mutex()

    /**
     * Read the whole collection, off the main thread; reading a few hundred
     * small files is fast but it is still I/O and it still happens while the
     * launch window is on screen.
     *
     * A RELOAD KEEPS WHAT IS NOT ON DISK YET. Nothing calls this twice today,
     * but AM10's import will, and replacing the collection wholesale would take
     * a record whose write failed — kept in memory ON PURPOSE, see the class
     * note — and quietly swap it for the older text still in the file. That is
     * the exact loss the write-through policy above exists to prevent, and it
     * would happen without a message. [CollectionState.writeError] survives for
     * the same reason: a notice the owner has not dismissed is not dismissed by
     * a reload.
     *
     * A dirty record whose folder has since gone from disk is NOT resurrected —
     * it is absent from the fresh list, so nothing maps onto it. Something
     * removed that folder, and inventing it back is a larger claim than
     * dropping an edit.
     */
    suspend fun load() = writeLock.withLock {
        _state.update { it.copy(isLoading = true) }
        val records = withContext(io) { store.loadCollection() }
        _state.update { previous ->
            CollectionState(
                records = records.map { previous.unsaved(it.slug) ?: it },
                isLoaded = true,
                writeError = previous.writeError,
            )
        }
    }

    fun record(slug: String): WatchRecord? = _state.value.records.firstOrNull { it.slug == slug }

    /**
     * Add a watch. Disk first here, unlike an edit, because the store is what
     * assigns the slug — there is no identity to put in memory until it has.
     *
     * Returns null when the write failed; the error is in [CollectionState.writeError].
     */
    suspend fun create(watch: Watch): WatchRecord? = writeLock.withLock {
        try {
            val created = withContext(io) { store.create(watch) }
            _state.update { it.copy(records = (it.records + created).sortedBy(WatchRecord::slug)) }
            created
        } catch (e: Exception) {
            _state.update { it.copy(writeError = describe("could not create", watch.brand, e)) }
            null
        }
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
    ): WatchRecord? = writeLock.withLock {
        val current = record(slug) ?: return null
        val watch = current.watch ?: return null

        val edited = current.copy(watch = transform(watch))
        if (!edited.isDirty) return current

        replace(edited)

        try {
            val saved = withContext(io) { store.save(edited, backup) }
            replace(saved)
            saved
        } catch (e: Exception) {
            _state.update { it.copy(writeError = describe("could not save", slug, e)) }
            edited
        }
    }

    /** Move a watch into `backups/deleted/`. See [WatchStore.delete]. */
    suspend fun delete(slug: String): Boolean = writeLock.withLock {
        val record = record(slug) ?: return false

        _state.update { it.copy(records = it.records.filterNot { r -> r.slug == slug }) }

        try {
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
