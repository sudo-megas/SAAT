package io.github.sudomegas.saat.ui.detail

import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.storage.Acquisition
import io.github.sudomegas.saat.storage.Case
import io.github.sudomegas.saat.storage.Dial
import io.github.sudomegas.saat.storage.LogEntry
import io.github.sudomegas.saat.storage.Maintenance
import io.github.sudomegas.saat.storage.Movement
import io.github.sudomegas.saat.storage.Strap
import io.github.sudomegas.saat.storage.TimingEntry
import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.WatchRecord
import io.github.sudomegas.saat.storage.fullyPopulatedWatch
import io.github.sudomegas.saat.storage.minimalWatch
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.time.LocalDate

/**
 * SPEC-ANDROID 5.6's rules about the detail page, as assertions.
 *
 * All of them are properties of [detailPage], which is why it is a pure
 * function: "an absent field renders as a muted em-dash inside a shown group, a
 * wholly empty group is hidden" is a statement about which groups exist and
 * which rows carry null, and checking it against a rendered `Column` would need
 * a device and would still be checking the wrong layer.
 */
class DetailPageTest {

    private val media = File("/media/test")

    private fun page(watch: Watch) =
        detailPage(WatchRecord("test", File("/watches/test"), watch = watch, loaded = watch), media)

    private fun groupTitles(watch: Watch) = page(watch)!!.specGroups.map { it.titleRes }

    private fun rows(watch: Watch, titleRes: Int) =
        page(watch)!!.specGroups.first { it.titleRes == titleRes }.rows

    private fun value(watch: Watch, titleRes: Int, labelRes: Int) =
        rows(watch, titleRes).first { it.labelRes == labelRes }.value

    // --- group visibility ---------------------------------------------------

    @Test
    fun `a watch with only brand and model shows no spec groups at all`() {
        // SPEC-ANDROID 5.6: "A watch with only brand and model shows a short
        // page, and that is correct." Short means empty here — every group is
        // wholly absent, so every group is hidden rather than rendered as a
        // column of dashes.
        val page = page(minimalWatch())!!

        assertEquals(emptyList<Int>(), page.specGroups.map { it.titleRes })
        assertEquals(emptyList<StrapCard>(), page.straps)
        assertEquals(emptyList<LogLine>(), page.log)
        assertEquals(emptyList<TimingLine>(), page.timing)
        assertNull(page.notes)
    }

    @Test
    fun `one filled field is enough to show its group, and only its group`() {
        val watch = minimalWatch().copy(dial = Dial(colour = "Black"))

        assertEquals(listOf(R.string.screen_detail_group_dial), groupTitles(watch))
    }

    @Test
    fun `an absent field inside a shown group is a null value, not a dropped row`() {
        // The em-dash is the composable's rendering of null. What matters here
        // is that the ROW SURVIVES: a group that hid its empty fields would
        // silently change shape from watch to watch, and the owner could not
        // tell "not recorded" from "not a field".
        val watch = minimalWatch().copy(dial = Dial(colour = "Black"))
        val dial = rows(watch, R.string.screen_detail_group_dial)

        assertEquals(5, dial.size)
        assertEquals(
            SpecValue.Plain("Black"),
            dial.first { it.labelRes == R.string.field_dial_colour }.value,
        )
        assertNull(dial.first { it.labelRes == R.string.field_lume }.value)
    }

    @Test
    fun `groups appear in the model's order`() {
        val titles = groupTitles(fullyPopulatedWatch())

        assertEquals(
            listOf(
                R.string.screen_detail_group_movement,
                R.string.screen_detail_group_case,
                R.string.screen_detail_group_dial,
                R.string.screen_detail_group_acquisition,
                R.string.screen_detail_group_maintenance,
            ),
            titles,
        )
    }

    // --- the movement's one conditional row ---------------------------------

    @Test
    fun `a mechanical movement shows power reserve and not battery life`() {
        val watch = minimalWatch().copy(
            movement = Movement(kind = "Automatic", powerReserveHours = 38.0),
        )
        val labels = rows(watch, R.string.screen_detail_group_movement).map { it.labelRes }

        assertTrue(R.string.field_power_reserve in labels)
        assertTrue(R.string.field_battery_life !in labels)
    }

    @Test
    fun `quartz and solar swap power reserve for battery life`() {
        listOf("Quartz", "Solar", "  quartz  ", "SOLAR").forEach { kind ->
            val watch = minimalWatch().copy(movement = Movement(kind = kind))
            val labels = rows(watch, R.string.screen_detail_group_movement).map { it.labelRes }

            assertTrue("$kind should show battery life", R.string.field_battery_life in labels)
            assertTrue("$kind should hide power reserve", R.string.field_power_reserve !in labels)
        }
    }

