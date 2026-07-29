package io.github.sudomegas.saat.storage

import io.github.sudomegas.saat.storage.SaatPaths.Companion.IMAGES
import io.github.sudomegas.saat.storage.SaatPaths.Companion.WATCH_FILENAME
import java.io.File
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

/** How many timestamped copies `backups/` keeps — SPEC-ANDROID 3. */
const val BACKUP_KEEP = 20

private val BACKUP_TIMESTAMP = DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmss")

/**
 * A watch as it exists on disk: the parsed model plus the bookkeeping needed to
 * write it back.
 *
 * [watch] and [loaded] are null when the file failed to load — [loadError] says
 * why, and the UI shows the slug with an error badge instead of the app
 * crashing or the watch quietly disappearing (SPEC-ANDROID 3).
 *
 * [loaded] is the model exactly as it came off disk and is what makes byte
 * preservation checkable: [isDirty] is the whole of "has the owner actually
 * edited this watch", and [WatchStore.save] refuses to write when it is false.
 */
data class WatchRecord(
    val slug: String,
    val dir: File,
    val watch: Watch? = null,
    val loaded: Watch? = null,
    val loadError: String? = null,
    /** Fields the loader could not read, named and quoted. Never fatal. */
    val warnings: List<String> = emptyList(),
) {
    /** True once the in-memory watch differs from what is on disk. */
    val isDirty: Boolean get() = watch != null && watch != loaded
}

/**
 * Reads and writes the collection. Every path it touches comes from [paths], and
 * [paths] is rooted at `filesDir` in the app and at a temp directory in the
 * tests — nothing here knows what a `Context` is.
 *
 * [now] is injected so the backup tests can produce a known filename instead of
 * asserting against the second the test happened to run in.
 *
 * OPEN, and the three writing methods with it, for one reason: hard rule 6 says
 * a failure must reach the UI with its message intact, and that behaviour is
 * only testable if a write can be made to fail on demand. The alternatives were
 * worse — chmod-ing a directory read-only is a no-op when the tests run as root,
 * and an interface with one production implementation is indirection bought for
 * nothing. There is no other subclass and none is expected outside the tests.
 */
