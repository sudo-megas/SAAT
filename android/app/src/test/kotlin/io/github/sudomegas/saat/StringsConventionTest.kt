package io.github.sudomegas.saat

import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

/**
 * Guards the string-resource discipline AM1 item 7 asks for, from the first
 * commit rather than from AM11.
 *
 * Two rules, and the second is the one that will actually save work:
 *
 *  1. No user-visible literal ever appears in a composable. AM11 adds
 *     `values-tr/`, and a string sweep at that point would be the expensive way
 *     to do it.
 *  2. Every resource name carries a role prefix. The desktop gets away with a
 *     flat vocabulary because Qt translation contexts disambiguate — the same
 *     English word can take different Turkish translations in different places.
 *     Android string resources are one flat namespace with no such mechanism,
 *     and several terms genuinely recur: "Power Reserve" is both a movement
 *     field label and a complication value; "GMT", "None", "Other",
 *     "Chronograph" and "Silicone" each appear in two or three enum lists.
 *     Collapsing those into one key produces wrong Turkish, and it only becomes
 *     visible in AM11 when the sweep is frozen.
 */
class StringsConventionTest {

    private val allowedPrefixes = listOf(
        "app_",
        "nav_",
        "screen_",
        "settings_",
        "action_",
        "error_",
        "field_",
        "enum_",
    )

    private fun stringNames(): List<String> {
        val file = File("src/main/res/values/strings.xml")
        check(file.exists()) { "missing ${file.absolutePath}" }

        val doc = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(file)
        val nodes = doc.getElementsByTagName("string")
        return (0 until nodes.length).map {
            nodes.item(it).attributes.getNamedItem("name").nodeValue
        }
    }

    @Test
    fun `every string resource carries a role prefix`() {
        val offenders = stringNames().filterNot { name ->
            allowedPrefixes.any { name.startsWith(it) }
        }
        assertTrue(
            "these need one of $allowedPrefixes — see android/docs/ANDROID-STRINGS.md: $offenders",
            offenders.isEmpty(),
        )
    }

    @Test
    fun `enum values are namespaced by their group`() {
        // enum_<group>_<value>, so enum_complication_power_reserve can never
        // collide with field_power_reserve.
        val malformed = stringNames()
            .filter { it.startsWith("enum_") }
            .filterNot { it.count { ch -> ch == '_' } >= 2 }
        assertTrue(
            "enum_* keys must be enum_<group>_<value>: $malformed",
            malformed.isEmpty(),
        )
    }

    @Test
    fun `no user-visible literal appears in a composable`() {
        val sources = File("src/main/kotlin").walkTopDown().filter { it.extension == "kt" }

        // Text("…"), Text(text = "…") and the same for contentDescription. A
        // bare "" is allowed — it is an absence, not a message.
        val literalInText = Regex("""\b(Text|Button|Label)\s*\(\s*(text\s*=\s*)?"[^"]+"""")
        val literalContentDescription = Regex("""contentDescription\s*=\s*"[^"]+"""")

        val offenders = sources.flatMap { file ->
            file.readLines().withIndex().filter { (_, line) ->
                literalInText.containsMatchIn(line) || literalContentDescription.containsMatchIn(line)
            }.map { (i, line) -> "${file.name}:${i + 1}  ${line.trim()}" }
        }.toList()

        assertTrue(
            "user-visible strings must come from resources, not literals:\n" +
                offenders.joinToString("\n"),
            offenders.isEmpty(),
        )
    }
}
