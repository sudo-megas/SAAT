package io.github.sudomegas.saat

import io.github.sudomegas.saat.config.AppConfig
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

/**
 * Guards SPEC-ANDROID hard rule 7: the app never reads the system locale, and
 * its UI language defaults to English until the owner says otherwise.
 *
 * Every piece of machinery this rule needs was put in place in AM1 and all of
 * it is correct — but until now nothing held it there, and that is the whole
 * reason this file exists. The rule is enforced by a conspiracy of four things
 * that look unrelated to anyone reading them one at a time:
 *
 *  1. `AppConfig.DEFAULT_LANGUAGE` is English.
 *  2. `MainActivity` extends `AppCompatActivity`.
 *  3. `Theme.SAAT` descends from `Theme.AppCompat`.
 *  4. `SaatApplication.onCreate` calls `setApplicationLocales` before the first
 *     composition.
 *
 * Break any one and the app quietly becomes a system-locale follower: Android
 * resource resolution picks up the device language the moment `values-tr/`
 * exists. Nothing fails, nothing logs, and a Turkish phone simply starts
 * showing Turkish. The catch is the timing — `values-tr/` does not exist until
 * AM11, so a regression introduced at any point between here and there stays
 * invisible right up to the public-release milestone, which is the one with no
 * slack behind it. These assertions are cheap; discovering this in AM11 is not.
 *
 * Deliberately plain JVM tests. The theme parent is read by parsing the XML off
 * disk (the pattern PaletteXmlParityTest established) and the call sites are
 * read out of the sources (the pattern StringsConventionTest established), so
 * this needs neither Robolectric nor an instrumented device. A source scan
 * cannot prove the call actually runs — but it does prove nobody deleted it,
 * which is the failure being guarded against.
 */
class LocalePolicyTest {

    private fun source(path: String): String {
        val file = File(path)
        check(file.exists()) { "missing $path (working dir: ${File(".").absolutePath})" }
        return file.readText()
    }

    /** The `parent` of the named style in a themes.xml, or null if absent. */
    private fun themeParent(path: String, style: String): String? {
        val file = File(path)
        check(file.exists()) { "missing $path (working dir: ${File(".").absolutePath})" }

        val doc = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(file)
        val nodes = doc.getElementsByTagName("style")
        return (0 until nodes.length)
            .map { nodes.item(it) }
            .firstOrNull { it.attributes.getNamedItem("name")?.nodeValue == style }
            ?.attributes?.getNamedItem("parent")?.nodeValue
    }

    @Test
    fun `the UI language defaults to English`() {
        assertEquals(
            "hard rule 7: the default UI language is English, not whatever the device is set to",
            "en",
            AppConfig.DEFAULT_LANGUAGE,
        )
    }

    @Test
    fun `MainActivity is an AppCompatActivity`() {
        // AppCompatDelegate.setApplicationLocales is the only per-app locale API
        // that spans the whole minSdk 26 range, and it requires this base class.
        // The framework's LocaleManager is API 33+ and leaves 26-32 unserved.
        val text = source("src/main/kotlin/io/github/sudomegas/saat/MainActivity.kt")
        assertTrue(
            "MainActivity must extend AppCompatActivity or setApplicationLocales stops working below API 33",
            Regex("""class\s+MainActivity\s*:\s*AppCompatActivity\s*\(""").containsMatchIn(text),
        )
    }

    @Test
    fun `the XML theme descends from Theme_AppCompat`() {
        listOf(
            "src/main/res/values/themes.xml",
            "src/main/res/values-night/themes.xml",
        ).forEach { path ->
            val parent = themeParent(path, "Theme.SAAT")
            assertTrue(
                "$path: Theme.SAAT must descend from Theme.AppCompat for the AppCompat " +
                    "locale and night-mode machinery to apply, but its parent is $parent",
                parent != null && parent.startsWith("Theme.AppCompat"),
            )
        }
    }

