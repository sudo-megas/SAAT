package io.github.sudomegas.saat.storage

import io.github.sudomegas.saat.ui.detail.compatibleStrapCards
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Strap compatibility — AM9c, ported from the desktop's `strap_compat.py`.
 *
 * Every clause of that module's four rules gets its own case here, because the
 * failure mode of a partial port is silent: a rule dropped on this side simply
 * means the two apps answer "what else fits this watch" differently on the same
 * collection, and nobody notices until they are standing at a drawer.
 */
class StrapCompatTest {

    private fun record(slug: String, watch: Watch?) =
        WatchRecord(slug, File("/watches/$slug"), watch = watch, loaded = watch)

    private fun watch(
        lugWidthMm: Int? = null,
        status: String = Watch.STATUS_OWNED,
        straps: List<Strap> = emptyList(),
    ) = Watch(
        brand = "Test",
        model = "Watch",
        status = status,
        case = Case(lugWidthMm = lugWidthMm),
        straps = straps,
    )

    private fun matches(target: WatchRecord, vararg others: WatchRecord) =
        compatibleStraps(target, listOf(target, *others))

    // --- the width match ------------------------------------------------------

    @Test
    fun `a strap of the same width on another watch fits`() {
        val target = record("target", watch(lugWidthMm = 20))
        val other = record("other", watch(lugWidthMm = 20, straps = listOf(Strap(widthMm = 20))))

        assertEquals(1, matches(target, other).size)
    }

    @Test
    fun `a strap of a different width does not`() {
        val target = record("target", watch(lugWidthMm = 20))
        val other = record("other", watch(lugWidthMm = 22, straps = listOf(Strap(widthMm = 22))))

        assertTrue(matches(target, other).isEmpty())
    }

    /**
     * The rule that makes the feature useful at all. Most straps in a real
     * collection never get a width typed in, so they match on their OWN watch's
     * lug width — SPEC.md §4's "defaults to `case.lug_width_mm`". Matching on
     * the raw field would find almost nothing and the section would look broken.
     */
    @Test
    fun `a strap with no width of its own uses its owner's lug width`() {
        val target = record("target", watch(lugWidthMm = 20))
        val other = record("other", watch(lugWidthMm = 20, straps = listOf(Strap(material = "Leather"))))

        assertEquals(1, matches(target, other).size)
    }

    @Test
    fun `a strap states its own width even when its owner disagrees`() {
        val target = record("target", watch(lugWidthMm = 20))
        // A 22 mm watch carrying a 20 mm strap: the strap's own figure wins.
        val other = record("other", watch(lugWidthMm = 22, straps = listOf(Strap(widthMm = 20))))

        assertEquals(1, matches(target, other).size)
    }

    // --- the silences ---------------------------------------------------------

    /**
     * No lug width means nothing to match against. An empty list, NOT everything
     * — which is what a null-tolerant comparison would have quietly produced.
     */
    @Test
    fun `a watch with no lug width matches nothing`() {
        val target = record("target", watch(lugWidthMm = null))
        val other = record("other", watch(lugWidthMm = 20, straps = listOf(Strap(widthMm = 20))))

        assertTrue(matches(target, other).isEmpty())
    }

    @Test
    fun `a watch never lists its own straps`() {
        val target = record(
            "target",
            watch(lugWidthMm = 20, straps = listOf(Strap(widthMm = 20), Strap(widthMm = 20))),
        )

        assertTrue(matches(target).isEmpty())
    }

    /**
     * Compared by SLUG rather than by identity: the record handed in may be a
     * different instance of the same watch than the one in the collection list,
     * and an identity check would then list a watch's own straps back to it.
     */
    @Test
    fun `self-exclusion survives two instances of the same record`() {
        val watch = watch(lugWidthMm = 20, straps = listOf(Strap(widthMm = 20)))
        val target = record("target", watch)
        val sameWatchAgain = record("target", watch.copy())

        assertTrue(compatibleStraps(target, listOf(sameWatchAgain)).isEmpty())
    }

    // --- the Owned rule -------------------------------------------------------

    @Test
    fun `a strap on a watch that is not owned is not available`() {
        val target = record("target", watch(lugWidthMm = 20))
        val wishlist = record(
            "wishlist",
            watch(lugWidthMm = 20, status = "Wishlist", straps = listOf(Strap(widthMm = 20))),
        )

        assertTrue(matches(target, wishlist).isEmpty())
    }

    @Test
    fun `a watch that is not owned is not asking what fits it`() {
        val sold = record("sold", watch(lugWidthMm = 20, status = "Sold"))
        val other = record("other", watch(lugWidthMm = 20, straps = listOf(Strap(widthMm = 20))))

        assertTrue(matches(sold, other).isEmpty())
    }

    // --- shape ----------------------------------------------------------------

    @Test
    fun `a record that did not load contributes nothing and asks nothing`() {
        val broken = record("broken", null)
        val other = record("other", watch(lugWidthMm = 20, straps = listOf(Strap(widthMm = 20))))
        val target = record("target", watch(lugWidthMm = 20))

        assertTrue(matches(broken, other).isEmpty())
        assertEquals(1, matches(target, other, broken).size)
    }

    /**
     * Two identical straps on two watches are two straps the owner could reach
     * for. Collapsing them would hide where the second one is.
     */
    @Test
    fun `identical straps on different watches are both listed`() {
        val target = record("target", watch(lugWidthMm = 20))
        val a = record("a", watch(lugWidthMm = 20, straps = listOf(Strap(material = "Leather", widthMm = 20))))
        val b = record("b", watch(lugWidthMm = 20, straps = listOf(Strap(material = "Leather", widthMm = 20))))

        assertEquals(2, matches(target, a, b).size)
    }

    @Test
    fun `one watch can contribute two of its straps`() {
        val target = record("target", watch(lugWidthMm = 20))
        val other = record(
            "other",
            watch(lugWidthMm = 20, straps = listOf(Strap(widthMm = 20), Strap(widthMm = 20))),
        )

        assertEquals(2, matches(target, other).size)
    }

    // --- the cards ------------------------------------------------------------

    @Test
    fun `a card names its owner and resolves the photograph into that owner's media`() {
        val target = record("target", watch(lugWidthMm = 20))
        val other = WatchRecord(
            "seiko-sarb033",
            File("/watches/seiko-sarb033"),
            watch = Watch(
                brand = "Seiko",
                model = "SARB033",
                case = Case(lugWidthMm = 20),
                straps = listOf(Strap(material = "Leather", image = "strap.jpg")),
            ),
        ).let { it.copy(loaded = it.watch) }

        val card = compatibleStrapCards(
            target = target,
            all = listOf(target, other),
            mediaFor = { slug -> File("/media/$slug") },
        ).single()

        assertEquals("seiko-sarb033", card.ownerSlug)
        assertEquals("Seiko", card.ownerBrand)
        assertEquals("SARB033", card.ownerModel)
        // The photograph comes from the STRAP'S OWNER's folder, not the target's.
        assertEquals(File("/media/seiko-sarb033/strap.jpg"), card.strap.image)
    }

    /**
     * The card's width shows the effective figure, so a strap that inherited its
     * owner's lug width still prints a number rather than an em-dash.
     */
    @Test
    fun `a card shows the effective width`() {
        val target = record("target", watch(lugWidthMm = 20))
        val other = record("other", watch(lugWidthMm = 20, straps = listOf(Strap(material = "Rubber"))))

        val card = compatibleStrapCards(target, listOf(target, other)) { File("/media/$it") }.single()

        assertEquals(20, card.strap.widthMm)
    }
}
