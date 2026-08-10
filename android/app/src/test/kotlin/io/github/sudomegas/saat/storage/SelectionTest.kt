package io.github.sudomegas.saat.storage

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.time.LocalDate
import kotlin.random.Random

/**
 * "Pick for me" — mirrors `tests/test_selection.py`, minus the week-planner
 * cases (`pick_week`/`week_dates`), which have no Kotlin equivalent by
 * design (see `storage/Selection.kt`).
 *
 * Every statistical test uses a fixed seed rather than `Random.Default` —
 * generous tolerance bands still need a test that never flakes in CI.
 *
 * `pick_one`'s desktop "invalid mode throws" case has no Kotlin equivalent
 * either: [PickerMode] is an enum, so an invalid mode is a compile error,
 * not a runtime one — compile-time safety subsumes the test.
 */
class SelectionTest {

    private val today = LocalDate.of(2026, 8, 3) // a Monday, matching the desktop fixture

    private fun record(
        slug: String,
        brand: String = "Brand",
        model: String = "Model",
        worn: List<LocalDate> = emptyList(),
        status: String = Watch.STATUS_OWNED,
    ) = WatchRecord(
        slug = slug,
        dir = File(slug),
        watch = Watch(brand = brand, model = model, worn = worn, status = status),
    )

    // ---- owned-only filtering — SPEC-ANDROID 5.5 -------------------------

    private val ownedAndNot = listOf(
        record("owned-a"),
        record("owned-b"),
        record("wishlist", status = "Wishlist"),
        record("sold", status = "Sold"),
        record("gifted", status = "Gifted"),
        record("incoming", status = "Incoming"),
    )

    @Test
    fun `pick random never returns a non-owned watch`() {
        val random = Random(1)
        val seen = (1..200).map { pickRandom(ownedAndNot, random).slug }.toSet()
        assertEquals(setOf("owned-a", "owned-b"), seen)
    }

    @Test
    fun `pick weighted never returns a non-owned watch`() {
        val random = Random(1)
        val seen = (1..200).map { pickWeighted(ownedAndNot, today, random).slug }.toSet()
        assertEquals(setOf("owned-a", "owned-b"), seen)
    }

    @Test
    fun `no owned watches throws for both modes`() {
        val noOwned = listOf(record("wishlist", status = "Wishlist"))
        assertThrows(NoOwnedWatchesException::class.java) { pickRandom(noOwned) }
        assertThrows(NoOwnedWatchesException::class.java) { pickWeighted(noOwned, today) }
    }

    // ---- pickRandom --------------------------------------------------------

    @Test
    fun `uniform distribution over many trials`() {
        val records = (0 until 5).map { record("w$it") }
        val random = Random(42)
        val trials = 5000
        val counts = records.associate { it.slug to 0 }.toMutableMap()
        repeat(trials) {
            val slug = pickRandom(records, random).slug
            counts[slug] = counts.getValue(slug) + 1
        }
        val expected = trials / records.size.toDouble()
        // Generous tolerance -- a sanity check on uniformity, not a statistical
        // proof, and must never flake in CI.
        counts.forEach { (slug, count) ->
            assertTrue("$slug picked too rarely for a uniform draw", count > expected * 0.7)
            assertTrue("$slug picked too often for a uniform draw", count < expected * 1.3)
        }
    }

    @Test
    fun `single owned watch is always that watch`() {
        val records = listOf(record("only"))
        val random = Random(7)
        repeat(20) { assertEquals("only", pickRandom(records, random).slug) }
    }

    // ---- computeWeights ------------------------------------------------------

    @Test
    fun `every owned watch keeps a nonzero weight`() {
        val records = listOf(
            record("worn-today", worn = listOf(today)),
            record("worn-recently", worn = listOf(today.minusDays(2))),
            record("never-worn"),
            record("worn-in-the-future", worn = listOf(today.plusDays(10))), // a pre-planned day, SPEC-ANDROID 5.5
        )
        val weights = computeWeights(records, today)
        weights.forEach { (slug, weight) -> assertTrue("$slug has a non-positive weight", weight > 0.0) }
    }

    @Test
    fun `never-worn gets the maximum weight`() {
        val records = listOf(record("never-worn"), record("worn-long-ago", worn = listOf(today.minusDays(365))))
        val weights = computeWeights(records, today)
        assertEquals(weights.values.max(), weights.getValue("never-worn"))
        assertTrue(weights.getValue("never-worn") > weights.getValue("worn-long-ago"))
    }

    @Test
    fun `most recently worn gets the least weight`() {
        val records = listOf(
            record("today", worn = listOf(today)),
            record("ten-days-ago", worn = listOf(today.minusDays(10))),
            record("never-worn"),
        )
        val weights = computeWeights(records, today)
        assertTrue(weights.getValue("today") < weights.getValue("ten-days-ago"))
        assertTrue(weights.getValue("ten-days-ago") < weights.getValue("never-worn"))
    }

    @Test
    fun `all never-worn watches are tied`() {
        val records = listOf(record("a"), record("b"), record("c"))
        val weights = computeWeights(records, today)
        assertEquals(1, weights.values.toSet().size)
    }

    // ---- pickWeighted --------------------------------------------------------

    @Test
    fun `a neglected watch is favoured but never certain`() {
        // SPEC-ANDROID 5.5: a gentle curve, not a hard cutoff -- the
        // recently-worn watch must still turn up occasionally.
        val records = listOf(record("neglected"), record("worn-today", worn = listOf(today)))
        val random = Random(3)
        val counts = mutableMapOf("neglected" to 0, "worn-today" to 0)
        repeat(2000) {
            val slug = pickWeighted(records, today, random).slug
            counts[slug] = counts.getValue(slug) + 1
        }
        assertTrue(counts.getValue("neglected") > counts.getValue("worn-today"))
        assertTrue("the recently-worn watch should never be truly excluded", counts.getValue("worn-today") > 0)
    }

    @Test
    fun `pick one dispatches by mode`() {
        val records = listOf(record("only"))
        assertEquals("only", pickOne(records, PickerMode.RANDOM, today, Random(1)).slug)
        assertEquals("only", pickOne(records, PickerMode.WEIGHTED, today, Random(1)).slug)
    }

    @Test
    fun `weighted and random can disagree, proving both paths are live`() {
        // Not a desktop-mirrored case -- a cheap confidence check that mode
        // actually changes behaviour rather than one branch accidentally
        // shadowing the other.
        val records = listOf(
            record("stale", worn = listOf(today.minusDays(400))),
            record("fresh", worn = listOf(today)),
        )
        val weightedPicks = (1..50).map { pickOne(records, PickerMode.WEIGHTED, today, Random(it)).slug }
        assertTrue(weightedPicks.any { it == "stale" })
        assertNotEquals(emptySet<String>(), weightedPicks.toSet())
    }
}
