package io.github.sudomegas.saat

import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * The structural rules AM3 introduced, which no behavioural test can reach.
 *
 * Two of hard rule 1's and hard rule 8's guarantees are properties of where code
 * and files live rather than of what they compute:
 *
 *  - the demo-watch generator must not be referenced from shared code, or the
 *    release variant would not compile — and "it compiles today" is not a rule,
 *    it is a coincidence waiting to be broken by one import;
 *  - image caches must land in `cacheDir`, never in `filesDir`, because
 *    `filesDir` is where `watches/` lives and hard rule 8 forbids derived files
 *    inside it.
 *
 * The release-build half of the demo-fixture claim is NOT tested here — it
 * cannot be, since AGP creates no release unit-test variant.
 * `verifyReleaseDemoFixturePolicy` asserts that from the build instead.
 */
class GridPolicyTest {

    @Test
    fun `shared code never names the debug-only devtools package`() {
        // src/main cannot see src/debug, so a stray import here breaks the
        // release build outright. Catching it as a rule gives a message that
        // explains itself, instead of an "unresolved reference" in a variant
        // nobody compiles locally.
        val offenders = SourceScan.offenders("src/main/kotlin") { line ->
            line.contains("devtools")
        }

        assertTrue(
            "the demo fixture is debug-only (hard rule 1) and src/main must not " +
                "reference it — call DeveloperSection, which has a release twin:\n" +
                offenders.joinToString("\n"),
            offenders.isEmpty(),
        )
    }

    @Test
    fun `both DeveloperSection twins exist`() {
        // If either disappears, one variant stops compiling — but only when
        // somebody happens to build that variant. Assert both halves are present.
        listOf(
            "src/debug/kotlin/io/github/sudomegas/saat/ui/screens/DeveloperSection.kt",
            "src/release/kotlin/io/github/sudomegas/saat/ui/screens/DeveloperSection.kt",
        ).forEach { path ->
            assertTrue(
                "missing $path — SettingsScreen calls DeveloperSection in every variant",
                File(path).exists(),
            )
        }
    }

    @Test
    fun `both DeveloperSection twins declare the same function`() {
        val signature = Regex("""fun\s+DeveloperSection\s*\(\s*repository:\s*WatchRepository\s*\)""")
        listOf(
            "src/debug/kotlin/io/github/sudomegas/saat/ui/screens/DeveloperSection.kt",
            "src/release/kotlin/io/github/sudomegas/saat/ui/screens/DeveloperSection.kt",
        ).forEach { path ->
            assertTrue(
                "$path must declare DeveloperSection(repository: WatchRepository) — the two " +
                    "twins are only interchangeable while their signatures match",
                signature.containsMatchIn(File(path).readText()),
            )
        }
    }

    @Test
    fun `the image cache is configured under cacheDir and never filesDir`() {
        val loader = File("src/main/kotlin/io/github/sudomegas/saat/SaatApplication.kt")
        val code = SourceScan.codeLines(loader).joinToString("\n") { it.value }

        assertTrue(
            "the Coil disk cache must name cacheDir — hard rule 8 keeps derived " +
                "files out of the data tree, and inheriting a library default is " +
                "not the same as deciding it",
            code.contains("DiskCache") && code.contains("cacheDir"),
        )
        assertTrue(
            "the image cache must not be rooted in filesDir: that is where " +
                "watches/ lives, and hard rule 8 forbids derived files inside it",
            !Regex("""DiskCache[\s\S]{0,400}?filesDir""").containsMatchIn(code),
        )
    }
}
