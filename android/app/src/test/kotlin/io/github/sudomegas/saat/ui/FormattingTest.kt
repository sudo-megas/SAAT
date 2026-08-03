package io.github.sudomegas.saat.ui

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.LocalDate
import java.util.Locale

/**
 * The display formatters, and the one property that is easy to lose: none of
 * them may read the device's locale.
 *
 * Hard rule 7 is written about the UI *language*, but a number formatter that
 * inherits the default locale breaks the same promise through a side door —
 * the app would render `41,5 mm` and `1.234,50 TRY` on this owner's Turkish
 * phone while `watch.toml` still said `41.5`, and nobody chose that. Worse, a
 * date pattern resolved against a locale with non-Latin digits renders
 * `٠٧.٠٣.٢٠٢٤`.
 *
 * Every test below therefore runs its assertions twice: once under the JVM's
 * own default, and once with the default flipped to Turkish. The second pass is
 * the one that matters, and it is why the formatters name `Locale.ROOT`
 * explicitly rather than relying on the overload that looks equivalent.
 */
class FormattingTest {

    private val original: Locale = Locale.getDefault()

    @After
    fun restoreLocale() {
        Locale.setDefault(original)
    }

    /** Runs [assertions] under the JVM default and again under tr-TR. */
    private fun inEveryLocale(assertions: () -> Unit) {
        assertions()
        Locale.setDefault(Locale.forLanguageTag("tr-TR"))
        assertions()
    }

    @Test
    fun `measurements drop a trailing zero and keep a real fraction`() {
        inEveryLocale {
            assertEquals("41", formatMeasurement(41.0))
            assertEquals("41.5", formatMeasurement(41.5))
            assertEquals("0", formatMeasurement(0.0))
            assertEquals("-2.25", formatMeasurement(-2.25))
        }
    }

    @Test
    fun `dates are DD_MM_YYYY with Latin digits everywhere`() {
        inEveryLocale {
            assertEquals("07.03.2024", formatDate(LocalDate.of(2024, 3, 7)))
            assertEquals("31.12.1999", formatDate(LocalDate.of(1999, 12, 31)))
        }
    }

    @Test
    fun `a signed measurement always carries its sign`() {
        inEveryLocale {
            assertEquals("+8", formatSignedMeasurement(8.0))
            assertEquals("-5", formatSignedMeasurement(-5.0))
            assertEquals("+0", formatSignedMeasurement(0.0))
            // Negative zero is a real Double and prints as "-0" through a naive
            // sign test. A movement running at nothing is not running slow.
            assertEquals("+0", formatSignedMeasurement(-0.0))
            assertEquals("+2.5", formatSignedMeasurement(2.5))
        }
    }

    @Test
    fun `prices group thousands with a comma and never with a full stop`() {
        inEveryLocale {
            assertEquals("1,234.50", formatPrice(1234.5))
            assertEquals("850.00", formatPrice(850.0))
            assertEquals("0.00", formatPrice(0.0))
            assertEquals("1,000,000.00", formatPrice(1_000_000.0))
        }
    }
}
