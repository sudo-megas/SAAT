package io.github.sudomegas.saat.storage

import io.github.sudomegas.saat.storage.SaatPaths.Companion.IMAGES
import io.github.sudomegas.saat.storage.SaatPaths.Companion.WATCHES
import io.github.sudomegas.saat.storage.SaatPaths.Companion.WATCH_FILENAME
import java.io.File
import java.io.InputStream
import java.util.zip.ZipInputStream

/**
 * What an import did, all of it named — SPEC-ANDROID 3.2's "finish with a
 * summary: n added, n skipped, named".
 *
 * Three ways to not be added, kept apart because they mean different things to
 * the owner: [skipped] is "you already have this one", [malformed] is "this file
 * would not parse", and [ignored] is "this entry is not part of a collection".
 * Collapsing them into one figure would turn a corrupt archive and a duplicate
 * import into the same message.
 */
data class ImportSummary(
    val added: List<String> = emptyList(),
    val skipped: List<String> = emptyList(),
    val malformed: List<String> = emptyList(),
    val ignored: List<String> = emptyList(),
)

/**
 * An archive this app will not open, with the reason.
 *
 * Thrown BEFORE anything is written, which is the whole point of surveying the
 * archive in a separate pass: a refusal must leave the collection exactly as it
 * was, and a per-entry check made while extracting cannot promise that.
 */
class UnsafeArchiveException(message: String) : Exception(message)

/** Where an archive entry belongs once the two accepted roots are normalised. */
internal sealed interface EntryTarget {
    val slug: String

    data class Toml(override val slug: String) : EntryTarget
    data class Image(override val slug: String, val filename: String) : EntryTarget
}

/**
 * Read an archive into the collection — SPEC-ANDROID 3.2, AM10b.
 *
 * TWO PASSES, and the split is the brief's "validate before touching disk"
 * taken literally. `ZipInputStream` cannot seek, so [open] is a factory called
 * twice rather than a stream passed once: pass one surveys every entry name,
 * refuses the whole archive if any of them is unsafe, and reads the (small)
 * `watch.toml` files so malformed ones are found before a byte is written; pass
 * two streams the photographs for the watches that survived. A validation done
 * while extracting could only promise to stop halfway.
 *
 * BOTH ROOTS ARE ACCEPTED, per entry rather than by a global decision. Desktop
 * users zip their collection both ways — from above `watches/` and from inside
 * it — so a leading `watches/` is stripped when present and what remains must be
 * `<slug>/watch.toml` or `<slug>/images/<filename>`. Deciding the shape once for
 * the whole archive would need a tie-break for a mixed one; deciding per entry
 * needs none, and a watch slugged `watches` survives it in a watches/-rooted
 * archive (`watches/watches/watch.toml`). In a SLUG-ROOTED one it does not:
 * `watches/watch.toml` is indistinguishable from an archive root with a stray
 * file in it, and is ignored. That is a real limitation and it is written down
 * rather than papered over — nobody has a watch slugged `watches`, and guessing
 * wrong in the other direction would misread an ordinary archive.
 *
 * A SLUG THAT ALREADY EXISTS IS SKIPPED WHOLE — the owner's decision, recorded
 * in SPEC-ANDROID 3.2. Not merged, not overwritten, not renamed to `-2`: an
 * import is for watches this phone does not have, and anything else would put
 * the archive's opinion of a watch above the one the owner has been editing.
 *
 * IMPORTED FILES KEEP THEIR ORIGINAL BYTES. The `watch.toml` is parsed to decide
 * whether to accept it and then written unchanged, so a comment written on the
 * desktop is still there afterwards. Parsing and writing are separate steps here
 * for exactly that reason.
 */
