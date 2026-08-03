package io.github.sudomegas.saat.ui.detail

import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.storage.Case
import io.github.sudomegas.saat.storage.Dial
import io.github.sudomegas.saat.storage.LogEntry
import io.github.sudomegas.saat.storage.Movement
import io.github.sudomegas.saat.storage.Strap
import io.github.sudomegas.saat.storage.TimingEntry
import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.WatchRecord
import io.github.sudomegas.saat.storage.minimalWatch
import io.github.sudomegas.saat.ui.form.BEZELS
import io.github.sudomegas.saat.ui.form.GROUPS
import io.github.sudomegas.saat.ui.form.INDICES
import io.github.sudomegas.saat.ui.form.STYLES
import io.github.sudomegas.saat.ui.form.labelFor
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.io.File

/**
 * Enum values carry their translation — AM11a, hard rule 7's UI half.
 *
 * The stored value and the shown label are two different things, and this is
 * where that stays true. Every assertion here is about a value that is written
 * to `watch.toml` in English while the interface reads it in whatever language
 * the owner picked.
 */
class EnumDisplayTest {

    private fun page(watch: Watch) = detailPage(
        WatchRecord("test", File("/watches/test"), watch = watch, loaded = watch),
        File("/media/test"),
    )!!

    private fun value(watch: Watch, titleRes: Int, labelRes: Int) = page(watch)
        .specGroups.first { it.titleRes == titleRes }
        .rows.first { it.labelRes == labelRes }.value

    /**
     * THE RULE IN ONE ASSERTION. `Automatic` is what the file says and what the
     * desktop reads; the label is what a Turkish build puts on screen. Both are
     * carried, and the value is never replaced.
     */
    @Test
    fun `a schema value keeps its English and gains a label`() {
        val watch = minimalWatch().copy(movement = Movement(kind = "Automatic"))

        val kind = value(watch, R.string.screen_detail_group_movement, R.string.field_kind)

        assertEquals(SpecValue.EnumValue("Automatic", R.string.enum_kind_automatic), kind)
    }

    /**
     * Free text has no label and must not acquire one. SPEC.md §4: the lists are
     * suggestions, "the owner will buy something you did not anticipate", and
     * what they typed is their word rather than the app's vocabulary.
     */
    @Test
    fun `a value the schema never suggested has no label`() {
        val watch = minimalWatch().copy(movement = Movement(kind = "Spring Drive"))

        val kind = value(watch, R.string.screen_detail_group_movement, R.string.field_kind)

        assertEquals(SpecValue.EnumValue("Spring Drive", null), kind)
    }

    /**
     * THE REASON THE LOOKUP TAKES A LIST. The same English word is a different
     * thing in different fields, and a flat value-to-label map would pick
     * whichever it met first and produce the wrong Turkish for the other.
     */
    @Test
    fun `the same word in two fields resolves to two different labels`() {
        assertEquals(R.string.enum_group_other, labelFor("Other", GROUPS))
        assertEquals(R.string.enum_style_other, labelFor("Other", STYLES))
        assertEquals(R.string.enum_bezel_none, labelFor("None", BEZELS))
        assertEquals(R.string.enum_indices_none, labelFor("None", INDICES))
    }

    @Test
    fun `labelFor is null for absent and blank values`() {
        assertNull(labelFor(null, GROUPS))
        assertNull(labelFor("   ", GROUPS))
    }

    @Test
    fun `a list of complications translates each of its parts`() {
        val watch = minimalWatch().copy(dial = Dial(complications = listOf("Date", "GMT")))

        val complications =
            value(watch, R.string.screen_detail_group_dial, R.string.field_complications)

        assertEquals(
            SpecValue.Joined(
                listOf(
                    SpecValue.EnumValue("Date", R.string.enum_complication_date),
                    SpecValue.EnumValue("GMT", R.string.enum_complication_gmt),
                ),
            ),
            complications,
        )
    }

    @Test
    fun `strap material and clasp carry labels, the colour does not`() {
        val watch = minimalWatch().copy(
            case = Case(lugWidthMm = 20),
            straps = listOf(Strap(material = "Leather", colour = "Cognac", clasp = "Deployant")),
        )

        val strap = page(watch).straps.single()

        assertEquals(
            SpecValue.EnumValue("Leather", R.string.enum_strapmaterial_leather),
            strap.material,
        )
        assertEquals(SpecValue.EnumValue("Deployant", R.string.enum_clasp_deployant), strap.clasp)
        // A colour is the owner's own word — there is no schema list for it.
        assertEquals("Cognac", strap.colour)
    }

    @Test
    fun `a log kind and a timing position carry labels`() {
        val watch = minimalWatch().copy(
            log = listOf(LogEntry(kind = "Service", note = "Full service")),
            timing = listOf(TimingEntry(deviationSec = 2.0, position = "Dial Up")),
        )

        assertEquals(
            SpecValue.EnumValue("Service", R.string.enum_logkind_service),
            page(watch).log.single().kind,
        )
        assertEquals(
            SpecValue.EnumValue("Dial Up", R.string.enum_position_dial_up),
            page(watch).timing.single().position,
        )
    }

    /**
     * A brand called `Solar` is a BRAND, not a movement kind. Identity fields
     * that are not enum* stay Plain, so nothing translates the owner's own name
     * for a thing into a movement type.
     */
    @Test
    fun `a brand that happens to spell an enum value is left alone`() {
        val watch = minimalWatch().copy(brand = "Solar")

        assertEquals("Solar", page(watch).brand)
    }
}
