package io.github.sudomegas.saat.ui.detail

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The typed-name guard on Delete.
 *
 * Exact, matching the desktop's `text == self._model`. Every case below that
 * fails is a case a looser rule would have let through, and the guard exists so
 * that deleting a watch cannot be a gesture.
 */
class DeleteGuardTest {

    @Test
    fun `the exact model name confirms`() {
        assertTrue(deleteConfirmed("SARB033", "SARB033"))
        assertTrue(deleteConfirmed("Amphibian 420", "Amphibian 420"))
    }

    @Test
    fun `a different case does not confirm`() {
        // The field turns autocapitalisation off precisely so the keyboard
        // cannot produce this on the owner's behalf.
        assertFalse(deleteConfirmed("sarb033", "SARB033"))
        assertFalse(deleteConfirmed("Sarb033", "SARB033"))
    }

    @Test
    fun `stray whitespace does not confirm`() {
        assertFalse(deleteConfirmed("SARB033 ", "SARB033"))
        assertFalse(deleteConfirmed(" SARB033", "SARB033"))
        assertFalse(deleteConfirmed("Amphibian420", "Amphibian 420"))
    }

    @Test
    fun `nothing typed never confirms, whatever the model is called`() {
        assertFalse(deleteConfirmed("", "SARB033"))
        // Including the degenerate case: a watch whose model somehow reads as
        // empty must not be deletable by touching nothing.
        assertFalse(deleteConfirmed("", " "))
    }

    @Test
    fun `a prefix or a superset does not confirm`() {
        assertFalse(deleteConfirmed("SARB", "SARB033"))
        assertFalse(deleteConfirmed("SARB0333", "SARB033"))
    }
}
