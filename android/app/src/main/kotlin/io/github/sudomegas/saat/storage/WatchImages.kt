package io.github.sudomegas.saat.storage

import io.github.sudomegas.saat.storage.SaatPaths.Companion.IMAGES
import java.io.File
import java.io.InputStream

/**
 * A watch's photographs, on disk — SPEC-ANDROID 3 and 5.7.
 *
 * THE COLLECTION NEVER DEPENDS ON A URI. Everything the picker or the camera
 * produces is COPIED into `media/<slug>/`, because a `content://` URI is a
 * permission grant to somebody else's file: it expires when the process dies,
 * it dies when the owner clears the gallery app's data, and a collection whose
 * photographs are borrowed is a collection that empties itself over a year. The
 * milestone brief says this in as many words, and it is the difference between a
 * record and a bookmark.
 *
 * BYTES ARE COPIED VERBATIM — no decode, no re-encode, no rotation baked in.
 * "EXIF orientation honoured" is achieved by PRESERVING the tag rather than by
 * applying it: Coil reads it at decode time and so does the desktop's Pillow,
 * while re-encoding would be lossy, would change the file the desktop also
 * reads, and would throw away every other tag the camera wrote. The desktop's
 * `import_image` uses `shutil.copy2` for exactly this reason, and the two apps
 * have to agree about what is in the file.
 */
class WatchImages(private val paths: SaatPaths) {

    /** The filenames already in this watch's media folder, in no order. */
    fun existing(slug: String): List<String> =
        paths.watchMedia(slug).listFiles().orEmpty().filter { it.isFile }.map { it.name }

    /**
     * Copy [source] into `media/<slug>/` and answer the name it got.
     *
     * [taken] is the names already spoken for — what is on disk plus whatever
     * else is being imported in the same save — so two photographs picked in one
     * gesture cannot land on each other.
     */
    fun import(slug: String, source: InputStream, preferredName: String, taken: Set<String>): String {
        val directory = paths.watchMedia(slug)
        directory.mkdirs()

        val name = uniqueImageName(safeImageFilename(preferredName), taken + existing(slug))
        writeAtomically(File(directory, name)) { output -> source.copyTo(output) }
        return name
    }

    /**
     * Take a photograph out of the collection — into `backups/deleted/`, never
     * erased.
     *
     * The same grave a deleted watch goes to and the same shape:
     * `backups/deleted/<slug>/images/<name>`, which is the desktop's own layout
     * and what AM10 can zip without transforming. A photograph is not
     * recoverable by any other means — there is no second copy anywhere — so
     * "delete" here means the same thing it means for a whole watch.
     *
     * Colliding names are numbered rather than overwritten. After a delete that
     * IS the only copy there was, which makes it the one place in the app where
     * overwriting a file is unrecoverable.
     */
    fun delete(slug: String, filename: String) {
        val source = File(paths.watchMedia(slug), File(filename).name)
        if (!source.exists()) return

        val grave = File(File(paths.deletedDir, slug), IMAGES)
        grave.mkdirs()

        val destination = availableName(File(grave, source.name))
        if (!source.renameTo(destination)) {
            source.copyTo(destination)
            source.delete()
        }
    }

    /** `target`, or the next free `front-2.jpg` beside it. */
    private fun availableName(target: File): File {
        if (!target.exists()) return target

        val (stem, suffix) = splitExtension(target.name)
        var n = 2
        while (File(target.parentFile, "$stem-$n$suffix").exists()) n += 1
        return File(target.parentFile, "$stem-$n$suffix")
    }
}

/**
 * A filesystem-safe image filename — a port of the desktop's
 * `safe_image_filename`, and the image counterpart of [slugify].
 *
 * The same three whole-name rules as a slug — forbidden characters out, length
 * capped, reserved names guarded — but applied to the STEM only so the
 * extension survives, and without slugify's lowercasing. A photograph the owner
 * picked should keep the name they recognise: mixed case, spaces and accents are
 * all perfectly writable once the characters no filesystem accepts are gone.
 *
 * Guarded on every platform rather than only where it bites, for the same reason
 * the slug is: a name one filesystem accepts and another cannot open is a
 * collection that stops being portable the moment it is copied across, and this
 * one travels inside the exported ZIP.
 */
fun safeImageFilename(name: String): String {
    // Split on the last dot by hand rather than through File(): a raw name can
    // still hold a ':' or a '/' here, which a path type would misread as a
    // separator. A leading-dot-only name has no stem and therefore no extension.
    val (rawStem, suffix) = splitExtension(name)

    var stem = FILENAME_FORBIDDEN.replace(rawStem, "").trim(' ', '.')
    if (stem.length > IMAGE_NAME_MAX_LENGTH) {
        stem = stem.take(IMAGE_NAME_MAX_LENGTH).trim(' ', '.')
    }
    if (stem.isEmpty()) stem = FALLBACK_IMAGE_STEM

    // Windows reserves con/nul/lpt1/... as the first dot-separated segment even
    // with an extension — `con.jpg` is still the console — so the guard is on
    // that segment, keeping any second extension intact.
    val segment = stem.substringBefore('.')
    if (segment.lowercase() in WINDOWS_RESERVED_IMAGE_NAMES) {
        stem = "$segment-image" + stem.substring(segment.length)
    }

    return stem + FILENAME_FORBIDDEN.replace(suffix, "")
}

/**
 * [name], or the next free `front-2.jpg`.
 *
 * CASE-INSENSITIVE, matching the desktop and matching the filesystems this has
 * to survive: `Front.JPG` beside `front.jpg` is two files on Linux and one on
 * Windows, and the exported ZIP is opened on both.
 */
fun uniqueImageName(name: String, taken: Set<String>): String {
    val folded = taken.mapTo(mutableSetOf()) { it.lowercase() }
    if (name.lowercase() !in folded) return name

    val (stem, suffix) = splitExtension(name)
    var n = 2
    while ("$stem-$n$suffix".lowercase() in folded) n += 1
    return "$stem-$n$suffix"
}

/**
 * `("front", ".jpg")`. A name that is all extension — `.gitkeep` — is all stem,
 * which is what keeps a leading dot from being read as an empty name.
 */
private fun splitExtension(name: String): Pair<String, String> {
    val dot = name.lastIndexOf('.')
    return if (dot > 0) name.take(dot) to name.substring(dot) else name to ""
}

private val FILENAME_FORBIDDEN = Regex("""[<>:"/\\|?*\x00-\x1f]""")

private const val IMAGE_NAME_MAX_LENGTH = 80

private const val FALLBACK_IMAGE_STEM = "image"

private val WINDOWS_RESERVED_IMAGE_NAMES: Set<String> = buildSet {
    addAll(listOf("con", "prn", "aux", "nul"))
    (1..9).forEach {
        add("com$it")
        add("lpt$it")
    }
}
