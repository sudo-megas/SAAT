package io.github.sudomegas.saat.ui.compare

import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.storage.Case
import io.github.sudomegas.saat.storage.Movement
import io.github.sudomegas.saat.storage.Strap
import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.WatchRecord
import io.github.sudomegas.saat.storage.fullyPopulatedWatch
import io.github.sudomegas.saat.storage.minimalWatch
import io.github.sudomegas.saat.ui.detail.SpecRow
import io.github.sudomegas.saat.ui.detail.SpecValue
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * SPEC-ANDROID 5.4's three rules, as assertions: shared values dim, differing
 * values do not, and a row neither watch can fill is not drawn at all.
 *
 * Pure, for the reason [comparePage] is pure — the classification is the whole
 * feature, and asserting a colour against a rendered `Row` would need a device
 * and would still be testing the wrong layer.
 */
class ComparePageTest {

    private fun record(slug: String, watch: Watch) =
        WatchRecord(slug, File("/watches/$slug"), watch = watch, loaded = watch)

    private fun page(left: Watch, right: Watch): ComparePage? = comparePage(
        left = record("left", left),
        leftMedia = File("/media/left"),
        right = record("right", right),
        rightMedia = File("/media/right"),
    )

    private fun rows(left: Watch, right: Watch, titleRes: Int): List<CompareRow> =
        page(left, right)!!.groups.firstOrNull { it.titleRes == titleRes }?.rows.orEmpty()

    private fun row(left: Watch, right: Watch, titleRes: Int, labelRes: Int): CompareRow? =
        rows(left, right, titleRes).firstOrNull { it.labelRes == labelRes }

    // --- the three classification rules --------------------------------------

    @Test
    fun `a value both watches share is dimmed`() {
        val left = minimalWatch().copy(case = Case(material = "Steel"))
        val right = minimalWatch().copy(case = Case(material = "Steel"))

        val material = row(left, right, R.string.screen_detail_group_case, R.string.field_case_material)

        assertEquals(RowContrast.SHARED, material!!.contrast)
    }

    @Test
    fun `values that disagree sit at full contrast`() {
        val left = minimalWatch().copy(case = Case(material = "Steel"))
        val right = minimalWatch().copy(case = Case(material = "Titanium"))

        val material = row(left, right, R.string.screen_detail_group_case, R.string.field_case_material)

        assertEquals(RowContrast.DIFFERS, material!!.contrast)
    }

    /**
     * The rule that is easy to get wrong. A value on one side and nothing on the
     * other is a DIFFERENCE, not a match — the desktop's `_all_present_and_equal`
     * fails on any absent value before it ever compares, and dimming this row
     * would hide the most interesting kind of row on the screen.
     */
    @Test
    fun `present on one side and absent on the other differs`() {
        val left = minimalWatch().copy(case = Case(material = "Steel"))
        val right = minimalWatch()

        val material = row(left, right, R.string.screen_detail_group_case, R.string.field_case_material)

        assertEquals(RowContrast.DIFFERS, material!!.contrast)
        assertNotNull(material.left)
        assertNull(material.right)
    }

    @Test
    fun `a row neither watch can fill is not built`() {
        val left = minimalWatch().copy(case = Case(material = "Steel"))
        val right = minimalWatch().copy(case = Case(material = "Titanium"))

        // Both have a case material, so the group exists; neither has a crystal.
        assertNull(row(left, right, R.string.screen_detail_group_case, R.string.field_crystal))
    }

    @Test
    fun `a group with nothing to say is hidden entirely`() {
        val titles = page(minimalWatch(), minimalWatch())!!.groups.map { it.titleRes }

        // Two watches with only brand and model: Identity survives on those two
        // fields alone (and Status, which the model defaults), and every other
        // group drops out rather than rendering as a column of em-dashes.
        assertEquals(listOf(R.string.screen_detail_group_identity), titles)
    }

    // --- the alignment trap ---------------------------------------------------

    /**
     * THE TEST THIS FILE EXISTS FOR.
     *
     * `movementRows` is conditional: a mechanical watch gets a `power_reserve`
     * row and a quartz gets `battery_life`, so the two lists are not the same
     * length and position N is not the same attribute on both sides. Pairing by
     * index would put the automatic's 72-hour power reserve opposite the
     * quartz's 2-year battery life, classify them as differing, and be
     * confidently wrong on both rows.
     *
     * Keyed by label, each figure appears on its own row with the other side
     * absent.
     */
    @Test
    fun `a mechanical against a quartz keeps power reserve and battery life apart`() {
        val mechanical = minimalWatch().copy(
            movement = Movement(kind = "Automatic", powerReserveHours = 72.0),
        )
        val quartz = minimalWatch().copy(
            movement = Movement(kind = "Quartz", batteryLifeYears = 2.0),
        )

        val powerReserve = row(
            mechanical, quartz,
            R.string.screen_detail_group_movement, R.string.field_power_reserve,
        )
        val batteryLife = row(
            mechanical, quartz,
            R.string.screen_detail_group_movement, R.string.field_battery_life,
        )

        // The mechanical's figure is on the left of the power-reserve row and
        // the quartz has nothing there — NOT its battery life.
        assertNotNull(powerReserve!!.left)
        assertNull(powerReserve.right)

        // And the mirror: the battery row carries the quartz's figure on the
        // right, with the mechanical absent.
        assertNull(batteryLife!!.left)
        assertNotNull(batteryLife.right)
    }

