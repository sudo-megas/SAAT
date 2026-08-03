package io.github.sudomegas.saat.ui.screens

import io.github.sudomegas.saat.ui.form.FormImage
import io.github.sudomegas.saat.ui.form.StrapFormState
import io.github.sudomegas.saat.ui.form.WatchFormState
import io.github.sudomegas.saat.ui.form.toWatch
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

/**
 * Ordering and removal in the Images group.
 *
 * Both are pure transforms of the form state, which is what lets the two rules
 * that matter be checked without a device: the primary photograph IS index zero,
 * and removing a photograph must not leave a strap pointing at it.
 */
class FormImagesTest {

    @get:Rule
    val temp = TemporaryFolder()

    private fun form(vararg names: String) = WatchFormState.empty().copy(
        brand = "Seiko",
        model = "SKX007",
        images = names.map { FormImage(it) },
    )

    private fun names(state: WatchFormState) = state.images.map { it.filename }

    // --- order ---------------------------------------------------------------

    @Test
    fun `setting the primary moves that photograph to the front`() {
        // SPEC-ANDROID 5.7's "setting the primary" is exactly this, because
        // Watch.images stores the gallery order and the first entry IS the
        // primary. There is no separate flag to keep in step.
        val reordered = form("a.jpg", "b.jpg", "c.jpg").withImageMoved(2, 0)

        assertEquals(listOf("c.jpg", "a.jpg", "b.jpg"), names(reordered))
        assertEquals("c.jpg", reordered.toWatch().images.first())
    }

    @Test
    fun `moving one place keeps everything else in order`() {
        val state = form("a.jpg", "b.jpg", "c.jpg")

        assertEquals(listOf("b.jpg", "a.jpg", "c.jpg"), names(state.withImageMoved(0, 1)))
        assertEquals(listOf("a.jpg", "c.jpg", "b.jpg"), names(state.withImageMoved(1, 2)))
    }

    @Test
    fun `a move that goes nowhere or off the end changes nothing`() {
        val state = form("a.jpg", "b.jpg")

        assertEquals(state, state.withImageMoved(0, 0))
        assertEquals(state, state.withImageMoved(0, 5))
        assertEquals(state, state.withImageMoved(-1, 0))
    }

    @Test
    fun `the order the owner chose is the order that reaches the file`() {
        val watch = form("a.jpg", "b.jpg", "c.jpg").withImageMoved(2, 0).toWatch()

        assertEquals(listOf("c.jpg", "a.jpg", "b.jpg"), watch.images)
    }

    // --- removal -------------------------------------------------------------

    @Test
    fun `removing a saved photograph remembers it for the save to bury`() {
        val removed = form("a.jpg", "b.jpg").withImageRemoved(0)

        assertEquals(listOf("b.jpg"), names(removed))
        assertEquals(listOf("a.jpg"), removed.removedImages)
    }

    @Test
    fun `removing a staged photograph deletes it and remembers nothing`() {
        // It was never part of the collection, so there is nothing to bury —
        // and leaving the cacheDir copy behind would be a file nobody ever
        // deletes.
        val staged = File(temp.newFolder(), "new.jpg").apply { writeBytes(byteArrayOf(1, 2, 3)) }
        val state = form("a.jpg").copy(images = listOf(FormImage("new.jpg", staged)))

        val removed = state.withImageRemoved(0)

        assertEquals(emptyList<String>(), names(removed))
        assertEquals(emptyList<String>(), removed.removedImages)
        assertFalse("the staged copy should be gone", staged.exists())
    }

    @Test
    fun `removing a photograph clears any strap that pointed at it`() {
        // The desktop does this too. A strap naming a photograph that is gone
        // renders as a permanently broken thumbnail, and the reference would
        // survive every future edit because nothing else ever looks at it.
        val state = form("front.jpg", "tan.jpg").copy(
            straps = listOf(
                StrapFormState(material = "Leather", image = "tan.jpg"),
                StrapFormState(material = "Steel", image = "front.jpg"),
            ),
        )

        val removed = state.withImageRemoved(1)

        assertEquals(listOf("", "front.jpg"), removed.straps.map { it.image })
        assertTrue(removed.toWatch().straps.first().image == null)
    }

    @Test
    fun `removing the primary promotes the next photograph`() {
        // Nothing has to do the promoting: the primary is index zero, so
        // removing it makes the next one primary by construction.
        val removed = form("a.jpg", "b.jpg", "c.jpg").withImageRemoved(0)

        assertEquals("b.jpg", removed.toWatch().images.first())
    }

    @Test
    fun `removing an index that is not there changes nothing`() {
        val state = form("a.jpg")

        assertEquals(state, state.withImageRemoved(7))
    }
}
