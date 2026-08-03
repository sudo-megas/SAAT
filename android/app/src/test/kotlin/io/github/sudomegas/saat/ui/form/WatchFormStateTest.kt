package io.github.sudomegas.saat.ui.form

import io.github.sudomegas.saat.storage.Strap
import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.fittedCount
import io.github.sudomegas.saat.storage.fullyPopulatedWatch
import io.github.sudomegas.saat.storage.minimalWatch
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

/**
 * The add/edit form's rules — SPEC-ANDROID 5.7.
 *
 * The form is plain data on purpose, so the two promises the milestone is
 * graded on are assertions rather than a device walk-through: saving with only
 * brand and model must succeed, and backing out with unsaved changes must
 * prompt. The first is [WatchFormState.canSave]; the second is state inequality
 * against the state the form opened with, which is what these tests check by
 * comparing states directly.
 */
class WatchFormStateTest {

    // --- validation: the one rule, and no others -----------------------------

    @Test
    fun `brand and model alone are enough to save`() {
        val form = WatchFormState.empty().copy(brand = "Casio", model = "F-91W")

        assertTrue(form.canSave)
        assertEquals(Watch(brand = "Casio", model = "F-91W", acquisition = form.toWatch().acquisition), form.toWatch())
    }

    @Test
    fun `a missing brand or model is the only thing that blocks`() {
        assertFalse(WatchFormState.empty().canSave)
        assertFalse(WatchFormState.empty().copy(brand = "Casio").canSave)
        assertFalse(WatchFormState.empty().copy(model = "F-91W").canSave)
        assertFalse(WatchFormState.empty().copy(brand = "  ", model = "F-91W").canSave)
    }

    @Test
    fun `nothing else can block a save, however wrong it looks`() {
        // Validation "may advise, it may never obstruct". A diameter of "abc"
        // and a rating of 900 are still a saveable watch; the values that do not
        // parse are simply absent, and the ones that do are written as given.
        val form = WatchFormState.empty().copy(
            brand = "Casio",
            model = "F-91W",
            diameterMm = "abc",
            jewels = "not a number",
            rating = "900",
        )

        assertTrue(form.canSave)
        val watch = form.toWatch()
        assertNull(watch.case.diameterMm)
        assertNull(watch.movement.jewels)
        assertEquals(900, watch.rating)
    }

    // --- blank is absent -----------------------------------------------------

    @Test
    fun `a cleared field becomes null, never an empty string`() {
        // WatchToml omits a null key entirely, so clearing a field removes the
        // line from the file rather than leaving `nickname = ""` behind.
        val form = WatchFormState.empty().copy(
            brand = "Casio",
            model = "F-91W",
            nickname = "   ",
            notes = "",
            origin = "\t",
        )
        val watch = form.toWatch()

        assertNull(watch.nickname)
        assertNull(watch.notes)
        assertNull(watch.movement.origin)
    }

    @Test
    fun `a wholly blank log or timing row is dropped rather than written`() {
        val form = WatchFormState.empty().copy(
            brand = "Casio",
            model = "F-91W",
            log = listOf(LogFormState(), LogFormState(note = "Arrived.")),
            timing = listOf(TimingFormState(), TimingFormState(deviationSec = "2")),
        )
        val watch = form.toWatch()

        assertEquals(1, watch.log.size)
        assertEquals(1, watch.timing.size)
    }

    // --- the round trip ------------------------------------------------------

    @Test
    fun `opening a watch and saving it unchanged produces the same watch`() {
        // The property the dirty check rests on. If this failed, opening any
        // watch would report unsaved changes before a key was pressed.
        listOf(fullyPopulatedWatch(), minimalWatch()).forEach { original ->
            val form = WatchFormState.from(original)

            assertEquals(form, WatchFormState.from(form.toWatch(original.worn)))
        }
    }

    @Test
    fun `a stored integer-valued double does not come back as dirty text`() {
        // 41.0 renders as "41". Rendering it as "41.0" would round-trip to the
        // same number but to a DIFFERENT form state, so every watch with a whole
        // diameter would open already dirty.
        val form = WatchFormState.from(minimalWatch().copy(case = fullyPopulatedWatch().case))

        assertEquals("41", form.diameterMm)
        assertEquals(WatchFormState.from(form.toWatch()), form)
    }

    @Test
    fun `editing preserves the wear history the form never shows`() {
        val worn = listOf(LocalDate.of(2026, 8, 1), LocalDate.of(2026, 8, 2))
        val original = minimalWatch().copy(worn = worn)

        val edited = WatchFormState.from(original).copy(nickname = "Beater").toWatch(original.worn)

        assertEquals(worn, edited.worn)
    }

    // --- the dirty check -----------------------------------------------------

    @Test
    fun `typing a character and deleting it is not an unsaved change`() {
        // The desktop's signal-based flag says it is, and prompts. A prompt that
        // fires when nothing changed is one people learn to dismiss without
        // reading, which is worse than not having it.
        val initial = WatchFormState.from(fullyPopulatedWatch())

        val typed = initial.copy(nickname = initial.nickname + "x")
        val undone = typed.copy(nickname = initial.nickname)

        assertTrue("a typed character is a change", typed != initial)
        assertEquals("deleting it is not", initial, undone)
    }

