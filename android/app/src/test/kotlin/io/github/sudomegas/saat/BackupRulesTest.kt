package io.github.sudomegas.saat

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory
import org.w3c.dom.Element

/**
 * The Auto Backup rules, as a test — SPEC-ANDROID 3.1, AM10c.
 *
 * The rules themselves were written in AM1 and have been right ever since. What
 * they have not had is anything stopping them from quietly going wrong, and
 * they are exactly the sort of file that does: an `<exclude>` added in good
 * faith, a `media` typed into the wrong element, and the failure is invisible
 * until an owner restores a phone and finds either their photographs missing
 * from a quota they never had, or the quota blown and the RECORDS missing too.
 * Nothing at runtime reads these files, so nothing at runtime can notice.
 *
 * THE RULE IS INCLUDE-ONLY, AND THAT IS WHAT MAKES IT SAFE. Presence of any
 * `<include>` makes everything unlisted excluded, so `media/`, `backups/` and
 * `cacheDir` are left out by omission rather than by a rule somebody has to
 * remember to update as the schema grows. There are no wildcards to get wrong —
 * the format supports none, which is the reason the photographs live in their
 * own top-level tree at all.
 */
class BackupRulesTest {

    private fun rules(path: String): Element {
        val file = File(path)
        check(file.exists()) { "missing ${file.absolutePath}" }
        return DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(file).documentElement
    }

    /** Every `<include>`/`<exclude>` path under a parent element, in order. */
    private fun paths(parent: Element, tag: String): List<String> {
        val nodes = parent.getElementsByTagName(tag)
        return (0 until nodes.length).map { index ->
            (nodes.item(index) as Element).getAttribute("path")
        }
    }

    // --- API 26-30 -------------------------------------------------------------

    @Test
    fun `the legacy rules carry the records and nothing else`() {
        val root = rules(BACKUP_RULES)

        assertEquals(listOf("watches", "config.toml"), paths(root, "include"))
    }

    /**
     * An `<exclude>` here would mean somebody had stopped trusting the
     * include-only rule and started enumerating — which cannot be made correct,
     * because slugs are created at runtime and the format has no wildcards.
     */
    @Test
    fun `the legacy rules enumerate no exclusions`() {
        assertTrue(paths(rules(BACKUP_RULES), "exclude").isEmpty())
    }

    // --- API 31+ ---------------------------------------------------------------

    @Test
    fun `cloud backup carries the records only`() {
        val cloud = rules(EXTRACTION_RULES).getElementsByTagName("cloud-backup").item(0) as Element

        assertEquals(listOf("watches", "config.toml"), paths(cloud, "include"))
    }

    /**
     * THE ONE ASSERTION THIS FILE EXISTS FOR. The photographs must never be in
     * the cloud-backup list: the quota is roughly 25 MB, the records are
     * irreplaceable and small, and photographs would exhaust it — so a restore
     * that had silently started including them would bring back neither.
     */
    @Test
    fun `cloud backup never carries the photographs`() {
        val cloud = rules(EXTRACTION_RULES).getElementsByTagName("cloud-backup").item(0) as Element

        assertTrue(
            "media/ is in the cloud-backup rules — the quota is ~25 MB and the " +
                "records must always fit; photographs travel by ZIP (SPEC-ANDROID 3.1)",
            "media" !in paths(cloud, "include"),
        )
    }

    /**
     * Device transfer is the deliberate opposite: no quota, never leaves the two
     * phones, so the photographs go too. Moving to a new phone brings the whole
     * collection; a cloud restore brings the records and leaves the photographs
     * to the ZIP.
     */
    @Test
    fun `device transfer carries the photographs as well`() {
        val transfer =
            rules(EXTRACTION_RULES).getElementsByTagName("device-transfer").item(0) as Element

        assertEquals(listOf("watches", "media", "config.toml"), paths(transfer, "include"))
    }

    @Test
    fun `the two destinations are not the same list`() {
        val root = rules(EXTRACTION_RULES)
        val cloud = root.getElementsByTagName("cloud-backup").item(0) as Element
        val transfer = root.getElementsByTagName("device-transfer").item(0) as Element

        // If these ever become equal, one of the two policies has been lost.
        assertTrue(paths(cloud, "include") != paths(transfer, "include"))
    }

    /** Nothing derived is ever backed up: the cache is disposable by definition. */
    @Test
    fun `neither file mentions a cache or a backup folder`() {
        listOf(BACKUP_RULES, EXTRACTION_RULES).forEach { path ->
            val text = File(path).readText()
            listOf("cache", "backups").forEach { forbidden ->
                assertTrue(
                    "$path names \"$forbidden\" in a rule — everything unlisted is " +
                        "already excluded, so naming it can only be a mistake",
                    !text.substringAfter("-->").contains(forbidden),
                )
            }
        }
    }

    companion object {
        private const val BACKUP_RULES = "src/main/res/xml/backup_rules.xml"
        private const val EXTRACTION_RULES = "src/main/res/xml/data_extraction_rules.xml"
    }
}
