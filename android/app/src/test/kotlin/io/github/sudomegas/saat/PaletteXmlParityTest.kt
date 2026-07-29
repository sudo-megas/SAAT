package io.github.sudomegas.saat

import androidx.compose.ui.graphics.Color
import io.github.sudomegas.saat.ui.theme.DefaultDark
import io.github.sudomegas.saat.ui.theme.DefaultLight
import io.github.sudomegas.saat.ui.theme.SaatRoles
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

/**
 * The palette exists twice — as Kotlin constants that Compose paints with, and
 * as `colors.xml` entries for the handful of things Compose cannot own (the
 * pre-Compose window background, the adaptive-icon background, the AppCompat
 * host theme). Two copies of a colour always eventually drift, and the drift is
 * invisible: a stale `windowBackground` shows only as a one-frame flash at cold
 * start, which nobody notices in review.
 *
 * Parses the XML off disk rather than through `Resources`, so this stays a
 * plain JVM test with no Robolectric.
 */
class PaletteXmlParityTest {

    private fun colours(path: String): Map<String, String> {
        val file = File(path)
        check(file.exists()) { "missing $path (working dir: ${File(".").absolutePath})" }

        val doc = DocumentBuilderFactory.newInstance()
            .apply { isNamespaceAware = true }
            .newDocumentBuilder()
            .parse(file)

        val nodes = doc.getElementsByTagName("color")
        return (0 until nodes.length).associate { i ->
            val node = nodes.item(i)
            val name = node.attributes.getNamedItem("name").nodeValue
            name to node.textContent.trim().uppercase()
        }
    }

    /** Kotlin `Color` back to the `#AARRGGBB` spelling used in colors.xml. */
    private fun Color.toHex(): String {
        val argb = value.toLong() ushr 32
        return "#%08X".format(argb)
    }

    private fun assertParity(path: String, roles: SaatRoles) {
        val xml = colours(path)
        mapOf(
            "plate" to roles.plate,
            "plate_high" to roles.plateHigh,
            "gilt" to roles.gilt,
            "ruby" to roles.ruby,
        ).forEach { (name, expected) ->
            assertEquals(
                "$path: @color/$name has drifted from its Kotlin constant",
                expected.toHex(),
                xml[name],
            )
        }
    }

    @Test
    fun `values colors_xml matches DefaultLight`() =
        assertParity("src/main/res/values/colors.xml", DefaultLight)

    @Test
    fun `values-night colors_xml matches DefaultDark`() =
        assertParity("src/main/res/values-night/colors.xml", DefaultDark)
}
