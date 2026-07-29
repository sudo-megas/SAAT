package io.github.sudomegas.saat.storage

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Locale

/**
 * Every clause of SPEC-ANDROID 3's slug rule, tested separately.
 *
 * These are ports of the desktop's `saat/storage.py` rather than a fresh design,
 * so the test asks the same question throughout: would the desktop have produced
 * this? A slug generated differently on the two platforms is a watch that
 * duplicates itself the first time a collection crosses between them.
 */
class SlugTest {

    private val systemLocale: Locale = Locale.getDefault()

    @After
    fun restoreLocale() {
        Locale.setDefault(systemLocale)
    }

    // ---- the ordinary case ----------------------------------------------

    @Test
    fun `brand and model, lowercased and hyphenated`() {
        assertEquals("seiko-skx007", slugify("Seiko", "SKX007"))
        assertEquals("grand-seiko-sbga211", slugify("Grand Seiko", "SBGA211"))
    }

    @Test
    fun `runs of punctuation collapse to a single hyphen`() {
        assertEquals("tag-heuer-carrera", slugify("TAG  Heuer", "Carrera"))
        assertEquals("a-o-b", slugify("A. & O.", "B"))
        assertEquals("omega-speedmaster-professional", slugify("Omega", "Speedmaster — Professional"))
    }

    @Test
    fun `leading and trailing punctuation is stripped, not left as hyphens`() {
        assertEquals("seiko-5", slugify("...Seiko", "5!!!"))
        assertEquals("casio", slugify("  Casio  ", "  "))
    }

    @Test
    fun `accented letters are dropped rather than transliterated`() {
        // Measured against the desktop, and deliberately not "improved" on. An
        // accented letter is not folded to its ASCII base — it is simply not in
        // [a-z0-9], so it becomes a separator like any other character. `Züblin`
        // slugs as `z-blin`, which looks wrong and is exactly what the desktop
        // produces; transliterating here would give the same watch two different
        // folder names on the two platforms.
        assertEquals("z-blin-bauche", slugify("Züblin", "Ébauche"))

        // Nothing in [a-z0-9] survives at all, so the fallback name takes over.
        assertEquals("watch", slugify("時計", "腕"))
    }

    // ---- the Turkish dotless-i trap --------------------------------------

    @Test
    fun `slugs do not change when the phone is set to Turkish`() {
        // The live case, not the theoretical one: the owner's phone is Turkish.
        // A locale-sensitive lowercase maps I to the dotless ı, which is not in
        // [a-z0-9] and would be swallowed — so `Seiko` would slug as `seko` and
        // the same watch would exist twice the first time it crossed platforms.
        val turkish = Locale.forLanguageTag("tr-TR")

        Locale.setDefault(Locale.ENGLISH)
        val english = listOf(
            slugify("Seiko", "SKX007"),
            slugify("IWC", "Mark XVIII"),
            slugify("İzmir Saat", "Model I"),
            slugify("TISSOT", "PRX"),
        )

        Locale.setDefault(turkish)
        val onATurkishPhone = listOf(
            slugify("Seiko", "SKX007"),
            slugify("IWC", "Mark XVIII"),
            slugify("İzmir Saat", "Model I"),
            slugify("TISSOT", "PRX"),
        )

        assertEquals("the slug must not depend on the phone's locale", english, onATurkishPhone)
        assertEquals("seiko-skx007", onATurkishPhone[0])
        assertEquals("iwc-mark-xviii", onATurkishPhone[1])
        assertEquals("tissot-prx", onATurkishPhone[3])
    }

    @Test
    fun `a dotted capital I lowercases the way the desktop's Python does`() {
        // U+0130 lowercases, under the root locale, to "i" followed by a
        // COMBINING DOT ABOVE — two characters, not one. The combining mark is
        // then outside [a-z0-9] and becomes a separator, so `İzmir` slugs as
        // `i-zmir` on both platforms. Measured against the desktop rather than
        // reasoned about: the interesting thing is not that it is tidy, it is
        // that it is identical.
        assertEquals("i-zmir-saat-model-i", slugify("İzmir Saat", "Model I"))
    }

    // ---- whole-name rules -----------------------------------------------

    @Test
    fun `an empty result falls back rather than producing an unnameable folder`() {
        assertEquals("watch", slugify("", ""))
        assertEquals("watch", slugify("---", "!!!"))
        assertEquals("watch", slugify(" ", " "))
    }