    @Test
    fun `a value the kind did not predict is still shown`() {
        // Mecha-quartz has both a battery and a mainspring, and `kind` is free
        // text besides. Hiding a figure the owner typed in because the enum did
        // not expect it would be the display layer overruling the file.
        val watch = minimalWatch().copy(
            movement = Movement(kind = "Quartz", powerReserveHours = 45.0),
        )
        val labels = rows(watch, R.string.screen_detail_group_movement).map { it.labelRes }

        assertTrue(R.string.field_battery_life in labels)
        assertTrue(R.string.field_power_reserve in labels)
    }

    // --- values -------------------------------------------------------------

    @Test
    fun `water resistance carries the bar equivalent, rounded the desktop's way`() {
        // Python's round() is half-to-even, so 5 m is 0 bar and 15 m is 2 bar.
        // Half-up would answer 1 and 2. Neither figure matters much on its own;
        // the two apps agreeing about it does.
        mapOf(100 to "10", 200 to "20", 5 to "0", 15 to "2", 30 to "3").forEach { (m, bar) ->
            val watch = minimalWatch().copy(case = Case(waterResistanceM = m))

            assertEquals(
                SpecValue.Resource(
                    R.string.field_value_water_resistance,
                    listOf(m.toString(), bar),
                ),
                value(watch, R.string.screen_detail_group_case, R.string.field_water_resistance),
            )
        }
    }

    @Test
    fun `frequency carries hertz beside the beat rate`() {
        val watch = minimalWatch().copy(movement = Movement(bph = 28800))

        assertEquals(
            SpecValue.Resource(R.string.field_value_frequency, listOf("28800", "4")),
            value(watch, R.string.screen_detail_group_movement, R.string.field_frequency),
        )
    }

    @Test
    fun `accuracy keeps the half it knows when the other is missing`() {
        val watch = minimalWatch().copy(movement = Movement(accuracyMin = -5.0))

        assertEquals(
            SpecValue.Resource(R.string.field_value_accuracy, listOf("-5", "?", "sec/day")),
            value(watch, R.string.screen_detail_group_movement, R.string.field_accuracy),
        )
    }

    @Test
    fun `accuracy is absent only when neither bound is recorded`() {
        val watch = minimalWatch().copy(movement = Movement(kind = "Automatic"))

        assertNull(
            value(watch, R.string.screen_detail_group_movement, R.string.field_accuracy),
        )
    }

    @Test
    fun `a price with no currency prints the figure alone`() {
        // Defaulting to TRY here would be the display layer inventing a fact
        // about what somebody paid. SPEC.md §4 makes TRY the FORM's default.
        val watch = minimalWatch().copy(acquisition = Acquisition(price = 1234.5))

        assertEquals(
            SpecValue.Plain("1,234.50"),
            value(watch, R.string.screen_detail_group_acquisition, R.string.field_price),
        )
    }

    @Test
    fun `a price with a currency names it`() {
        val watch = minimalWatch().copy(
            acquisition = Acquisition(price = 850.0, currency = "TRY"),
        )

        assertEquals(
            SpecValue.Resource(R.string.field_value_price, listOf("850.00", "TRY")),
            value(watch, R.string.screen_detail_group_acquisition, R.string.field_price),
        )
    }

    @Test
    fun `dates render DD_MM_YYYY`() {
        val watch = minimalWatch().copy(
            acquisition = Acquisition(date = LocalDate.of(2024, 3, 7)),
        )

        assertEquals(
            SpecValue.Plain("07.03.2024"),
            value(watch, R.string.screen_detail_group_acquisition, R.string.field_acquired),
        )
    }

    @Test
    fun `booleans render as Yes or No, and null stays absent`() {
        val yes = minimalWatch().copy(movement = Movement(hacking = true))
        val no = minimalWatch().copy(movement = Movement(hacking = false))
        val unknown = minimalWatch().copy(movement = Movement(jewels = 21))

        assertEquals(
            SpecValue.Resource(R.string.field_value_yes),
            value(yes, R.string.screen_detail_group_movement, R.string.field_hacking),
        )
        assertEquals(
            SpecValue.Resource(R.string.field_value_no),
            value(no, R.string.screen_detail_group_movement, R.string.field_hacking),
        )
        assertNull(value(unknown, R.string.screen_detail_group_movement, R.string.field_hacking))
    }

    @Test
    fun `a blank string is absence, not a value`() {
        // A hand-edited file — and the desktop's own writer — can carry
        // `nickname = ""`. An empty string is the owner not having filled the
        // field in, and rendering it as a value would show a group with a blank
        // where an em-dash belongs.
        val watch = minimalWatch().copy(
            nickname = "  ",
            notes = "\n ",
            dial = Dial(colour = "", lume = "Lumibrite"),
        )
        val page = page(watch)!!

        assertNull(page.nickname)
        assertNull(page.notes)
        assertNull(value(watch, R.string.screen_detail_group_dial, R.string.field_dial_colour))
    }

    // --- the list-shaped sections -------------------------------------------

    @Test
    fun `the log reads newest first, with undated entries last`() {
        val watch = minimalWatch().copy(
            log = listOf(
                LogEntry(LocalDate.of(2023, 1, 1), "Note", "oldest"),
                LogEntry(null, "Note", "undated"),
                LogEntry(LocalDate.of(2025, 6, 1), LogEntry.KIND_SERVICE, "newest"),
            ),
        )

        assertEquals(
            listOf("newest", "oldest", "undated"),
            page(watch)!!.log.map { it.note },
        )
    }