open class WatchStore(
    val paths: SaatPaths,
    private val now: () -> LocalDateTime = LocalDateTime::now,
) {

    // ---- reading ---------------------------------------------------------

    /**
     * Every watch under `watches/`, in slug order, including the ones that
     * failed. A malformed file becomes a record carrying its error rather than
     * vanishing from the list — never a crash, never silent (SPEC-ANDROID 3).
     */
    open fun loadCollection(): List<WatchRecord> {
        val dir = paths.watchesDir
        if (!dir.isDirectory) return emptyList()

        return dir.listFiles().orEmpty()
            .filter { it.isDirectory && !isHiddenEntry(it.name) }
            .sortedBy { it.name }
            .map { loadWatch(it) }
    }

    fun loadWatch(dir: File): WatchRecord {
        val slug = dir.name
        val file = File(dir, WATCH_FILENAME)

        if (!file.exists()) {
            return WatchRecord(slug, dir, loadError = "$WATCH_FILENAME not found")
        }

        val text = try {
            file.readText()
        } catch (e: Exception) {
            return WatchRecord(slug, dir, loadError = e.message ?: "could not be read")
        }

        return try {
            val decoded = decodeWatch(text)
            WatchRecord(
                slug = slug,
                dir = dir,
                watch = decoded.watch,
                loaded = decoded.watch,
                warnings = decoded.warnings,
            )
        } catch (e: WatchFormatException) {
            WatchRecord(slug, dir, loadError = e.message ?: "could not be read as a watch")
        } catch (e: Exception) {
            // Anything the decoder did not anticipate still becomes a visible
            // (file, error) pair rather than escaping the loader. Hard rule 6
            // is about surfacing the message, not about where it was thrown.
            WatchRecord(slug, dir, loadError = "${e::class.simpleName}: ${e.message}")
        }
    }

    // ---- writing ---------------------------------------------------------

    /**
     * Give a new watch a folder and write it. The slug is resolved against every
     * directory already in `watches/`, hidden ones included — a name collision
     * is a filesystem fact and does not care that the loader skips `_template`.
     */
    open fun create(watch: Watch): WatchRecord {
        val existing = paths.watchesDir.listFiles().orEmpty()
            .filter { it.isDirectory }
            .mapTo(mutableSetOf()) { it.name }

        val slug = uniqueSlug(watch.brand, watch.model, existing)
        return save(WatchRecord(slug = slug, dir = paths.watchDir(slug), watch = watch))
    }

    /**
     * Write the watch back, atomically, taking a backup first.
     *
     * THE BYTE PRESERVATION RULE (SPEC-ANDROID 3). A watch loaded from disk and
     * never edited is never rewritten, so a hand-written file keeps its comments,
     * its key order and its formatting until the owner actually changes that
     * watch — at which point they are lost, because a Kotlin TOML writer
     * regenerates the file rather than editing it in place the way the desktop's
     * tomlkit does. That limit is stated plainly in `docs/ANDROID-STORAGE.md`
     * instead of being papered over.
     *
     * The guard lives here rather than only in the repository so that no future
     * caller can bypass it by holding a record and calling save in a loop.
     *
     * [backup] is false for edits that are not a "destructive operation" in
     * SPEC.md §3's sense — a wear-date toggle from the calendar, which can touch
     * many watches in one gesture. `backups/` is pruned to a shared 20 slots, so
     * every caller that edits hand-typed fields must keep the default or
     * evictable wear toggles will crowd out a real snapshot.
     *
     * @throws IllegalArgumentException if the record failed to load; there is
     *   nothing to write and overwriting the file would destroy what is there.
     */
    open fun save(record: WatchRecord, backup: Boolean = true): WatchRecord {
        val watch = requireNotNull(record.watch) {
            "cannot save ${record.slug}: it did not load (${record.loadError})"
        }

        val file = File(record.dir, WATCH_FILENAME)

        // Unedited and already on disk: writing would change the bytes of a file
        // the owner did not ask us to touch. The exists() half is a repair
        // path — if the file is gone, an unedited record is still worth writing.
        if (!record.isDirty && file.exists()) return record

        record.dir.mkdirs()
        if (backup && file.exists()) {
            backupWatchToml(record.slug, file)
        }

        writeAtomically(file, encodeWatch(watch))

        return record.copy(loaded = watch, loadError = null, warnings = emptyList())
    }

    /**
     * Move a watch out of the collection rather than erasing it — SPEC-ANDROID 3.
     *
     * Both of its trees go, because on the phone a watch is two folders: its
     * record in `watches/<slug>/` and its photographs in `media/<slug>/`. They
     * REJOIN on the way out, into the shape the desktop and the exported ZIP
     * both use:
     *
     * ```
     * backups/deleted/<slug>/watch.toml
     * backups/deleted/<slug>/images/...
     * ```
     *
     * so that a deleted watch is one self-contained folder that reads as a watch
     * to anyone browsing the files, and that AM10 can zip without transforming.
     * The split back into `watches/` and `media/` is what a restore would do,
     * which is the same amount of work either way.
     *
     * A timestamped copy of the `watch.toml` also goes into `backups/` first, so
     * a delete leaves the same trace in the same place every other destructive
     * edit does.
     */
    open fun delete(record: WatchRecord) {
        backupWatchToml(record.slug, File(record.dir, WATCH_FILENAME))

        val destination = availableDeletedDir(record.slug)
        destination.parentFile?.mkdirs()

        moveDirectory(record.dir, destination)
        moveDirectory(paths.watchMedia(record.slug), File(destination, IMAGES))
    }

    // ---- backups ---------------------------------------------------------

    /**
     * Copy the current `watch.toml` into `backups/` under a timestamped name,
     * then prune. Silent when there is nothing to copy — the first save of a new
     * watch has no previous version to keep.
     */
    fun backupWatchToml(slug: String, source: File) {
        if (!source.exists()) return

        val dir = paths.backupsDir
        dir.mkdirs()

        val base = "$slug-${now().format(BACKUP_TIMESTAMP)}"
        var destination = File(dir, "$base.toml")
        var n = 2
        while (destination.exists()) {
            destination = File(dir, "$base-$n.toml")
            n += 1
        }

        source.copyTo(destination)
        pruneBackups()
    }

    /**
     * Keep the newest [BACKUP_KEEP] backups and delete the rest.
     *
     * Only files directly inside `backups/` count, which is what leaves
     * `backups/deleted/` — a directory — out of the budget. A deleted watch is
     * not competing for slots with a save from last Tuesday.
     *
     * Ordered by last-modified with the filename as tie-break, because several
     * backups can land inside one filesystem timestamp tick and an arbitrary
     * eviction order would make the pruning test flake rather than fail.
     */
    private fun pruneBackups(keep: Int = BACKUP_KEEP) {
        val files = paths.backupsDir.listFiles().orEmpty().filter { it.isFile }
        val excess = files.size - keep
        if (excess <= 0) return

        files.sortedWith(compareBy({ it.lastModified() }, { it.name }))
            .take(excess)
            .forEach { it.delete() }
    }

    private fun availableDeletedDir(slug: String): File {
        val plain = File(paths.deletedDir, slug)
        if (!plain.exists()) return plain

        val stamped = File(paths.deletedDir, "$slug-${now().format(BACKUP_TIMESTAMP)}")
        if (!stamped.exists()) return stamped

        var n = 2
        while (File(paths.deletedDir, "${stamped.name}-$n").exists()) n += 1
        return File(paths.deletedDir, "${stamped.name}-$n")
    }

    /**
     * Move a whole directory, merging into the destination if it already has
     * something in it.
     *
     * A single `renameTo` handles the ordinary case in one syscall. The
     * file-by-file fallback exists for the collection that came in from a
     * desktop ZIP with `watches/<slug>/images/` already populated, where the
     * photographs would otherwise have nowhere to land.
     */
    private fun moveDirectory(source: File, destination: File) {
        if (!source.exists()) return
        if (!destination.exists() && source.renameTo(destination)) return

        destination.mkdirs()
        source.listFiles().orEmpty().forEach { child ->
            val target = File(destination, child.name)
            if (child.isDirectory) {
                moveDirectory(child, target)
            } else if (!child.renameTo(target)) {
                child.copyTo(target, overwrite = true)
                child.delete()
            }
        }
        source.delete()
    }
}
