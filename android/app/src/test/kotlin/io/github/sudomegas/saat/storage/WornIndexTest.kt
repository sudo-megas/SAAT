package io.github.sudomegas.saat.storage

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.io.File
import java.time.LocalDate

/**
 * The date-to-watch index — SPEC-ANDROID 5.5.
 *
 * Built in memory from each watch's own `worn` list, never from a central log.
 * These tests are what says so: nothing here reads a second store, and the
 * "deleting a watch takes its days with it" property is a consequence of that
 * rather than something the delete path has to remember.
 */
class WornIndexTest {

    private fun record(slug: String, status: String = Watch.STATUS_OWNED, vararg worn: LocalDate) =
        WatchRecord(
            slug = slug,
            dir = File("/watches/$slug"),
            watch = Watch(brand = "Seiko", model = slug, status = status, worn = worn.toList()),
        ).let { it.copy(loaded = it.watch) }

    private val monday = LocalDate.of(2026, 8, 3)

    @Test
    fun `every worn day maps to the watch that holds it`() {
        val index = listOf(
            record("skx", worn = arrayOf(monday, monday.plusDays(1))),
            record("f91w", worn = arrayOf(monday.plusDays(2))),
        ).wornIndex()

        assertEquals("skx", index[monday]?.slug)
        assertEquals("skx", index[monday.plusDays(1)]?.slug)
        assertEquals("f91w", index[monday.plusDays(2)]?.slug)
        assertEquals(3, index.size)
    }

    @Test
    fun `a day nobody wore is simply absent`() {
        val index = listOf(record("skx", worn = arrayOf(monday))).wornIndex()

        assertNull(index[monday.plusDays(1)])
    }

    @Test
    fun `only Owned watches hold days`() {
        // SPEC.md §5.12: a watch that is Sold, Gifted, Incoming or on a Wishlist
        // is not on anybody's wrist, so it does not appear in the calendar. The
        // desktop's build_worn_index filters the same way.
        val index = listOf(
            record("sold", status = "Sold", worn = arrayOf(monday)),
            record("wishlist", status = "Wishlist", worn = arrayOf(monday.plusDays(1))),
            record("owned", worn = arrayOf(monday.plusDays(2))),
        ).wornIndex()

        assertEquals(1, index.size)
        assertEquals("owned", index[monday.plusDays(2)]?.slug)
    }

    @Test
    fun `a record that did not load contributes nothing`() {
        val broken = WatchRecord("broken", File("/watches/broken"), loadError = "line 3: bad")

        assertEquals(emptyMap<LocalDate, WatchRecord>(), listOf(broken).wornIndex())
    }

    @Test
    fun `a day claimed by two hand-edited files resolves rather than throwing`() {
        // Only reachable by editing two watch.toml files by hand. The calendar
        // shows one watch per day because that is what it can draw; the files
        // still say what they say, and the next assignment tidies both.
        val index = listOf(
            record("a", worn = arrayOf(monday)),
            record("b", worn = arrayOf(monday)),
        ).wornIndex()

        assertEquals(1, index.size)
        assertEquals("b", index[monday]?.slug)
    }

    @Test
    fun `removing a watch from the list removes its days with it`() {
        // The property the whole no-central-log rule buys: nothing has to clean
        // up after a delete, because there is nowhere else the days were kept.
        val all = listOf(
            record("skx", worn = arrayOf(monday)),
            record("f91w", worn = arrayOf(monday.plusDays(1))),
        )

        assertEquals(2, all.wornIndex().size)
        assertEquals(
            mapOf(monday.plusDays(1) to "f91w"),
            all.filterNot { it.slug == "skx" }.wornIndex().mapValues { it.value.slug },
        )
    }
}