    @Test
    fun `timing reads newest first and keeps the sign of each reading`() {
        val watch = minimalWatch().copy(
            timing = listOf(
                TimingEntry(LocalDate.of(2025, 1, 1), -2.5, "Dial Up"),
                TimingEntry(LocalDate.of(2025, 2, 1), 3.0, "Crown Down"),
            ),
        )
        val timing = page(watch)!!.timing

        assertEquals(listOf("01.02.2025", "01.01.2025"), timing.map { it.date })
        assertEquals(listOf("+3", "-2.5"), timing.map { it.deviation })
    }

    @Test
    fun `a strap with no width of its own borrows the watch's lug width`() {
        val watch = minimalWatch().copy(
            case = Case(lugWidthMm = 20),
            straps = listOf(
                Strap(material = "Leather", fitted = true),
                Strap(material = "NATO", widthMm = 18),
            ),
        )

        assertEquals(listOf(20, 18), page(watch)!!.straps.map { it.widthMm })
        assertEquals(listOf(true, false), page(watch)!!.straps.map { it.fitted })
    }

    // --- photographs --------------------------------------------------------

    @Test
    fun `images resolve into the media tree and keep the owner's order`() {
        val watch = minimalWatch().copy(images = listOf("front.jpg", "back.jpg"))

        assertEquals(
            listOf(File(media, "front.jpg"), File(media, "back.jpg")),
            page(watch)!!.images,
        )
    }

    @Test
    fun `a path in the images key is reduced to its filename`() {
        // SPEC-ANDROID 3 depends on `images` holding BARE FILENAMES, which is
        // what lets the photographs live in a separate media/ tree and still
        // re-root into watches/<slug>/images/ inside the exported ZIP. A
        // hand-edited file can still write a path, and `../` in one would
        // otherwise reach another watch's folder.
        val watch = minimalWatch().copy(images = listOf("images/front.jpg", "../other/back.jpg"))

        assertEquals(
            listOf(File(media, "front.jpg"), File(media, "back.jpg")),
            page(watch)!!.images,
        )
    }

    @Test
    fun `a strap photo resolves the same way`() {
        val watch = minimalWatch().copy(straps = listOf(Strap(image = "strap/tan.jpg")))

        assertEquals(File(media, "tan.jpg"), page(watch)!!.straps.single().image)
    }

    // --- the header ---------------------------------------------------------

    @Test
    fun `status is always in the meta line and rating renders as stars`() {
        val watch = minimalWatch().copy(rating = 4, style = "Diver")

        // Style and status are EnumValue, not Plain: both are schema values with
        // translations, and the header used to be the one place on the detail
        // page that printed them in English regardless of the interface
        // language. The stars stay Plain — they are punctuation, not vocabulary.
        assertEquals(
            listOf(
                SpecValue.EnumValue("Diver", R.string.enum_style_diver),
                SpecValue.EnumValue(Watch.STATUS_OWNED, R.string.enum_status_owned),
                SpecValue.Plain("★★★★☆"),
            ),
            page(watch)!!.meta,
        )
    }

    @Test
    fun `a style the schema does not know keeps the owner's own spelling`() {
        // The other half of the same rule: a null label is what makes a word the
        // owner invented survive the trip to the screen unchanged.
        assertEquals(
            SpecValue.EnumValue("Skin diver", null),
            page(minimalWatch().copy(style = "Skin diver"))!!.meta.first(),
        )
    }

    @Test
    fun `a rating outside 0 to 5 is clamped rather than repeated negatively`() {
        // "★".repeat(-1) throws, and a hand-edited file can say rating = 9.
        assertEquals(
            SpecValue.Plain("★★★★★"),
            page(minimalWatch().copy(rating = 9))!!.meta.last(),
        )
        assertEquals(
            SpecValue.Plain("☆☆☆☆☆"),
            page(minimalWatch().copy(rating = -3))!!.meta.last(),
        )
    }

    @Test
    fun `the fully populated fixture fills every group and every list`() {
        // The parity fixture carries a distinctive value in every field, so this
        // is the one test that would notice a whole group quietly failing to
        // build — a null-safe chain returning empty rather than throwing.
        val page = page(fullyPopulatedWatch())!!

        assertEquals(5, page.specGroups.size)
        assertTrue(page.specGroups.all { group -> group.rows.any { it.value != null } })
        assertTrue(page.straps.isNotEmpty())
        assertTrue(page.log.isNotEmpty())
        assertTrue(page.timing.isNotEmpty())
        assertNotNull(page.notes)
        assertTrue(page.tags.isNotEmpty())
    }

    @Test
    fun `a record that did not load has no page`() {
        val record = WatchRecord("broken", File("/watches/broken"), loadError = "line 3: bad")

        assertNull(detailPage(record, media))
    }
}
