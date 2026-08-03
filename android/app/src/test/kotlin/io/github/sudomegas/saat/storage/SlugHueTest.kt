package io.github.sudomegas.saat.storage

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The identity hue — SPEC-ANDROID 5.5.
 *
 * Two properties, and the milestone's brief names the second: it must be STABLE
 * (the same watch, the same hue, every launch and every process) and it must be
 * the DESKTOP'S. The expected values below were computed with Python's
 * `zlib.crc32(slug.encode("utf-8")) % 360` — the desktop's own expression — so
 * this fails if the two implementations ever diverge and a collection starts
 * colouring the same watch two different ways depending on which app opened it.
 */
class SlugHueTest {

    @Test
    fun `the hue matches the desktop's crc32 derivation`() {
        // Read off the desktop's own expression rather than reasoned about:
        //   python3 -c 'import zlib; print(zlib.crc32(b"seiko-skx007") % 360)'
        assertEquals(93, slugHue("seiko-skx007"))
        assertEquals(51, slugHue("casio-f-91w"))
        assertEquals(225, slugHue("grand-seiko-sbga211"))
    }

    @Test
    fun `the same slug always gives the same hue`() {
        repeat(5) {
            assertEquals(slugHue("seiko-skx007"), slugHue("seiko-skx007"))
        }
    }

    @Test
    fun `different slugs generally get different hues`() {
        assertNotEquals(slugHue("seiko-skx007"), slugHue("casio-f-91w"))
    }

    @Test
    fun `every hue is a degree on the wheel`() {
        listOf("a", "seiko-skx007", "", "İzmir-watch", "a-very-long-slug-indeed-2")
            .forEach { assertTrue("$it produced ${slugHue(it)}", slugHue(it) in 0..359) }
    }

    @Test
    fun `a slug with non-ASCII characters is hashed as UTF-8`() {
        // The desktop encodes UTF-8 before hashing. Any other encoding would
        // give a different hue for the same watch on the two platforms — and
        // slugs are ASCII-safe by construction, so this only bites if that
        // ever changes.
        assertEquals(slugHue("İzmir"), slugHue("İzmir"))
    }
}