    @Test
    fun `the application asserts a locale on every process start`() {
        val text = source("src/main/kotlin/io/github/sudomegas/saat/SaatApplication.kt")

        assertTrue(
            "SaatApplication must call AppCompatDelegate.setApplicationLocales — the English " +
                "default is an assertion, not something Android does by leaving it alone",
            text.contains("AppCompatDelegate.setApplicationLocales"),
        )
        assertTrue(
            "applyLanguage must be reached from onCreate, before the first composition",
            Regex("""fun\s+onCreate\(\)[\s\S]*?applyLanguage\(""").containsMatchIn(text),
        )
    }

    /**
     * The half of hard rule 7 that the assertions above could not see, and that
     * consequently shipped broken all the way to the release candidate.
     *
     * `AppCompatDelegate.setApplicationLocales` looks like it asserts the
     * language from `Application.onCreate`, and on API 26-32 it does. On 33+ it
     * locates the framework's LocaleManager by walking its live AppCompat
     * delegates; during `onCreate` there are none, so it returns having done
     * nothing at all, and the app follows the system locale for the rest of the
     * process. Nothing throws and nothing is logged.
     *
     * Every test in this file passed while that was true — they read the
     * sources, and the sources said `setApplicationLocales`. Verified on a
     * Turkish HONOR ELP-NX9 (Android 16, API 36): before the fix `cmd locale
     * get-app-locales` reported `[]` and the UI was Turkish with `config.toml`
     * saying `en`; after it, `[en]` and English.
     *
     * A source scan still cannot prove the branch RUNS — only a device can, and
     * androidcheck.md item 12 is where that is recorded. What it can prove is
     * that nobody deletes the branch and quietly restores the silent no-op,
     * which is exactly how this got here.
     */
    @Test
    fun `the locale is asserted through the framework on API 33 and above`() {
        val text = source("src/main/kotlin/io/github/sudomegas/saat/SaatApplication.kt")

        val body = Regex("""fun\s+applyLanguage\([\s\S]*?\n    \}""")
            .find(text)?.value
            ?: error("applyLanguage not found in SaatApplication.kt")

        assertTrue(
            "applyLanguage must branch on the SDK level: AppCompatDelegate alone is a " +
                "silent no-op from Application.onCreate on API 33+",
            body.contains("Build.VERSION.SDK_INT") &&
                body.contains("Build.VERSION_CODES.TIRAMISU"),
        )
        assertTrue(
            "the API 33+ branch must set applicationLocales on the framework's LocaleManager, " +
                "which is the only mechanism that works before any Activity exists",
            body.contains("LocaleManager") && body.contains("applicationLocales"),
        )
        assertTrue(
            "the API 26-32 branch must keep AppCompatDelegate.setApplicationLocales — the " +
                "framework's LocaleManager does not exist there",
            body.contains("AppCompatDelegate.setApplicationLocales"),
        )
    }

    @Test
    fun `no source file reads the system locale`() {
        // The point of the rule. Anything here would hand language selection
        // back to the device.
        //
        // `LocaleManager` used to be on this list as a bare word, which was too
        // blunt to be right: the class is BOTH the way to read the device's
        // languages and the only supported way to assert the app's own on API
        // 33+. Banning the name outright banned the fix along with the defect,
        // and the defect is the one that actually shipped — see
        // `SaatApplication.applyLanguage`. What the rule always meant is the
        // reading half, so that is what is named here. `applicationLocales` is
        // this app's own setting and is deliberately not listed.
        val forbidden = listOf(
            "Locale.getDefault(",
            "LocaleList.getDefault(",
            "LocaleListCompat.getDefault(",
            "Resources.getSystem(",
            "getConfiguration().locale",
            "configuration.locales",
            "getSystemLocales",
            ".systemLocales",
        )

        val offenders = SourceScan.offenders("src/main/kotlin") { line ->
            forbidden.any { line.contains(it) }
        }

        assertTrue(
            "hard rule 7: the app never reads the system locale, but found:\n" +
                offenders.joinToString("\n"),
            offenders.isEmpty(),
        )
    }
}
