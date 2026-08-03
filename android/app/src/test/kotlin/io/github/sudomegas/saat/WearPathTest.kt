package io.github.sudomegas.saat

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * EXACTLY ONE IMPLEMENTATION OF THE ONE-WATCH-PER-DAY RULE, and this test says
 * where it lives — AM8's item 6, which asks for that to be verified rather than
 * asserted in a commit message.
 *
 * It lives in `WatchRepository.assignWorn`, and the reason it has to be one
 * place is that there are now FOUR ways to record a day: the detail page's
 * button, the calendar's picker, the widget and the launcher shortcut. A second
 * copy of "take the day off whoever else has it" would not fail any test — both
 * copies would work — it would simply drift, and the symptom would be a day
 * belonging to two watches in a file nobody looks at.
 *
 * A source scan rather than a behavioural test on purpose: the behaviour is
 * covered by WearLoggingTest, and what is being guarded here is that nobody adds
 * a second implementation. That is a property of the codebase, not of a run.
 */
class WearPathTest {

    private fun sources() = File("src/main/kotlin")
        .walkTopDown()
        .filter { it.extension == "kt" }

    @Test
    fun `only the repository strips a day from another watch`() {
        // `worn.filterNot` is the rule's signature move: taking a date OUT of
        // some other watch's list. Matched exactly rather than as "worn" near
        // "filterNot", which also hits MonthStats' `wornSlugs` and would make
        // this test cry wolf about honest code.
        val offenders = sources()
            .filterNot { it.name == "WatchRepository.kt" }
            .filter { file ->
                SourceScan.codeLines(file).any { (_, line) -> line.contains("worn.filterNot") }
            }
            .map { it.path }
            .toList()

        assertTrue(
            "one-watch-per-day belongs to WatchRepository.assignWorn and nowhere " +
                "else — there are four callers and a second copy would drift " +
                "rather than fail:\n" + offenders.joinToString("\n"),
            offenders.isEmpty(),
        )
    }

    @Test
    fun `the wear operations are declared exactly once`() {
        // Two declarations would compile, both would work, and they would drift.
        val declarations = sources()
            .flatMap { file ->
                SourceScan.codeLines(file)
                    .filter { (_, line) ->
                        line.contains("fun assignWorn") || line.contains("fun clearWorn")
                    }
                    .map { file.name }
            }
            .toList()

        assertEquals(listOf("WatchRepository.kt", "WatchRepository.kt"), declarations.sorted())
    }

    @Test
    fun `the four entry points exist and all of them are wired to it`() {
        // Named so that deleting one is a visible change rather than a silent
        // one. Each of these files calls assignWorn — directly, or through the
        // CalendarViewModel the widget's picker activity shares.
        val callers = mapOf(
            "the detail page's button" to "ui/DetailViewModel.kt",
            "the calendar and the widget's picker" to "ui/CalendarViewModel.kt",
        )

        callers.forEach { (what, path) ->
            val file = File("src/main/kotlin/io/github/sudomegas/saat/$path")
            assertTrue("missing $path ($what)", file.exists())
            assertTrue(
                "$what must record wear through WatchRepository.assignWorn",
                file.readText().contains("assignWorn"),
            )
        }

        // The widget's picker and the launcher shortcut both land on the same
        // activity, which drives CalendarViewModel — so they are the same path
        // rather than two more.
        val picker = File("src/main/kotlin/io/github/sudomegas/saat/widget/TodayPickerActivity.kt")
        assertTrue(picker.exists())
        assertTrue(
            "the widget and shortcut picker must record through CalendarViewModel",
            picker.readText().contains("assignToday"),
        )
    }

    @Test
    fun `both static shortcuts are declared`() {
        val shortcuts = File("src/main/res/xml/shortcuts.xml")
        assertTrue("missing src/main/res/xml/shortcuts.xml", shortcuts.exists())

        val text = shortcuts.readText()
        // Static rather than dynamic so they work on a cold start: the launcher
        // reads them from this file and no app code has to have run first.
        assertTrue("the wore-today shortcut is missing", text.contains("wore_today"))
        assertTrue("the add-watch shortcut is missing", text.contains("add_watch"))
        assertTrue(
            "\"Wore this today\" must open the picker, not the app shell",
            text.contains("TodayPickerActivity"),
        )
    }
}
