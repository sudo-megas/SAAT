package io.github.sudomegas.saat

import androidx.compose.ui.graphics.Color
import io.github.sudomegas.saat.ui.theme.DefaultDark
import io.github.sudomegas.saat.ui.theme.DefaultLight
import io.github.sudomegas.saat.ui.theme.SaatRoles
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The desktop's contrast matrix, applied to the static fallback palette.
 *
 * Thresholds are the desktop's and the reasoning carries over unchanged: the
 * type scale is small enough that nothing qualifies as WCAG "large text", so
 * text roles get no 3:1 discount. gilt and ruby as small accent shapes get 3:1;
 * as solid fills carrying `plate` as their label, 4.5:1.
 *
 * `rule` is deliberately never checked against text. It is a hairline colour at
 * roughly 1.4:1 against both backgrounds, and the desktop's own test file says
 * in so many words that pairing it with text is the thing to avoid rather than
 * the thing to measure. In the Material mapping it lands on `outlineVariant`
 * (decorative) and never on `outline` (interactive) for exactly this reason.
 *
 * NOT covered here, and not coverable: dynamic colour. When the palette is
 * derived from the user's wallpaper there are no constants to assert. That is
 * an eye check on a real device, listed in the AM1 verification table.
 */
class ThemeContrastTest {

    private data class Pair3(val palette: String, val field: String, val background: String)

    /**
     * Ported from the desktop's KNOWN_CONTRAST_SHORTFALLS, and it TIGHTENS
     * rather than waives: the stored value is the exact measured ratio, so any
     * regression below it still fails. Default Dark's destructive button —
     * #CF3931 filled, #1C1B19 label — is an accepted 3.51:1, recorded on the
     * desktop side as a deliberate product decision rather than an oversight.
     */
    private val knownShortfalls = mapOf(
        Pair3("default-dark", "ruby", "plate") to 3.509859287322408,
    )

    private fun minimumFor(palette: String, field: String, background: String, default: Double) =
        knownShortfalls[Pair3(palette, field, background)] ?: default

    private fun backgrounds(roles: SaatRoles) =
        listOf("plate" to roles.plate, "plate_high" to roles.plateHigh)

    private fun palettes() = listOf("default-light" to DefaultLight, "default-dark" to DefaultDark)

    @Test
    fun `wcag helper matches the desktop's reference values`() {
        assertEquals(21.0, contrastRatio(Color.Black, Color.White), 0.01)
        assertEquals(1.0, contrastRatio(Color(0xFF1C1B19), Color(0xFF1C1B19)), 0.0001)
        // Symmetric by construction, like the desktop's.
        assertEquals(
            contrastRatio(Color(0xFF1C1B19), Color(0xFFE8E4DC)),
            contrastRatio(Color(0xFFE8E4DC), Color(0xFF1C1B19)),
            0.0000001,
        )
    }

    @Test
    fun `text and text_muted meet 4_5 to 1 against both backgrounds`() {
        palettes().forEach { (name, roles) ->
            listOf("text" to roles.text, "text_muted" to roles.textMuted).forEach { (field, colour) ->
                backgrounds(roles).forEach { (bgName, bg) ->
                    val ratio = contrastRatio(colour, bg)
                    val minimum = minimumFor(name, field, bgName, 4.5)
                    assertTrue(
                        "$name: $field on $bgName is %.4f, needs %.4f".format(ratio, minimum),
                        ratio >= minimum - 1e-9,
                    )
                }
            }
        }
    }

    @Test
    fun `gilt and ruby meet 3 to 1 against both backgrounds`() {
        palettes().forEach { (name, roles) ->
            listOf("gilt" to roles.gilt, "ruby" to roles.ruby).forEach { (field, colour) ->
                backgrounds(roles).forEach { (bgName, bg) ->
                    val ratio = contrastRatio(colour, bg)
                    val minimum = minimumFor(name, field, bgName, 3.0)
                    assertTrue(
                        "$name: $field on $bgName is %.4f, needs %.4f".format(ratio, minimum),
                        ratio >= minimum - 1e-9,
                    )
                }
            }
        }
    }

    /**
     * The on-accent pairing. This is what makes `onPrimary == onError == plate`
     * safe rather than merely faithful — if the mapping ever changed to white
     * or black on gilt, this is the test that would object.
     */
    @Test
    fun `plate as text on gilt and ruby meets 4_5 to 1`() {
        palettes().forEach { (name, roles) ->
            listOf("gilt" to roles.gilt, "ruby" to roles.ruby).forEach { (field, accent) ->
                val ratio = contrastRatio(roles.plate, accent)
                val minimum = minimumFor(name, field, "plate", 4.5)
                assertTrue(
                    "$name: plate on $field is %.4f, needs %.4f".format(ratio, minimum),
                    ratio >= minimum - 1e-9,
                )
            }
        }
    }

    /**
     * Guards the mapping itself, not just the colours: `rule` must never end up
     * somewhere that needs contrast. It is 1.4:1 and would be invisible.
     */
    @Test
    fun `rule is too low contrast to ever carry text and that is expected`() {
        palettes().forEach { (name, roles) ->
            backgrounds(roles).forEach { (bgName, bg) ->
                val ratio = contrastRatio(roles.rule, bg)
                assertTrue(
                    "$name: rule on $bgName is %.2f — if this ever exceeds 3.0 the "
                        .format(ratio) + "hairline has become a real colour and the mapping needs review",
                    ratio < 3.0,
                )
            }
        }
    }
}
