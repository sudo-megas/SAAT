package io.github.sudomegas.saat.ui.compare

import androidx.annotation.StringRes
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.WatchRecord
import io.github.sudomegas.saat.ui.detail.SpecRow
import io.github.sudomegas.saat.ui.detail.SpecValue
import io.github.sudomegas.saat.ui.detail.acquisitionRows
import io.github.sudomegas.saat.ui.detail.caseRows
import io.github.sudomegas.saat.ui.detail.dialRows
import io.github.sudomegas.saat.ui.detail.identityRows
import io.github.sudomegas.saat.ui.detail.maintenanceRows
import io.github.sudomegas.saat.ui.detail.movementRows
import io.github.sudomegas.saat.ui.detail.strapRows
import java.io.File

/**
 * Two watches, side by side — SPEC-ANDROID 5.4, as data.
 *
 * Pure, like [io.github.sudomegas.saat.ui.detail.DetailPage] and for the same
 * reason: "rows where both share a value are dimmed, rows that differ sit at
 * full contrast, rows where neither has a value are hidden" is a claim about
 * classification, and asserting it against a rendered `Row` would need a device.
 *
 * EVERY VALUE ON THIS SCREEN COMES FROM THE DETAIL PAGE'S OWN ROW BUILDERS.
 * AM9's brief is explicit — "this screen must not become a second
 * implementation of value display" — so `movementRows`, `caseRows` and the rest
 * are called here rather than reimplemented, and a formatting fix made for the
 * detail page arrives here for free. The only thing this file knows how to do
 * that the detail page does not is *pair* two watches' rows and classify them.
 *
 * Exactly two watches. SPEC-ANDROID 5.4 records that as the portrait-screen
 * decision, and the type says so: two named fields, not a list that could hold
 * three.
 */
data class ComparePage(
    val left: CompareColumn,
    val right: CompareColumn,
    val groups: List<CompareGroup>,
)

/**
 * Two. SPEC-ANDROID 5.4 records it as a decision, not a limit to relax later:
 * "exactly two watches, side by side, portrait". The desktop compares up to
 * four because it has the width; a phone held upright does not.
 */
const val COMPARE_WATCHES = 2

/** One column's heading: which watch it is, and its photograph if it has one. */
data class CompareColumn(
    val slug: String,
    val brand: String,
    val model: String,
    /** `media/<slug>/<first image>`, or null when the watch has no photographs. */
    val image: File?,
)

/** A titled block. Only groups with at least one surviving row are built. */
data class CompareGroup(@StringRes val titleRes: Int, val rows: List<CompareRow>)

/**
 * One attribute across both watches.
 *
 * A null side is an absent field and renders as the muted em-dash, exactly as it
 * does on the detail page — the difference here is that an absent value on one
 * side and a present one on the other is itself a difference worth reading, so
 * such a row is [RowContrast.DIFFERS] rather than dimmed.
 */
data class CompareRow(
    @StringRes val labelRes: Int,
    val left: SpecValue?,
    val right: SpecValue?,
    val contrast: RowContrast,
)

/**
 * How loudly a row should read. Ported from the desktop's `RowContrast`, whose
 * two cases carry the same meanings.
 *
 * There is no third case for "hidden": a row where neither watch has a value is
 * never built, so anything that reaches the composable has something to say.
 */
enum class RowContrast {
    /** Both watches have this value and the values agree. Dimmed. */
    SHARED,

    /** The values disagree, or one side has none. Full contrast. */
    DIFFERS,
}

/**
 * Build the page, or null when either record failed to load.
 *
 * Both media directories are passed in rather than resolved here, keeping the
 * builder free of `SaatPaths` and therefore testable on a plain JVM — the same
 * bargain `detailPage` makes.
 */
fun comparePage(
    left: WatchRecord,
    leftMedia: File,
    right: WatchRecord,
    rightMedia: File,
): ComparePage? {
    val leftWatch = left.watch ?: return null
    val rightWatch = right.watch ?: return null

    return ComparePage(
        left = left.toColumn(leftWatch, leftMedia),
        right = right.toColumn(rightWatch, rightMedia),
        groups = GROUPS.mapNotNull { group ->
            compareGroup(group.titleRes, group.rows(leftWatch), group.rows(rightWatch))
        },
    )
}

/**
 * The groups, in the model's order — SPEC-ANDROID 5.4.
 *
 * The desktop's `GROUP_ORDER` is Identity, Movement, Case, Dial, Straps,
 * Acquisition. Maintenance is added at the end: the desktop has no maintenance
 * columns because its table view predates them, and a service interval is
 * exactly the sort of thing somebody comparing two watches wants to see.
 */
private class Group(@StringRes val titleRes: Int, val rows: (Watch) -> List<SpecRow>)