fun importCollection(
    paths: SaatPaths,
    open: () -> InputStream,
    onProgress: (done: Int, total: Int) -> Unit = { _, _ -> },
): ImportSummary {
    val survey = survey(open)

    // CASE-INSENSITIVELY, and by NAME rather than by isDirectory.
    //
    // Two separate bugs closed here. Comparing case-sensitively let an archive
    // carrying `Seiko-SKX007` land beside an existing `seiko-skx007` — two
    // folders that collide case-insensitively, which is exactly the collision
    // `uniqueSlug` detects case-insensitively to prevent, arriving through the
    // one door meant for moving a collection between platforms. On a
    // case-insensitive filesystem the second would simply overwrite the first.
    //
    // Filtering on isDirectory meant a PLAIN FILE at watches/<slug> was not
    // treated as existing, so the import accepted the slug and then failed at
    // mkdirs — after earlier watches had already been written.
    val existing = paths.watchesDir.listFiles().orEmpty()
        .mapTo(HashSet()) { it.name.lowercase() }

    val accepted = LinkedHashMap<String, ByteArray>()
    val skipped = mutableListOf<String>()
    // Tracks what THIS import is about to create, so an archive holding both
    // `Seiko` and `seiko` cannot produce the same collision by itself.
    val claimed = HashSet<String>()

    survey.tomlBySlug.forEach { (slug, bytes) ->
        when {
            slug.lowercase() in existing -> skipped += slug
            !claimed.add(slug.lowercase()) -> skipped += slug
            else -> accepted[slug] = bytes
        }
    }

    val total = accepted.size + survey.imagesBySlug
        .filterKeys { it in accepted }
        .values.sumOf { it.size }
    var done = 0

    // The records first, so a watch exists before its photographs arrive. An
    // interrupted import then leaves readable watches with missing pictures
    // rather than orphan pictures belonging to nothing.
    accepted.forEach { (slug, bytes) ->
        val dir = paths.watchDir(slug)
        // mkdirs() returns false rather than throwing, and the failure would
        // otherwise surface one line later from writeBytes — by which point
        // earlier watches are already on disk and the caller reports a total
        // failure over a partial import.
        if (!dir.isDirectory && !dir.mkdirs()) {
            throw UnsafeArchiveException("could not create a folder for $slug")
        }
        paths.watchToml(slug).writeBytes(bytes)
        onProgress(++done, total)
    }

    if (accepted.isNotEmpty()) {
        extractImages(paths, open, accepted.keys) { onProgress(++done, total) }
    }

    return ImportSummary(
        added = accepted.keys.toList(),
        skipped = skipped,
        malformed = survey.malformed,
        ignored = survey.ignored,
    )
}

private class Survey(
    val tomlBySlug: Map<String, ByteArray>,
    val imagesBySlug: Map<String, List<String>>,
    val malformed: List<String>,
    val ignored: List<String>,
)

/**
 * Pass one: every entry name checked, every `watch.toml` read and parsed.
 *
 * Nothing is written here and nothing may be: this function's contract is that
 * an archive it refuses has left the collection untouched.
 */
private fun survey(open: () -> InputStream): Survey {
    val toml = LinkedHashMap<String, ByteArray>()
    val images = LinkedHashMap<String, MutableList<String>>()
    val malformed = mutableListOf<String>()
    val ignored = mutableListOf<String>()

    open().useZip { entry, stream ->
        val name = entry.name
        rejectIfUnsafe(name)

        // A DIRECTORY ENTRY IS NEVER CONTENT, whatever its name looks like, and
        // this has to be the first thing checked rather than a special case on
        // one branch. An archive holding both `a/images/f.jpg` and
        // `a/images/f.jpg/` used to write the real 8-byte image and then
        // truncate it to nothing with the zero-length directory entry — while
        // still counting it as imported. `a/watch.toml/` likewise marked a
        // perfectly good watch malformed.
        if (entry.isDirectory) return@useZip

        when (val target = targetOf(name)) {
            null -> ignored += name

            is EntryTarget.Toml -> {
                // Bounded. An entry claiming to be a watch.toml can claim any
                // size, and every accepted one is held until the write loop, so
                // the peak is their SUM rather than the largest. A 256 MB entry
                // is enough to exhaust an Android app heap; a real watch.toml is
                // a couple of kilobytes.
                if (entry.size > MAX_TOML_BYTES) {
                    malformed += target.slug
                    return@useZip
                }
                val bytes = stream.readBytes()
                if (bytes.size > MAX_TOML_BYTES) {
                    malformed += target.slug
                    return@useZip
                }
                // Parsed now, written later, and never re-serialised in between
                // — that is what keeps the original bytes on disk.
                when {
                    // Same slug twice in one archive — reachable because both
                    // roots are accepted, so `watches/a/watch.toml` and
                    // `a/watch.toml` can both appear. FIRST WINS and the second
                    // is named, rather than last-wins in silence, which would
                    // let a decoy entry quietly replace the real one.
                    target.slug in toml -> ignored += name
                    parses(bytes) -> toml[target.slug] = bytes
                    else -> malformed += target.slug
                }
            }

            is EntryTarget.Image ->
                images.getOrPut(target.slug) { mutableListOf() } += target.filename
        }
    }

    // A photograph whose watch never arrived, or whose watch would not parse,
    // has nothing to belong to.
    images.keys.retainAll(toml.keys)

    return Survey(toml, images, malformed, ignored)
}

/** Pass two: the photographs, streamed straight to disk for accepted slugs. */
private fun extractImages(
    paths: SaatPaths,
    open: () -> InputStream,
    accepted: Set<String>,
    onWritten: () -> Unit,
) {
    open().useZip { entry, stream ->
        // The same directory-entry guard as the survey, and it has to be here
        // too because THIS is the pass that writes. A zero-length directory
        // entry named `a/images/f.jpg/` would otherwise reopen the real image's
        // path and truncate it to nothing.
        if (entry.isDirectory) return@useZip

        val target = targetOf(entry.name)
        if (target !is EntryTarget.Image || target.slug !in accepted) return@useZip

        val dir = paths.watchMedia(target.slug)
        dir.mkdirs()
        // The filename is the entry's LAST component and nothing else — see
        // targetOf — so this cannot resolve outside the directory just made.
        File(dir, target.filename).outputStream().use { stream.copyTo(it) }
        onWritten()
    }
}

