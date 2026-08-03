package io.github.sudomegas.saat.storage

import java.io.File
import java.io.FileOutputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption

/**
 * Write a file so that a reader either sees the whole previous version or the
 * whole new one, never a truncated file — a port of the desktop's
 * `saat/atomic.py`.
 *
 * The temp file is created in the SAME directory as the target, because
 * `ATOMIC_MOVE` is only guaranteed within one filesystem. `fsync` before the
 * rename is what makes the content durable rather than merely visible; without
 * it a power loss can leave a correctly-named file full of zeroes.
 */
fun writeAtomically(target: File, content: String) {
    writeAtomically(target) { out -> out.write(content.toByteArray(Charsets.UTF_8)) }
}

/**
 * The same guarantee for bytes that arrive as a stream — a photograph being
 * copied in from the picker or the camera (AM5).
 *
 * A half-copied photograph matters for the same reason a half-written
 * `watch.toml` does: `images` in the record would name a file that decodes to
 * nothing, and the grid would show a placeholder tile for a watch the owner had
 * just photographed. The temp file also means an interrupted copy leaves a
 * `.tmp` the loader skips rather than a broken `.jpg` it lists.
 */
fun writeAtomically(target: File, write: (FileOutputStream) -> Unit) {
    val dir = target.parentFile ?: error("target has no parent directory: $target")
    dir.mkdirs()

    val temp = File.createTempFile(".${target.name}.", ".tmp", dir)
    try {
        FileOutputStream(temp).use { out ->
            write(out)
            out.flush()
            out.fd.sync()
        }
        Files.move(
            temp.toPath(),
            target.toPath(),
            StandardCopyOption.ATOMIC_MOVE,
            StandardCopyOption.REPLACE_EXISTING,
        )
    } catch (e: Throwable) {
        temp.delete()
        throw e
    }
}
