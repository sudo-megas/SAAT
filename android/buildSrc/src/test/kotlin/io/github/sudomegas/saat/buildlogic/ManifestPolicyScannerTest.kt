package io.github.sudomegas.saat.buildlogic

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The guardian's own guardian.
 *
 * This is not a one-off demonstration that the check works — it is a standing
 * test, and it lives in buildSrc precisely because Gradle runs `buildSrc:test`
 * before evaluating the root project. Every single Gradle invocation therefore
 * re-proves that the zero-permission check still detects a permission, with no
 * CI wiring anyone could remove.
 *
 * The two false-negative and false-positive cases below are the ones that
 * matter; both are real, not hypothetical.
 */
class ManifestPolicyScannerTest {

    // The declaration is prepended OUTSIDE trimIndent deliberately. When `body`
    // is a multi-line string, its lines sit at column 0 once interpolated, so
    // trimIndent computes a common indent of 0 and leaves every other line
    // indented — putting whitespace before `<?xml?>`, which is a parse error.
    // Whitespace before the root ELEMENT is legal; before the declaration it is
    // not.
    private fun manifest(
        applicationAttrs: String = DEFAULT_APP_ATTRS,
        body: String = "",
        appBody: String = "",
    ) = XML_DECL + """
        <manifest xmlns:android="http://schemas.android.com/apk/res/android"
            package="io.github.sudomegas.saat">
            $body
            <application $applicationAttrs>
                <activity android:name=".MainActivity" android:exported="true"/>
                $appBody
            </application>
        </manifest>
        """.trimIndent()

    @Test
    fun `a clean manifest passes`() {
        assertEquals(emptyList<Violation>(), ManifestPolicyScanner.scan(manifest()))
    }

    @Test
    fun `a plain uses-permission fails`() {
        val violations = ManifestPolicyScanner.scan(
            manifest(body = """<uses-permission android:name="android.permission.INTERNET"/>""")
        )
        assertEquals(1, violations.size)
        assertTrue(violations.single().detail.contains("android.permission.INTERNET"))
    }

    /**
     * The false negative. `uses-permission-sdk-23` is a genuine permission
     * request, merely gated to API 23+, and a check that only looks for
     * `uses-permission` sails straight past it.
     */
    @Test
    fun `uses-permission-sdk-23 fails too`() {
        val violations = ManifestPolicyScanner.scan(
            manifest(body = """<uses-permission-sdk-23 android:name="android.permission.CAMERA"/>""")
        )
        assertEquals(1, violations.size)
        assertTrue(violations.single().detail.contains("android.permission.CAMERA"))
    }

    @Test
    fun `declaring a permission fails, not just requesting one`() {
        val violations = ManifestPolicyScanner.scan(
            manifest(body = """<permission android:name="io.github.sudomegas.saat.SOMETHING"/>""")
        )
        assertEquals(1, violations.size)
    }

    /**
     * The false positive, and the more dangerous of the two. AM5 adds a
     * FileProvider with android:grantUriPermissions="true" for the camera
     * capture target. A guardian that greps the manifest text for "permission"
     * goes red then — for entirely the wrong reason — and the natural fix would
     * be to weaken the guardian.
     */
    @Test
    fun `grantUriPermissions on a provider passes`() {
        val violations = ManifestPolicyScanner.scan(
            manifest(
                appBody = """<provider
                    android:name="androidx.core.content.FileProvider"
                    android:authorities="io.github.sudomegas.saat.fileprovider"
                    android:exported="false"
                    android:grantUriPermissions="true"/>"""
            )
        )
        assertEquals(
            "grantUriPermissions is not a permission — see AM5",
            emptyList<Violation>(),
            violations,
        )
    }

    /**
     * `<queries>` declares package visibility, not permission. AM5 may need it
     * for the camera intent; it must not trip this check.
     */
    @Test
    fun `a queries block passes`() {
        val violations = ManifestPolicyScanner.scan(
            manifest(
                body = """<queries><intent>""" +
                    """<action android:name="android.media.action.IMAGE_CAPTURE"/>""" +
                    """</intent></queries>"""
            )
        )
        assertEquals(emptyList<Violation>(), violations)
    }

    @Test
    fun `a non-default namespace prefix still fails`() {
        val xml = """
            <?xml version="1.0" encoding="utf-8"?>
            <a:manifest xmlns:a="http://schemas.android.com/apk/res/android"
                package="io.github.sudomegas.saat">
                <a:uses-permission a:name="android.permission.INTERNET"/>
                <a:application a:allowBackup="true"
                    a:fullBackupContent="@xml/backup_rules"
                    a:dataExtractionRules="@xml/data_extraction_rules"/>
            </a:manifest>
        """.trimIndent()
        assertTrue(
            "matching must be on local name, not the literal string 'android:'",
            ManifestPolicyScanner.scan(xml).any { it.detail.contains("uses-permission") },
        )
    }

    @Test
    fun `suppressing rotation with configChanges fails`() {
        val xml = """
            <?xml version="1.0" encoding="utf-8"?>
            <manifest xmlns:android="http://schemas.android.com/apk/res/android">
                <application $DEFAULT_APP_ATTRS>
                    <activity android:name=".MainActivity"
                        android:configChanges="orientation|screenSize"/>
                </application>
            </manifest>
        """.trimIndent()
        assertTrue(
            ManifestPolicyScanner.scan(xml).any { it.detail.contains("configChanges") },
        )
    }

    @Test
    fun `losing a backup attribute fails`() {
        val violations = ManifestPolicyScanner.scan(
            manifest(applicationAttrs = """android:allowBackup="true"""")
        )
        assertEquals(2, violations.size)
        assertTrue(violations.any { it.detail.contains("fullBackupContent") })
        assertTrue(violations.any { it.detail.contains("dataExtractionRules") })
    }

    @Test
    fun `a required uses-feature fails`() {
        val violations = ManifestPolicyScanner.scan(
            manifest(body = """<uses-feature android:name="android.hardware.camera"/>""")
        )
        assertTrue(violations.any { it.detail.contains("uses-feature") })
    }

    private companion object {
        const val XML_DECL = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"

        const val DEFAULT_APP_ATTRS =
            """android:allowBackup="true" """ +
                """android:fullBackupContent="@xml/backup_rules" """ +
                """android:dataExtractionRules="@xml/data_extraction_rules""""
    }
}
