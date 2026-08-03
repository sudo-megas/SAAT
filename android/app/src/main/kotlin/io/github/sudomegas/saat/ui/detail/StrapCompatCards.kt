package io.github.sudomegas.saat.ui.detail

import io.github.sudomegas.saat.storage.WatchRecord
import io.github.sudomegas.saat.storage.compatibleStraps
import java.io.File

/**
 * A strap from another watch, ready to render — AM9c.
 *
 * [ownerSlug] is what a tap navigates to. The name is carried alongside rather
 * than looked up at draw time, so the row can say whose strap it is without the
 * composable holding the whole collection.
 */
data class CompatibleStrapCard(
    val ownerSlug: String,
    val ownerBrand: String,
    val ownerModel: String,
    /** The same [StrapCard] shape the watch's own straps render as. */
    val strap: StrapCard,
)

/**
 * The compatible straps, as cards.
 *
 * NOT PART OF [DetailPage], deliberately. That builder's contract is that the
 * page is a pure function of ONE record and its media directory, which is what
 * makes `DetailPageTest` possible; this question is about the whole collection.
 * So it sits beside `wear` and `maintenance` on the state instead — three
 * things the page needs that a single record cannot answer — and stays its own
 * pure function, testable on the same terms.
 *
 * [mediaFor] resolves a slug to its media directory rather than a `SaatPaths`
 * being passed in, so nothing here knows what a `Context` is. Each strap's
 * photograph comes from ITS OWN owner's folder, which is the whole reason this
 * cannot reuse the target's `mediaDir`.
 */
fun compatibleStrapCards(
    target: WatchRecord,
    all: List<WatchRecord>,
    mediaFor: (String) -> File,
): List<CompatibleStrapCard> = compatibleStraps(target, all).mapNotNull { match ->
    val owner = match.owner.watch ?: return@mapNotNull null
    CompatibleStrapCard(
        ownerSlug = match.owner.slug,
        ownerBrand = owner.brand,
        ownerModel = owner.model,
        strap = match.strap.toCard(owner, mediaFor(match.owner.slug)),
    )
}
