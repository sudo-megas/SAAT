package io.github.sudomegas.saat.buildlogic

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The demo-fixture guardian's own guardian.
 *
 * Like [ManifestPolicyScannerTest], these only run because
 * `buildSrc/build.gradle.kts` hangs the test task off `jar` with `finalizedBy` —
 * Gradle does not run buildSrc tests on its own.
 *
 * The cases below are the ways this check could go quietly wrong: matching too
 * little (and passing a release build that carries the fixture) or too much (and
 * failing one that does not).
 */
class DemoFixtureScannerTest {

    @Test
    fun `a class under the devtools package is a hit`() {
        assertTrue(
            DemoFixtureScanner.isDevtoolsClass(
                "io/github/sudomegas/saat/devtools/DemoWatches.class"
            )
        )
    }

    @Test
    fun `a Kotlin synthetic class under devtools is a hit too`() {
        // Suspend functions generate DemoWatches$generate$1 and friends. Missing
        // these would let most of the fixture through.
        assertTrue(
            DemoFixtureScanner.isDevtoolsClass(
                "io/github/sudomegas/saat/devtools/DemoWatches\$generate\$1.class"
            )
        )
    }

    @Test
    fun `windows path separators still match`() {
        assertTrue(
            DemoFixtureScanner.isDevtoolsClass(
                "io\\github\\sudomegas\\saat\\devtools\\DemoWatches.class"
            )
        )
    }

    @Test
    fun `an ordinary app class is not a hit`() {
        assertFalse(
            DemoFixtureScanner.isDevtoolsClass(
                "io/github/sudomegas/saat/storage/WatchStore.class"
            )
        )
    }

    @Test
    fun `the marker is found in class bytes`() {
        val bytes = ("some constant pool junk" + DemoFixtureScanner.MARKER + "more junk")
            .toByteArray(Charsets.UTF_8)
        assertTrue(DemoFixtureScanner.containsMarker(bytes))
    }

    @Test
    fun `the marker is found at the very end of the bytes`() {
        // Off-by-one in the search window would miss exactly this.
        assertTrue(
            DemoFixtureScanner.containsMarker(
                ("padding" + DemoFixtureScanner.MARKER).toByteArray(Charsets.UTF_8)
            )
        )
    }

    @Test
    fun `bytes without the marker are not a hit`() {
        assertFalse(
            DemoFixtureScanner.containsMarker("SAAT is a watch collection".toByteArray())
        )
    }

    @Test
    fun `bytes shorter than the marker are not a hit`() {
        assertFalse(DemoFixtureScanner.containsMarker("SAAT".toByteArray()))
        assertFalse(DemoFixtureScanner.containsMarker(ByteArray(0)))
    }

    @Test
    fun `demo string resources are found in an R txt`() {
        val symbols = """
            int string action_add_demo_watches 0x7f0e0001
            int string action_add_watch 0x7f0e0002
            int string settings_demo_watches_summary 0x7f0e0003
            int plurals screen_grid_notice_title 0x7f0f0001
        """.trimIndent()

        assertEquals(
            listOf("action_add_demo_watches", "settings_demo_watches_summary"),
            DemoFixtureScanner.demoResourceNames(symbols),
        )
    }

    @Test
    fun `an R txt with no demo resources yields nothing`() {
        val symbols = """
            int string action_add_watch 0x7f0e0002
            int string settings_theme 0x7f0e0004
        """.trimIndent()

        assertEquals(emptyList<String>(), DemoFixtureScanner.demoResourceNames(symbols))
    }

    @Test
    fun `a non-string resource that happens to say demo is ignored`() {
        // The rule is about the fixture's user-visible strings. A drawable or an
        // id named demo_something is somebody else's problem, and failing the
        // release build over it would teach people to weaken this check.
        val symbols = """
            int drawable demo_background 0x7f080001
            int id demo_container 0x7f090001
        """.trimIndent()

        assertEquals(emptyList<String>(), DemoFixtureScanner.demoResourceNames(symbols))
    }

    @Test
    fun `malformed R txt lines are skipped rather than crashing the build`() {
        val symbols = "\n   \nint\nint string action_add_demo_watches 0x1\n"
        assertEquals(
            listOf("action_add_demo_watches"),
            DemoFixtureScanner.demoResourceNames(symbols),
        )
    }
}