    @Test
    fun `text that will never parse still counts as an unsaved change`() {
        // Comparing built watches would call this equal — both produce a null
        // diameter — and let the owner walk away from something they typed.
        val initial = WatchFormState.from(minimalWatch())
        val typed = initial.copy(diameterMm = "forty")

        assertTrue(typed != initial)
        assertEquals(typed.toWatch(), initial.toWatch())
    }

    // --- water resistance ----------------------------------------------------

    @Test
    fun `water resistance converts to metres whatever unit was typed`() {
        fun metres(value: String, unit: String) = WatchFormState.empty()
            .copy(waterResistance = value, waterResistanceUnit = unit)
            .waterResistanceMetres()

        assertEquals(100, metres("100", WatchFormState.UNIT_METRES))
        assertEquals(100, metres("10", WatchFormState.UNIT_BAR))
        assertEquals(100, metres("10", WatchFormState.UNIT_ATM))
        assertEquals(2000, metres("200", WatchFormState.UNIT_BAR))
        assertNull(metres("", WatchFormState.UNIT_BAR))
        assertNull(metres("deep", WatchFormState.UNIT_METRES))
    }

    @Test
    fun `a watch reopened after a bar entry shows metres, not bar`() {
        // Metres are what is stored. Re-offering "bar" would invite a second
        // conversion of an already-converted figure — 10 bar saved, reopened as
        // "100 bar", saved again as 1000 m.
        val saved = WatchFormState.empty()
            .copy(brand = "Seiko", model = "SKX007", waterResistance = "20", waterResistanceUnit = "bar")
            .toWatch()

        val reopened = WatchFormState.from(saved)

        assertEquals(200, saved.case.waterResistanceM)
        assertEquals("200", reopened.waterResistance)
        assertEquals(WatchFormState.UNIT_METRES, reopened.waterResistanceUnit)
    }

    // --- straps --------------------------------------------------------------

    @Test
    fun `at most one strap is fitted, even if the state says otherwise`() {
        val form = WatchFormState.empty().copy(
            brand = "Seiko",
            model = "SKX007",
            straps = listOf(
                StrapFormState(material = "Steel", fitted = true),
                StrapFormState(material = "NATO", fitted = true),
            ),
        )

        val straps = form.toWatch().straps
        assertEquals(1, straps.fittedCount())
        assertEquals("Steel", straps.first { it.fitted }.material)
    }

    @Test
    fun `no strap fitted is a legal state`() {
        val form = WatchFormState.empty().copy(
            brand = "Seiko",
            model = "SKX007",
            straps = listOf(StrapFormState(material = "NATO")),
        )

        assertEquals(0, form.toWatch().straps.fittedCount())
        assertEquals(1, form.toWatch().straps.size)
    }

    @Test
    fun `a strap's own width survives a round trip and so does its absence`() {
        val original = minimalWatch().copy(
            straps = listOf(Strap(material = "NATO", widthMm = 20), Strap(material = "Leather")),
        )

        val rebuilt = WatchFormState.from(original).toWatch()

        assertEquals(listOf(20, null), rebuilt.straps.map { it.widthMm })
    }

    // --- currency ------------------------------------------------------------

    @Test
    fun `a new watch defaults to TRY and an existing one is never given it`() {
        // SPEC.md §4 makes TRY the FORM's default for a new entry. A watch whose
        // file names no currency has not said TRY, and adding one on open would
        // make an edit to some unrelated field invent a claim about what was
        // paid.
        assertEquals(WatchFormState.DEFAULT_CURRENCY, WatchFormState.empty().currency)
        assertEquals("", WatchFormState.from(minimalWatch()).currency)
        assertNull(WatchFormState.from(minimalWatch()).toWatch().acquisition.currency)
    }

    // --- enum* free text -----------------------------------------------------

    @Test
    fun `a value the schema never suggested is stored exactly as typed`() {
        // "The owner will buy something you did not anticipate" — SPEC.md §4.
        val form = WatchFormState.empty().copy(
            brand = "Vostok",
            model = "Amphibia",
            kind = "Automatic (Vostok 2416b)",
            caseMaterial = "Chromed brass",
            style = "Skin diver",
        )
        val watch = form.toWatch()

        assertEquals("Automatic (Vostok 2416b)", watch.movement.kind)
        assertEquals("Chromed brass", watch.case.material)
        assertEquals("Skin diver", watch.style)
        assertEquals(form, WatchFormState.from(watch))
    }

    @Test
    fun `an unrecognised movement kind does not silently become quartz`() {
        assertFalse(WatchFormState.empty().copy(kind = "Automatic").usesBattery)
        assertFalse(WatchFormState.empty().copy(kind = "Mecha-quartz").usesBattery)
        assertTrue(WatchFormState.empty().copy(kind = "Quartz").usesBattery)
        assertTrue(WatchFormState.empty().copy(kind = " solar ").usesBattery)
    }
}
