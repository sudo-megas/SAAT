package io.github.sudomegas.saat.storage

/**
 * Straps from OTHER watches that would fit this one — SPEC-ANDROID 5.6, AM9c.
 *
 * A port of the desktop's `saat/ui/strap_compat.py`, rule for rule, because the
 * two apps answering "what else fits this watch" differently on the same
 * collection would be a worse bug than either being wrong on its own.
 */
data class CompatibleStrap(
    /** The watch the strap belongs to. Tapping the row opens its page. */
    val owner: WatchRecord,
    val strap: Strap,
)

/**
 * Every strap in the collection that fits [target], in collection order.
 *
 * Four rules, all of them the desktop's:
 *
 *  1. **The target needs a lug width.** Without one there is nothing to match
 *     against, so the answer is an empty list and the section disappears —
 *     rather than matching everything, which is what a null-tolerant comparison
 *     would have quietly done.
 *  2. **Both sides must be Owned.** SPEC.md §5.12's reasoning: swapping a strap
 *     only makes sense between watches physically on hand. A strap on a watch
 *     that was sold, or on one still on the wishlist, is not available to put on
 *     anything.
 *  3. **A candidate strap matches on its EFFECTIVE width** — its own
 *     `width_mm`, or its owner's `case.lug_width_mm` when it does not state one
 *     (SPEC.md §4's "defaults to `case.lug_width_mm`"). Most straps in a real
 *     collection never get a width typed in, and matching on the raw field
 *     would find almost nothing.
 *  4. **Never this watch's own straps.** Compared by SLUG rather than by
 *     identity, because the record handed in may be a different instance of the
 *     same watch than the one in the list.
 *
 * Not deduplicated: two identical 20 mm leather straps on two different watches
 * are two straps the owner could reach for, and collapsing them into one would
 * hide where the second one is.
 */
fun compatibleStraps(target: WatchRecord, all: List<WatchRecord>): List<CompatibleStrap> {
    val watch = target.watch ?: return emptyList()
    if (watch.status != Watch.STATUS_OWNED) return emptyList()
    val targetWidth = watch.case.lugWidthMm ?: return emptyList()

    return all.flatMap { candidate ->
        val other = candidate.watch
        if (candidate.slug == target.slug || other == null || other.status != Watch.STATUS_OWNED) {
            return@flatMap emptyList()
        }

        other.straps
            .filter { it.effectiveWidthMm(other) == targetWidth }
            .map { CompatibleStrap(owner = candidate, strap = it) }
    }
}
