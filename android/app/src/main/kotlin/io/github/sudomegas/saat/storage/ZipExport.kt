package io.github.sudomegas.saat.storage

import io.github.sudomegas.saat.storage.SaatPaths.Companion.IMAGES
import io.github.sudomegas.saat.storage.SaatPaths.Companion.WATCHES
import io.github.sudomegas.saat.storage.SaatPaths.Companion.WATCH_FILENAME
import java.io.BufferedOutputStream
import java.io.File
import java.io.OutputStream
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/**
 * What an export produced, for the notice afterwards.
 *
 * [skipped] names watch folders that carry no `watch.toml`. They are NOT
 * silently dropped — hard rule 6 — because a folder in `watches/` with no record
 * in it is either a half-finished hand edit or a sign something went wrong, and
 * the owner should hear about it while they still have the phone in their hand.
 */
data class ExportSummary(
    val watches: Int,
    val images: Int,
    val skipped: List<String>,
)

/** `saat-export-2026-08-03.zip` — SPEC-ANDROID 3.2. */
fun exportFilename(today: LocalDate): String =
    "saat-export-${today.format(DateTimeFormatter.ISO_LOCAL_DATE)}.zip"

/**
 * The collection, zipped into the DESKTOP'S shape — SPEC-ANDROID 3.2.
 *
 * ```
 * watches/<slug>/watch.toml
 * watches/<slug>/images/<filename>
 * ```
 *
 * THE RE-ROOT IS THE WHOLE JOB. On the phone the photographs live in a sibling
 * `media/<slug>/` tree, because Android's Auto Backup rules have no wildcards
 * and "back up the records, never the photographs" is not otherwise expressible
 * (SPEC-ANDROID 3). The archive puts them back inside each watch's folder, so
 * unzipping into the desktop app's directory IS the import on that side. The
 * phone's internal layout is an implementation detail; the archive is the
 * contract.
 *
 * That re-root works only because a watch's `images` key holds BARE FILENAMES
 * rather than paths — SPEC-ANDROID 3 says it "must continue to", and
 * [assertImagesAreBareFilenames] is where that assumption is checked rather than
 * assumed.
 *
 * BYTES ARE COPIED, NEVER RE-SERIALISED. Every `watch.toml` goes into the
 * archive exactly as it sits on disk, so a hand-written comment survives an
 * export — the byte-preservation rule of SPEC-ANDROID 3, which would be
 * pointless if the one operation that leaves the phone rewrote every file on the
 * way out. Nothing derived is included: no config, no backups, no caches, no
 * thumbnails. Clean data only.
 *
 * STREAMED. `copyTo` moves a buffer at a time and the archive is written
 * straight into [out], so a collection with hundreds of photographs never exists
 * in memory at once. [onProgress] is called per file with (done, total) — the
 * total is known in advance because listing directories is cheap and reading
 * them is not.
 *
 * Driven from `watches/`, not from `media/`: a photograph belonging to no record
 * is not part of the collection and does not travel. Entries whose names begin
 * with `_` or `.` are skipped on both trees, the same rule the loader applies,
 * so a scratch folder never lands in an archive bound for another machine.
 */
fun exportCollection(
    paths: SaatPaths,
    out: OutputStream,
    onProgress: (done: Int, total: Int) -> Unit = { _, _ -> },
): ExportSummary {
    val slugDirs = paths.watchesDir.listFiles().orEmpty()
        .filter { it.isDirectory && !isHiddenEntry(it.name) }
        // Sorted so two exports of an unchanged collection lay their entries
        // down in the same order — a diff between two archives should be about
        // the collection, not about what order the filesystem felt like.
        .sortedBy { it.name }

    val work = slugDirs.mapNotNull { dir ->
        val toml = File(dir, WATCH_FILENAME)
        if (!toml.isFile) null else SlugWork(dir.name, toml, imagesOf(paths, dir.name))
    }
    val skipped = slugDirs.map { it.name } - work.mapTo(HashSet()) { it.slug }

    val total = work.sumOf { 1 + it.images.size }
    var done = 0
    var images = 0

    ZipOutputStream(BufferedOutputStream(out)).use { zip ->
        work.forEach { entry ->
            zip.write("$WATCHES/${entry.slug}/$WATCH_FILENAME", entry.toml)
            onProgress(++done, total)

            entry.images.forEach { image ->
                zip.write("$WATCHES/${entry.slug}/$IMAGES/${image.name}", image)
                images++
                onProgress(++done, total)
            }
        }
    }

    return ExportSummary(watches = work.size, images = images, skipped = skipped)
}

private class SlugWork(val slug: String, val toml: File, val images: List<File>)

private fun imagesOf(paths: SaatPaths, slug: String): List<File> =
    paths.watchMedia(slug).listFiles().orEmpty()
        .filter { it.isFile && !isHiddenEntry(it.name) }
        .sortedBy { it.name }

private fun ZipOutputStream.write(path: String, source: File) {
    putNextEntry(ZipEntry(path))
    source.inputStream().use { it.copyTo(this) }
    closeEntry()
}

/**
 * Every filename in every `images` key, with no directory part.
 *
 * SPEC-ANDROID 3 makes this an invariant the storage layout DEPENDS on: the
 * `media/` split, the whole-folder delete and this export's re-root all assume
 * a bare filename, and a path in that key would mean an archive entry outside
 * the watch's own folder. AM5 is the only writer and it copies files in under
 * their own names, so this holds — but "it holds today" is a coincidence, not a
 * rule, so the round-trip test asserts it.
 */
fun assertImagesAreBareFilenames(watches: List<Watch>): List<String> =
    watches.flatMap { it.images }
        .filter { it.isNotBlank() && (it.contains('/') || it.contains('\\')) }
