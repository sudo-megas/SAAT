package io.github.sudomegas.saat.ui.form

import io.github.sudomegas.saat.storage.Movement
import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.minimalWatch
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The `enum*` lists, and the rule that makes them suggestions rather than
 * constraints.
 *
 * The VALUES themselves are checked against the desktop's own source by
 * `android/tools/parity_check.py enums`, which runs in CI — a respelled value
 * would fail nothing here, since every test would simply use the new spelling.
 * What is checked here is the behaviour around them.
 */
class EnumChoicesTest {

    private val allLists = listOf(
        GROUPS, STYLES, STATUSES, MOVEMENT_KINDS, ACCURACY_UNITS, CASE_MATERIALS,
        CRYSTALS, CROWNS, BEZELS, CASEBACKS, INDICES, COMPLICATIONS,
        STRAP_MATERIALS, CLASPS, CONDITIONS, LOG_KINDS, TIMING_POSITIONS,
    )

    @Test
    fun `every schema value carries a label resource`() {
        // A null labelRes means "the owner typed this", and the composable
        // renders it raw. A schema value with no resource would be an English
        // string that AM11's sweep cannot reach.
        val unlabelled = allLists.flatten().filter { it.labelRes == null }

        assertTrue("these would survive the Turkish sweep untranslated: $unlabelled", unlabelled.isEmpty())
    }

    @Test
    fun `no list is empty and none has a duplicate value`() {
        allLists.forEach { list ->
            assertTrue(list.isNotEmpty())
            assertEquals(list.map { it.value }.distinct().size, list.size)
        }
    }

    @Test
    fun `the collection's own values are offered after the schema's`() {
        // SPEC.md §4: "the listed values plus every value already used elsewhere
        // in the collection". The schema's vocabulary comes first — a one-off
        // value typed last year should not push it down the list.
        val watches = listOf(
            minimalWatch().copy(case = minimalWatch().case.copy(material = "Chromed brass")),
            minimalWatch().copy(case = minimalWatch().case.copy(material = "Titanium")),
        )

        val offered = CASE_MATERIALS.plusExisting(existingValues(watches) { it.case.material })

        assertEquals(CASE_MATERIALS, offered.take(CASE_MATERIALS.size))
        assertEquals(listOf("Chromed brass"), offered.drop(CASE_MATERIALS.size).map { it.value })
    }

    @Test
    fun `a collection value that only differs in case is not offered twice`() {
        val watches = listOf(
            minimalWatch().copy(case = minimalWatch().case.copy(material = "stainless steel")),
        )

        val offered = CASE_MATERIALS.plusExisting(existingValues(watches) { it.case.material })

        assertEquals(CASE_MATERIALS.size, offered.size)
    }

    @Test
    fun `a harvested value has no label, because it is the owner's word`() {
        val watches = listOf(minimalWatch().copy(style = "Skin diver"))

        val harvested = STYLES.plusExisting(existingValues(watches) { it.style }).last()

        assertEquals("Skin diver", harvested.value)
        assertNull(harvested.labelRes)
        assertNotNull(STYLES.first().labelRes)
    }

    @Test
    fun `blank and absent values are never harvested`() {
        val watches = listOf(
            minimalWatch().copy(style = "  "),
            minimalWatch().copy(style = null),
            minimalWatch().copy(style = "Diver"),
        )

        assertEquals(listOf("Diver"), existingValues(watches) { it.style })
    }

    @Test
    fun `list fields are harvested element by element`() {
        val watches = listOf(
            minimalWatch().copy(dial = minimalWatch().dial.copy(complications = listOf("Date", "Big Date"))),
            minimalWatch().copy(dial = minimalWatch().dial.copy(complications = listOf("Big Date"))),
        )

        assertEquals(listOf("Big Date", "Date"), existingListValues(watches) { it.dial.complications })
    }

    @Test
    fun `only quartz and solar run on a battery`() {
        // Mecha-quartz and Kinetic carry a battery too, but they also have a
        // mainspring or a rotor, and which figure their owner tracks is theirs
        // to say. This is the desktop's QUARTZ_LIKE_KINDS, not a guess.
        listOf("Quartz", "Solar", "quartz", " SOLAR ").forEach {
            assertTrue(it, runsOnBattery(it))
        }
        listOf("Automatic", "Manual", "Mecha-quartz", "Kinetic", null, "", "Spring Drive").forEach {
            assertFalse(it.orEmpty(), runsOnBattery(it))
        }
    }

    @Test
    fun `status is the one closed list and Owned is in it`() {
        // The model defaults status to Owned and the desktop offers no blank, so
        // a form that could clear it would write a value the loader then reads
        // back as Owned anyway.
        assertTrue(STATUSES.any { it.value == Watch.STATUS_OWNED })
    }

    @Test
    fun `accuracy units are the two the schema names`() {
        assertEquals(listOf("sec/day", "sec/month"), ACCURACY_UNITS.map { it.value })
        assertNull(Movement().accuracyUnit)
    }
}
