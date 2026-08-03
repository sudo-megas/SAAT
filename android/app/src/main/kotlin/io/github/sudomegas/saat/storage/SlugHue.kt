package io.github.sudomegas.saat.storage

import java.util.zip.CRC32

/**
 * One hue per watch, derived from its slug — SPEC-ANDROID 5.5's year view, and
 * the calendar cell for a watch with no photograph.
 *
 * CRC32, NOT `hashCode()`, and that is a parity requirement rather than a
 * preference. The desktop's `slug_color` uses `zlib.crc32` because Python's
 * `hash()` is randomised per process, so the same watch would land on a
 * different hue every launch. Kotlin's `String.hashCode` happens to be stable,
 * but it is a DIFFERENT function — a collection opened on the phone and on the
 * desktop would then colour the same watch two different ways, and the hue is
 * meant to be how you recognise a watch across screens.
 *
 * In the model layer and computed once, as the milestone's brief asks: the
 * calendar's photo-less cells and the year view's chips read the same function,
 * and so will anything else that wants to mark a watch's identity.
 *
 * 0–359, ready for HSV. The saturation and value belong to the theme, because
 * they depend on whether the plate underneath is light or dark.
 */
fun slugHue(slug: String): Int {
    val crc = CRC32()
    crc.update(slug.toByteArray(Charsets.UTF_8))
    return (crc.value % HUE_DEGREES).toInt()
}

private const val HUE_DEGREES = 360L