    /**
     * Both figures appear where their own side puts them, adjacent, rather than
     * the one-sided row being stranded at the bottom of the group — which is
     * what a plain union of the two label lists would have produced.
     */
    @Test
    fun `a label only one side carries lands in its natural place`() {
        val mechanical = listOf(
            SpecRow(R.string.field_caliber, SpecValue.Plain("6R15")),
            SpecRow(R.string.field_power_reserve, SpecValue.Plain("50 h")),
            SpecRow(R.string.field_jewels, SpecValue.Plain("23")),
        )
        val quartz = listOf(
            SpecRow(R.string.field_caliber, SpecValue.Plain("VK63")),
            SpecRow(R.string.field_battery_life, SpecValue.Plain("3 y")),
            SpecRow(R.string.field_jewels, SpecValue.Plain("0")),
        )

        assertEquals(
            listOf(
                R.string.field_caliber,
                R.string.field_power_reserve,
                R.string.field_battery_life,
                R.string.field_jewels,
            ),
            mergeLabels(mechanical, quartz),
        )
    }

    @Test
    fun `merging two identical label orders changes nothing`() {
        val rows = listOf(
            SpecRow(R.string.field_caliber, null),
            SpecRow(R.string.field_jewels, null),
        )

        assertEquals(rows.map { it.labelRes }, mergeLabels(rows, rows))
    }

    /**
     * A pathological input the current builders cannot produce — both sides
     * carrying both labels in opposite orders — must still terminate and must
     * still emit each label exactly once. The `LinkedHashSet` is what guarantees
     * the second half of that.
     */
    @Test
    fun `opposed orders still produce each label once`() {
        val forwards = listOf(
            SpecRow(R.string.field_caliber, null),
            SpecRow(R.string.field_jewels, null),
        )
        val backwards = forwards.reversed()

        val merged = mergeLabels(forwards, backwards)

        assertEquals(merged.distinct(), merged)
        assertEquals(setOf(R.string.field_caliber, R.string.field_jewels), merged.toSet())
    }

    // --- columns and groups ---------------------------------------------------

    @Test
    fun `identity comes first and carries brand and model`() {
        val page = page(fullyPopulatedWatch(), minimalWatch())!!

        assertEquals(R.string.screen_detail_group_identity, page.groups.first().titleRes)
        assertNotNull(
            row(
                fullyPopulatedWatch(), minimalWatch(),
                R.string.screen_detail_group_identity, R.string.field_brand,
            ),
        )
    }

    @Test
    fun `the straps group compares the fitted strap, not the whole list`() {
        val left = minimalWatch().copy(
            straps = listOf(
                Strap(material = "Rubber", fitted = false),
                Strap(material = "Leather", fitted = true),
            ),
        )
        val right = minimalWatch().copy(straps = listOf(Strap(material = "Leather", fitted = true)))

        val material = row(
            left, right,
            R.string.screen_detail_group_straps, R.string.field_strap_material,
        )

        // Leather against Leather — the unfitted rubber strap is not what is on
        // the wrist and does not enter the comparison.
        assertEquals(RowContrast.SHARED, material!!.contrast)
        assertEquals(SpecValue.Plain("Leather"), material.left)
    }

    /**
     * A strap with no width of its own matches on its owner's lug width — SPEC.md
     * §4 — so two watches whose fitted straps both say nothing still compare on
     * the figure the owner would actually measure.
     */
    @Test
    fun `a strap with no width falls back to its own watch's lug width`() {
        val left = minimalWatch().copy(
            case = Case(lugWidthMm = 20),
            straps = listOf(Strap(fitted = true)),
        )
        val right = minimalWatch().copy(
            case = Case(lugWidthMm = 22),
            straps = listOf(Strap(fitted = true)),
        )

        val width = row(
            left, right,
            R.string.screen_detail_group_straps, R.string.field_strap_width,
        )

        assertEquals(RowContrast.DIFFERS, width!!.contrast)
    }

    @Test
    fun `the columns name their watches and resolve photographs into media`() {
        val withPhoto = minimalWatch().copy(images = listOf("front.jpg"))
        val page = page(withPhoto, minimalWatch())!!

        assertEquals("left", page.left.slug)
        assertEquals("Casio", page.left.brand)
        assertEquals(File("/media/left/front.jpg"), page.left.image)
        assertNull(page.right.image)
    }

    /**
     * A hand-edited `images` entry with a directory part in it must not escape
     * the watch's own media folder — the same `File(it).name` guard the grid and
     * the detail page apply.
     */
    @Test
    fun `an images entry with a path is reduced to its filename`() {
        val sneaky = minimalWatch().copy(images = listOf("../../etc/passwd"))

        assertEquals(File("/media/left/passwd"), page(sneaky, minimalWatch())!!.left.image)
    }

    @Test
    fun `a record that did not load has no page`() {
        val broken = WatchRecord("broken", File("/watches/broken"), loadError = "bad TOML")

        assertNull(
            comparePage(
                left = broken,
                leftMedia = File("/media/broken"),
                right = record("right", minimalWatch()),
                rightMedia = File("/media/right"),
            ),
        )
    }

    @Test
    fun `every built row has something to say`() {
        val page = page(fullyPopulatedWatch(), minimalWatch())!!

        assertFalse(page.groups.isEmpty())
        assertTrue(
            "a row where neither watch has a value should never be built",
            page.groups.all { group ->
                group.rows.all { it.left != null || it.right != null }
            },
        )
    }

    @Test
    fun `two watches are the whole screen`() {
        assertEquals(2, COMPARE_WATCHES)
    }
}
