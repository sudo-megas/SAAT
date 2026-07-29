package io.github.sudomegas.saat.config

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
    val dir = target.parentFile ?: error("target has no parent directory: $target")
    dir.mkdirs()

    val temp = File.createTempFile(".${target.name}.", ".tmp", dir)
    try {
        FileOutputStream(temp).use { out ->
            out.write(content.toByteArray(Charsets.UTF_8))
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