    @Test
    fun `Windows device names are suffixed rather than rejected`() {
        assertEquals("con-watch", slugify("con", ""))
        assertEquals("nul-watch", slugify("NUL", ""))
        assertEquals("com1-watch", slugify("COM1", ""))
        assertEquals("lpt9-watch", slugify("LPT9", ""))
        assertEquals("aux-watch", slugify("aux", ""))
        assertEquals("prn-watch", slugify("PRN", ""))

        // The rule is about the finished name, so a separator between the two
        // halves takes it out of scope: `Com` + `1` is `com-1`, which Windows
        // has no objection to.
        assertEquals("com-1", slugify("Com", "1"))
    }

    @Test
    fun `a name that merely contains a device name is left alone`() {
        assertEquals("connor", slugify("Connor", ""))
        assertEquals("com10", slugify("COM10", ""))
        assertEquals("con-brand-x", slugify("Con Brand", "X"))
    }

    @Test
    fun `an over-long name is capped and never ends in a hyphen`() {
        val slug = slugify("A".repeat(60), "B".repeat(60))
        assertEquals(80, slug.length)
        assertFalse("a truncated slug must not end mid-separator", slug.endsWith("-"))

        // Truncation landing exactly on the separator must trim it away.
        val onTheSeam = slugify("C".repeat(80), "D")
        assertEquals(80, onTheSeam.length)
        assertFalse(onTheSeam.endsWith("-"))
        assertEquals("c".repeat(80), onTheSeam)
    }

    @Test
    fun `a pasted product description still yields a writable folder name`() {
        val slug = slugify(
            "Seiko Presage Cocktail Time Starlight",
            "SRPB43J1 Automatic Blue Sunburst Dial 40.5mm Stainless Steel Mens Dress Watch",
        )
        assertTrue(slug.length <= 80)
        assertTrue(slug.matches(Regex("[a-z0-9-]+")))
        assertTrue(slug.startsWith("seiko-presage-cocktail-time-starlight"))
    }

    // ---- collisions ------------------------------------------------------

    @Test
    fun `the first of a name is unsuffixed`() {
        assertEquals("seiko-skx007", uniqueSlug("Seiko", "SKX007", emptySet()))
        assertEquals("seiko-skx007", uniqueSlug("Seiko", "SKX007", setOf("casio-f-91w")))
    }

    @Test
    fun `collisions resolve with -2 then -3`() {
        assertEquals("seiko-skx007-2", uniqueSlug("Seiko", "SKX007", setOf("seiko-skx007")))
        assertEquals(
            "seiko-skx007-3",
            uniqueSlug("Seiko", "SKX007", setOf("seiko-skx007", "seiko-skx007-2")),
        )
        assertEquals(
            "seiko-skx007-4",
            uniqueSlug("Seiko", "SKX007", setOf("seiko-skx007", "seiko-skx007-2", "seiko-skx007-3")),
        )
    }

    @Test
    fun `a gap in the numbering is filled rather than skipped past`() {
        assertEquals(
            "seiko-skx007-2",
            uniqueSlug("Seiko", "SKX007", setOf("seiko-skx007", "seiko-skx007-3")),
        )
    }

    @Test
    fun `collisions are detected case-insensitively`() {
        // A hand-made `Seiko-SKX007` folder beside a generated `seiko-skx007` is
        // two watches on ext4 and one on NTFS. Compared case-insensitively on
        // every platform so the collection stays loadable in both directions —
        // on Windows the second save would otherwise open the first watch's
        // folder and overwrite it.
        assertEquals("seiko-skx007-2", uniqueSlug("Seiko", "SKX007", setOf("Seiko-SKX007")))
        assertEquals("seiko-skx007-2", uniqueSlug("Seiko", "SKX007", setOf("SEIKO-SKX007")))
        assertEquals(
            "seiko-skx007-3",
            uniqueSlug("Seiko", "SKX007", setOf("seiko-skx007", "Seiko-SKX007-2")),
        )
    }

    @Test
    fun `the device-name suffix happens before collision numbering`() {
        assertEquals("con-watch", uniqueSlug("con", "", emptySet()))
        assertEquals("con-watch-2", uniqueSlug("con", "", setOf("con-watch")))
    }

    // ---- what the loader skips -------------------------------------------

    @Test
    fun `entries starting with underscore or dot are hidden`() {
        assertTrue("the desktop's template must stay a template", isHiddenEntry("_template.toml"))
        assertTrue(isHiddenEntry("_work-in-progress"))
        assertTrue(isHiddenEntry(".DS_Store"))
        assertTrue(isHiddenEntry(".git"))

        assertFalse(isHiddenEntry("seiko-skx007"))
        assertFalse(isHiddenEntry("watch.toml"))
        assertFalse("only the first character counts", isHiddenEntry("a_b"))
    }
}
