package io.github.sudomegas.saat.widget

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import java.io.File

/**
 * A photograph, decoded small enough to cross a process boundary.
 *
 * A widget is drawn in the LAUNCHER'S process and cannot open this app's private
 * files, so the bitmap has to be sent already decoded — and it travels through a
 * Binder transaction, whose buffer is about a megabyte. A modern phone photo is
 * several times that raw, so it is subsampled on the way in rather than
 * hopefully resized afterwards.
 */
internal fun widgetBitmap(file: File, maxDimension: Int = WIDGET_IMAGE_MAX): Bitmap? {
    if (!file.exists()) return null

    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeFile(file.path, bounds)
    if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null

    val options = BitmapFactory.Options().apply {
        inSampleSize = sampleSize(bounds.outWidth, bounds.outHeight, maxDimension)
    }
    return BitmapFactory.decodeFile(file.path, options)
}

/**
 * The power of two that brings the longer edge to at most [maxDimension].
 *
 * `BitmapFactory` only honours powers of two, so asking for anything else would
 * silently round anyway. Pure, so the arithmetic is testable without a decoder.
 */
internal fun sampleSize(width: Int, height: Int, maxDimension: Int): Int {
    val longest = maxOf(width, height)
    var sample = 1
    // Until the DECODED edge fits, not until halving would take it under.
    // The off-by-one version stopped a step early and let a 4000px photo
    // through at 1000px — four times the pixels, across a Binder transaction
    // whose whole budget is about a megabyte. Caught by the test below.
    while (longest / sample > maxDimension) sample *= 2
    return sample
}

/** Generous for a widget cell, small enough to stay well inside a Binder transaction. */
private const val WIDGET_IMAGE_MAX = 512