/**
 * Refuse the archive outright rather than skipping the entry.
 *
 * A `../` in an archive is not a mistake anybody makes by accident: it is the
 * shape of an attempt to write outside the app's own directory, and the honest
 * response to one bad entry is to distrust the file it came in.
 *
 * ON SYMLINKS, HONESTLY. The brief asks for them to be rejected too, and the
 * platform's zip API gives no way to see one: a symlink is marked in the
 * central directory's external attributes, which `java.util.zip.ZipEntry` does
 * not expose, and adding a library that does would cost a dependency for it.
 * What is done instead makes it moot — every entry is written with
 * `File(dir, filename).outputStream()` under a path this code builds itself, so
 * a symlink entry in an archive extracts as an ordinary file containing the
 * text of its target and creates no link at all. The escape a symlink is for
 * cannot happen; the entry simply arrives as a small useless file, and if its
 * name is `watch.toml` it fails to parse and is reported as malformed.
 */
private fun rejectIfUnsafe(name: String) {
    val normalised = name.replace('\\', '/')

    if (normalised.startsWith("/")) {
        throw UnsafeArchiveException("absolute path in the archive: $name")
    }
    // A Windows drive letter is absolute too, and does not start with a slash.
    if (normalised.length >= 2 && normalised[1] == ':') {
        throw UnsafeArchiveException("absolute path in the archive: $name")
    }
    if (normalised.split('/').any { it == ".." }) {
        throw UnsafeArchiveException("path traversal in the archive: $name")
    }
}

/**
 * Which watch an entry belongs to, or null when it belongs to none.
 *
 * A leading `watches/` is stripped when present, so both archive roots land on
 * the same two shapes. Everything else — a README somebody added, a `config
 * .toml`, a `.DS_Store`, a nested folder nobody planned for — returns null and
 * is reported as ignored rather than guessed at.
 *
 * The loader's `_`/`.` rule applies to slugs and filenames alike, so an archive
 * cannot introduce a folder this app would then refuse to read back.
 */
internal fun targetOf(name: String): EntryTarget? {
    val parts = name.replace('\\', '/').split('/').filter { it.isNotEmpty() }
    val relative = if (parts.firstOrNull() == WATCHES) parts.drop(1) else parts

    // IMPORT IS THE ONLY WRITER OF watches/<slug> THAT DOES NOT GO THROUGH
    // `slugify`, so the checks that function performs have to be repeated here
    // or the archive gets to name a folder this app would never have created:
    // over-long (the filesystem refuses it mid-write, after other watches have
    // already landed), or carrying a NUL, which survives a zip entry name
    // intact and makes every File call fail.
    val slug = relative.getOrNull(0)?.takeIf { isUsableSlug(it) } ?: return null

    return when {
        relative.size == 2 && relative[1] == WATCH_FILENAME -> EntryTarget.Toml(slug)

        relative.size == 3 && relative[1] == IMAGES && !isHiddenEntry(relative[2]) ->
            EntryTarget.Image(slug, relative[2])

        else -> null
    }
}

/**
 * A folder name this app is willing to create.
 *
 * Deliberately NOT `slugify()`: that function MAKES a slug from a brand and a
 * model, and rewriting an incoming one would rename somebody's watch on the way
 * in and break the round trip. This only rejects the names that cannot work —
 * the ones where accepting them means failing mid-write.
 */
private fun isUsableSlug(name: String): Boolean =
    !isHiddenEntry(name) &&
        name.length <= SLUG_MAX_LENGTH_ON_IMPORT &&
        name.none { it == '\u0000' }

/** Matches `Slugs.kt`'s own cap, which is what this app's own slugs obey. */
private const val SLUG_MAX_LENGTH_ON_IMPORT = 80

/** A watch.toml is kilobytes. This is four orders of magnitude of headroom. */
private const val MAX_TOML_BYTES = 4L * 1024 * 1024

/**
 * Does this file read as a watch?
 *
 * Only a gate, and the decoded value is thrown away on purpose: what gets
 * written is the bytes that arrived, not a re-encoding of what they decoded to.
 */
private fun parses(bytes: ByteArray): Boolean = runCatching {
    decodeWatch(bytes.toString(Charsets.UTF_8))
}.isSuccess

/**
 * Walk the archive once and close it, whatever happens.
 *
 * The stream handed to [body] is the `ZipInputStream` itself, positioned on the
 * current entry — reading past the entry's end is not possible, which is what
 * makes `readBytes()` safe to call on it.
 */
private inline fun InputStream.useZip(body: (java.util.zip.ZipEntry, ZipInputStream) -> Unit) {
    ZipInputStream(this).use { zip ->
        while (true) {
            val entry = zip.nextEntry ?: break
            body(entry, zip)
            zip.closeEntry()
        }
    }
}
