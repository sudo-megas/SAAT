package io.github.sudomegas.saat.storage

import java.io.File

/**
 * Every path the app is allowed to touch, derived from one root — SPEC-ANDROID 3.
 *
 * The root is injected rather than taken from a `Context`, which is what keeps
 * the whole storage layer testable as plain JVM JUnit against a temp directory:
 * no Robolectric, and no fixture files committed to the repository (hard rule 1).
 * In the app the root is `filesDir` and nothing else ever is.
 *
 * ```
 * files/
 * ├── watches/<slug>/watch.toml     the records
 * ├── media/<slug>/<filename>       the photographs
 * ├── config.toml
 * └── backups/                      timestamped copies, newest 20
 *     └── deleted/<slug>/           a removed watch, whole
 * ```
 *
 * WHY THE PHOTOGRAPHS SIT IN THEIR OWN TREE rather than inside each watch's
 * folder, unlike the desktop: Android's Auto Backup rules match `path` as a
 * literal prefix with no wildcard support at all, so "back up the records, never
 * the photographs" is only expressible if the two are separate top-level trees.
 * See SPEC-ANDROID 3. This changes the phone's internal layout only — §3.2's ZIP
 * contract re-roots everything under `media/<slug>` back into
 * `watches/<slug>/images` on export, so the archive keeps the desktop's exact
 * shape.
 *
 * That split works only because a watch's `images` key holds bare filenames
 * rather than paths, so it must continue to.
 */
class SaatPaths(val root: File) {

    val watchesDir: File get() = File(root, WATCHES)
    val mediaRoot: File get() = File(root, MEDIA)
    val backupsDir: File get() = File(root, BACKUPS)

    /** Where a deleted watch goes, whole, instead of being erased. */
    val deletedDir: File get() = File(backupsDir, DELETED)

    fun watchDir(slug: String): File = File(watchesDir, slug)

    fun watchToml(slug: String): File = File(watchDir(slug), WATCH_FILENAME)

    /** This watch's photographs. Not created until there is one to put in it. */
    fun watchMedia(slug: String): File = File(mediaRoot, slug)

    companion object {
        const val WATCHES = "watches"
        const val MEDIA = "media"
        const val BACKUPS = "backups"
        const val DELETED = "deleted"
        const val WATCH_FILENAME = "watch.toml"

        /**
         * The folder photographs re-root into inside `backups/deleted/<slug>/`
         * and inside the exported ZIP — the desktop's own name for them.
         */
        const val IMAGES = "images"
    }
}
