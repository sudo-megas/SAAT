package io.github.sudomegas.saat

import androidx.compose.ui.graphics.Color

/**
 * A verbatim port of the desktop's `tests/contrast.py`.
 *
 * Kept byte-for-byte equivalent on purpose: the desktop authored its palettes
 * against these exact numbers, so a port that rounds differently would either
 * pass colours the desktop rejected or reject colours it shipped.
 *
 * Note the sRGB threshold is 0.03928 — the WCAG 2.0 value the desktop uses —
 * not the 0.04045 that appears in some later restatements. The difference is
 * tiny but it is the difference between reproducing the desktop's measurements
 * and merely getting close to them.
 */
private fun channel(value: Int): Double {
    val c = value / 255.0
    return if (c <= 0.03928) c / 12.92 else Math.pow((c + 0.055) / 1.055, 2.4)
}

fun relativeLuminance(color: Color): Double {
    val argb = color.value.toLong() ushr 32
    val r = ((argb shr 16) and 0xFF).toInt()
    val g = ((argb shr 8) and 0xFF).toInt()
    val b = (argb and 0xFF).toInt()
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

fun contrastRatio(a: Color, b: Color): Double {
    val la = relativeLuminance(a)
    val lb = relativeLuminance(b)
    val lighter = maxOf(la, lb)
    val darker = minOf(la, lb)
    return (lighter + 0.05) / (darker + 0.05)
}
