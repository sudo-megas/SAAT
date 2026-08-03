package io.github.sudomegas.saat

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * `versionName` and the newest changelog heading agree — AM11c.
 *
 * A mirror of the desktop's `tests/test_version.py`, which exists because of
 * exactly what happened after its milestone 12: a release that shipped real
 * behaviour changes and forgot to bump the version. The invariant is enforced
 * here rather than remembered by whoever writes the release commit, the same as
 * every other invariant in this project.
 *
 * COMPARED AS STRINGS, NEVER PARSED AS SEMVER, and that is not a shortcut — it
 * is the only thing that works. This project's sequence is
 * `0.8 → 0.9 → 0.10 → 1.0`, where `0.10` is the tenth milestone and not the
 * first: under semantic versioning `0.10 > 0.9`, but under this project's
 * scheme and under a plain string comparison `0.10 < 0.8`. Any guard that
 * sorted these would be wrong about the two most recent releases, so nothing
 * here sorts anything. It asserts equality and nothing more.
 */
class VersionGuardTest {

    private val buildScript = File("build.gradle.kts").readText()
    private val changelog = File("../CHANGELOG-ANDROID.md").readText()

    /** Two- and three-part versions are both valid, as on the desktop. */
    private val headings = Regex("""^## \[(\d+\.\d+(?:\.\d+)?)]""", RegexOption.MULTILINE)
        .findAll(changelog)
        .map { it.groupValues[1] }
        .toList()

    private fun buildValue(name: String): String? =
        Regex("""$name\s*=\s*"?([^"\s]+)"?""").find(buildScript)?.groupValues?.get(1)

    @Test
    fun `versionName matches the newest changelog heading`() {
        val versionName = buildValue("versionName")
        assertNotNull("no versionName in build.gradle.kts", versionName)
        assertTrue("no '## [x.y]' heading in CHANGELOG-ANDROID.md", headings.isNotEmpty())

        assertEquals(
            "versionName and the newest CHANGELOG-ANDROID.md heading disagree. " +
                "Bump one or write the other — do not ship a version with no entry.",
            headings.first(),
            versionName,
        )
    }

    /**
     * `versionCode` is what Android compares to decide whether an APK is an
     * update, and it is an integer — a `versionName` of "1.0" tells the platform
     * nothing at all.
     */
    @Test
    fun `versionCode is a positive integer`() {
        val versionCode = buildValue("versionCode")?.toIntOrNull()

        assertNotNull("versionCode is missing or is not an integer", versionCode)
        assertTrue("versionCode must be positive, was $versionCode", versionCode!! > 0)
    }

    /**
     * A duplicated heading is the shape a hand-edited changelog goes wrong in:
     * an entry copied to start the next one and its number left alone. It would
     * make the guard above pass while the file said two different things about
     * one version.
     */
    @Test
    fun `no version appears twice in the changelog`() {
        val duplicated = headings.groupingBy { it }.eachCount().filterValues { it > 1 }.keys

        assertTrue("these versions have more than one entry: $duplicated", duplicated.isEmpty())
    }

    /**
     * The release workflow triggers on `android-v*`, so the tag for this build
     * is `android-v` plus the version name. Asserted here so a version that
     * cannot be tagged — a space, a stray quote — fails before the tag is spent
     * rather than after.
     */
    @Test
    fun `the version name is usable as a git tag`() {
        val versionName = buildValue("versionName")!!

        assertTrue(
            "versionName '$versionName' would not make a clean android-v* tag",
            Regex("""^\d+\.\d+(\.\d+)?$""").matches(versionName),
        )
    }
}