private val GROUPS = listOf(
    Group(R.string.screen_detail_group_identity, ::identityRows),
    Group(R.string.screen_detail_group_movement, ::movementRows),
    Group(R.string.screen_detail_group_case, ::caseRows),
    Group(R.string.screen_detail_group_dial, ::dialRows),
    Group(R.string.screen_detail_group_straps, ::strapRows),
    Group(R.string.screen_detail_group_acquisition, ::acquisitionRows),
    Group(R.string.screen_detail_group_maintenance, ::maintenanceRows),
)

/** The group, or null when every one of its rows dropped out. */
internal fun compareGroup(
    @StringRes titleRes: Int,
    left: List<SpecRow>,
    right: List<SpecRow>,
): CompareGroup? {
    val leftByLabel = left.associateBy { it.labelRes }
    val rightByLabel = right.associateBy { it.labelRes }

    val rows = mergeLabels(left, right).mapNotNull { label ->
        val leftValue = leftByLabel[label]?.value
        val rightValue = rightByLabel[label]?.value
        // Neither watch has anything to say: the row is not built at all.
        if (leftValue == null && rightValue == null) return@mapNotNull null

        CompareRow(
            labelRes = label,
            left = leftValue,
            right = rightValue,
            contrast = contrastOf(leftValue, rightValue),
        )
    }

    return if (rows.isEmpty()) null else CompareGroup(titleRes, rows)
}

/**
 * Dimmed only when BOTH sides have a value and the two agree — the desktop's
 * `_all_present_and_equal`, which treats "present on one side, absent on the
 * other" as a difference rather than as a match.
 *
 * The comparison is on the FORMATTED value rather than the raw field, because
 * that is what the owner is reading. [SpecValue] is a data class, so two
 * `Plain("Steel")` are equal and a `Plain` never equals a `Resource`. Two raw
 * values that format identically — 40.001 mm and 40.002 mm both printing as
 * `40 mm` — therefore read as shared, which is the honest answer to "do these
 * two rows differ" when the rows are the only thing on screen.
 */
private fun contrastOf(left: SpecValue?, right: SpecValue?): RowContrast =
    if (left != null && left == right) RowContrast.SHARED else RowContrast.DIFFERS

/**
 * The two label orders, merged into one that respects both.
 *
 * MERGED, NOT ZIPPED, and this is the whole reason the function exists.
 * `movementRows` is conditional — a mechanical watch gets a `power_reserve` row
 * and a quartz gets `battery_life` — so the two lists are not the same length
 * and position N is not the same attribute on both sides. Pairing by index
 * would confidently align "power reserve" against "battery life" and then
 * classify the pair. Everything here is keyed by `labelRes` instead.
 *
 * A two-pointer merge rather than a plain union, so a label only one side
 * carries lands where THAT side puts it. Comparing an automatic against a
 * quartz gives `… power reserve, battery life, accuracy …` — both figures
 * adjacent and in their natural place — where appending the leftovers would
 * have stranded `battery life` at the bottom of the group.
 */
internal fun mergeLabels(left: List<SpecRow>, right: List<SpecRow>): List<Int> {
    val leftLabels = left.map { it.labelRes }
    val rightLabels = right.map { it.labelRes }
    val inLeft = leftLabels.toSet()
    val inRight = rightLabels.toSet()

    // A set, so a label reachable down both paths is still emitted once and the
    // merge cannot produce a duplicate row however the two orders disagree.
    val merged = LinkedHashSet<Int>()
    var i = 0
    var j = 0
    while (i < leftLabels.size || j < rightLabels.size) {
        when {
            i == leftLabels.size -> merged += rightLabels[j++]
            j == rightLabels.size -> merged += leftLabels[i++]
            leftLabels[i] == rightLabels[j] -> {
                merged += leftLabels[i]
                i++
                j++
            }
            // A label the other side does not have at all goes in here, where
            // the side that does have it puts it.
            leftLabels[i] !in inRight -> merged += leftLabels[i++]
            rightLabels[j] !in inLeft -> merged += rightLabels[j++]
            // Both sides carry both labels but in opposite orders. Today's
            // builders never do this — they are the same function over
            // different data — but the loop must still terminate and the result
            // must still be total, so the left order wins and the right catches
            // up on a later turn.
            else -> merged += leftLabels[i++]
        }
    }
    return merged.toList()
}

private fun WatchRecord.toColumn(watch: Watch, mediaDir: File) = CompareColumn(
    slug = slug,
    brand = watch.brand,
    model = watch.model,
    // `images` holds BARE FILENAMES (SPEC-ANDROID 3) and the photographs sit in
    // the sibling media/ tree. File(it).name strips any directory part a
    // hand-edited file could have put there.
    image = watch.images.firstOrNull { it.isNotBlank() }
        ?.let { File(mediaDir, File(it).name) },
)
