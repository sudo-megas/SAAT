package io.github.sudomegas.saat.ui.specs

import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.storage.Case
import io.github.sudomegas.saat.storage.Movement
import io.github.sudomegas.saat.storage.Strap
import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.fullyPopulatedWatch
import io.github.sudomegas.saat.storage.minimalWatch
import io.github.sudomegas.saat.ui.detail.SpecValue
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Specs list's presets — SPEC-ANDROID 5.3.
 *
 * The rule the whole screen rests on is that A ROW NEVER COLLAPSES: an absent
 * field is a cell carrying null, rendered as the muted em-dash, and never a cell
 * that is simply not there. A list whose rows changed length by watch would
 * break the alignment that is the entire reason the desktop's table had columns.
 */
class SpecsPresetTest {

    private fun cells(watch: Watch, preset: SpecsPreset) = specsCells(watch, preset)

    private fun labels(watch: Watch, preset: SpecsPreset) = cells(watch, preset).map { it.labelRes }

    @Test
    fun `a watch with nothing filled in still has a full row for every preset`() {
        SpecsPreset.entries.forEach { preset ->
            val row = cells(minimalWatch(), preset)

            assertTrue("$preset produced no cells", row.isNotEmpty())
            assertEquals(
                "$preset must be the same width for every watch",
                cells(fullyPopulatedWatch(), preset).size,
                row.size,
            )
        }
    }

    @Test
    fun `an absent field is a null cell, not a missing one`() {
        val row = cells(minimalWatch(), SpecsPreset.CASE)

        assertEquals(5, row.size)
        assertTrue(row.all { it.value == null })
        assertEquals(
            listOf(
                R.string.field_diameter,
                R.string.field_lug_to_lug,
                R.string.field_thickness,
                R.string.field_lug_width,
                R.string.field_water_resistance,
            ),
            row.map { it.labelRes },
        )
    }

    @Test
    fun `cells come out in the preset's order, not the schema group's`() {
        assertEquals(
            listOf(
                R.string.field_kind,
                R.string.field_caliber,
                R.string.field_power_reserve,
                R.string.field_frequency,
            ),
            labels(minimalWatch().copy(movement = Movement(kind = "Automatic")), SpecsPreset.MOVEMENT),
        )
    }

    @Test
    fun `quartz shows battery life in the same column mechanical shows power reserve`() {
        // The columns must still line up down the list. movementRows emits one
        // of the pair, so both rows are four cells wide and the fourth is
        // Frequency in each.
        val mechanical =
            labels(minimalWatch().copy(movement = Movement(kind = "Automatic")), SpecsPreset.MOVEMENT)
        val quartz =
            labels(minimalWatch().copy(movement = Movement(kind = "Quartz")), SpecsPreset.MOVEMENT)

        assertEquals(mechanical.size, quartz.size)
        assertEquals(R.string.field_power_reserve, mechanical[2])
        assertEquals(R.string.field_battery_life, quartz[2])
        assertEquals(R.string.field_frequency, quartz[3])
    }

    @Test
    fun `values are AM4's, formatted by AM4's own builders`() {
        // The point of building presets as a SELECTION rather than a second set
        // of field definitions: metres-and-bar, derived hertz and the em-dash
        // all behave here because they are the same code.
        val watch = minimalWatch().copy(
            case = Case(diameterMm = 41.0, waterResistanceM = 200),
            movement = Movement(bph = 28800),
        )

        val case = cells(watch, SpecsPreset.CASE).associateBy { it.labelRes }
        assertEquals(
            SpecValue.Resource(R.string.field_value_mm, listOf("41")),
            case.getValue(R.string.field_diameter).value,
        )
        assertEquals(
            SpecValue.Resource(R.string.field_value_water_resistance, listOf("200", "20")),
            case.getValue(R.string.field_water_resistance).value,
        )

        val movement = cells(watch, SpecsPreset.MOVEMENT).associateBy { it.labelRes }
        assertEquals(
            SpecValue.Resource(R.string.field_value_frequency, listOf("28800", "4")),
            movement.getValue(R.string.field_frequency).value,
        )
    }

    @Test
    fun `identity reads the filing fields and always states a status`() {
        val row = cells(minimalWatch(), SpecsPreset.IDENTITY).associateBy { it.labelRes }

        assertNull(row.getValue(R.string.field_reference).value)
        // The model defaults status to Owned, so this cell is never an em-dash.
        assertEquals(SpecValue.Plain(Watch.STATUS_OWNED), row.getValue(R.string.field_status).value)
    }

    @Test
    fun `straps show the fitted one, its effective width, and how many there are`() {
        val watch = minimalWatch().copy(
            case = Case(lugWidthMm = 20),
            straps = listOf(
                Strap(material = "NATO", colour = "Grey"),
                Strap(material = "Leather", colour = "Brown", fitted = true),
            ),
        )
        val row = cells(watch, SpecsPreset.STRAPS).associateBy { it.labelRes }

        assertEquals(SpecValue.Plain("Leather · Brown"), row.getValue(R.string.field_strap_fitted).value)
        // The fitted strap states no width of its own, so it borrows the case's
        // lug width — the same fallback every other screen uses.
        assertEquals(
            SpecValue.Resource(R.string.field_value_mm, listOf("20")),
            row.getValue(R.string.field_strap_width).value,
        )
        assertEquals(SpecValue.Plain("2"), row.getValue(R.string.field_strap_count).value)
    }

    @Test
    fun `a watch with no straps says zero rather than nothing`() {
        // Zero is a value here: it is how you notice, reading down the column,
        // which watches you have never bought a second strap for.
        val row = cells(minimalWatch(), SpecsPreset.STRAPS).associateBy { it.labelRes }

        assertEquals(SpecValue.Plain("0"), row.getValue(R.string.field_strap_count).value)
        assertNull(row.getValue(R.string.field_strap_fitted).value)
    }

    @Test
    fun `the token is the contract, not the constant name`() {
        SpecsPreset.entries.forEach {
            assertEquals(it, SpecsPreset.fromToken(it.token))
        }
        // A config written by a later version must not stop this one starting.
        assertEquals(SpecsPreset.DEFAULT, SpecsPreset.fromToken("compare"))
        assertEquals(SpecsPreset.DEFAULT, SpecsPreset.fromToken(null))
    }

    @Test
    fun `the fully populated fixture fills every preset`() {
        SpecsPreset.entries.forEach { preset ->
            val row = cells(fullyPopulatedWatch(), preset)
            assertNotNull("$preset had no filled cell", row.firstOrNull { it.value != null })
        }
    }
}
