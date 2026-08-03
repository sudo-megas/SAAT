package io.github.sudomegas.saat.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AssistChip
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.storage.CollectionSummary
import io.github.sudomegas.saat.storage.Facet
import io.github.sudomegas.saat.storage.FacetKind
import io.github.sudomegas.saat.storage.WatchFilter
import io.github.sudomegas.saat.ui.FiltersViewModel
import io.github.sudomegas.saat.ui.formatPrice
import io.github.sudomegas.saat.ui.form.CASE_MATERIALS
import io.github.sudomegas.saat.ui.form.EnumChoice
import io.github.sudomegas.saat.ui.form.GROUPS
import io.github.sudomegas.saat.ui.form.MOVEMENT_KINDS
import io.github.sudomegas.saat.ui.form.STATUSES
import io.github.sudomegas.saat.ui.form.STYLES
import io.github.sudomegas.saat.ui.form.labelFor

/**
 * The filter sheet — SPEC-ANDROID 5.12, the desktop sidebar folded into a
 * bottom sheet, with 5.11's collection summary as its footer.
 *
 * A sheet rather than a screen because filtering is something you do TO the list
 * you are looking at: it slides over the grid, you tap, the counts move, and the
 * grid behind it is already narrowing. A full screen would hide the thing being
 * filtered at the moment you are deciding how to filter it.
 *
 * WITH AN EMPTY COLLECTION THE SHEET IS JUST THE FOOTER. Every facet is derived
 * from values the collection actually holds, so an empty collection produces no
 * facets at all — and the brief asks for exactly that rather than eight empty
 * headings.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FilterSheet(viewModel: FiltersViewModel, onDismiss: () -> Unit) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = stringResource(R.string.screen_filters_title),
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                if (!state.filter.isEmpty) {
                    TextButton(onClick = viewModel::clear) {
                        Text(text = stringResource(R.string.action_clear_filters))
                    }
                }
            }

            state.facets.forEach { facet ->
                FacetBlock(
                    facet = facet,
                    selected = state.filter.values(facet.kind),
                    onToggle = { value -> viewModel.toggle(facet.kind, value) },
                )
            }

            SummaryFooter(state.summary)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun FacetBlock(facet: Facet, selected: Set<String>, onToggle: (String) -> Unit) {
    Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp)) {
        Text(
            text = stringResource(facet.kind.titleRes()),
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(bottom = 6.dp),
        )
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            facet.values.forEach { value ->
                FilterChip(
                    selected = value.value in selected,
                    onClick = { onToggle(value.value) },
                    label = {
                        Text(
                            text = stringResource(
                                R.string.screen_filters_facet_value,
                                facet.kind.label(value.value),
                                value.count,
                            )
                        )
                    },
                )
            }
        }
    }
}

/**
 * The collection summary — SPEC-ANDROID 5.11.
 *
 * Plain figures. No charts, no gauges, no progress rings: the spec says so, and
 * a collection of eleven watches has nothing to plot that a sentence does not
 * say better.
 */
@Composable
private fun SummaryFooter(summary: CollectionSummary) {
    Column(modifier = Modifier.padding(top = 8.dp)) {
        HorizontalDivider(
            thickness = Dp.Hairline,
            color = MaterialTheme.colorScheme.outlineVariant,
        )
        Column(
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(
                text = pluralStringResource(
                    R.plurals.screen_filters_summary_count,
                    summary.watchCount,
                    summary.watchCount,
                ),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
            summary.byMovementKind.forEach { (kind, count) ->
                // The kind is a schema value here too — the summary counted
                // `Automatic: 2` in Turkish until it asked for the label. A
                // movement the schema has never heard of keeps its own spelling.
                val label = labelFor(kind, MOVEMENT_KINDS)?.let { stringResource(it) } ?: kind
                Text(
                    text = stringResource(R.string.screen_filters_summary_kind, label, count),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            summary.valueByCurrency.forEach { (currency, total) ->
                Text(
                    text = if (currency.isEmpty()) {
                        // A price with no currency is still money that was
                        // spent, so it is counted — as an unlabelled figure
                        // rather than folded into TRY, which would invent a
                        // fact about what was paid.
                        formatPrice(total)
                    } else {
                        stringResource(R.string.field_value_price, formatPrice(total), currency)
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

/**
 * The active filters, under the top bar — this milestone's item 7.
 *
 * "So state is never hidden behind the closed sheet": a collection that is
 * quietly showing three of eleven watches, with nothing on screen saying why, is
 * a collection that appears to have lost eight. Each chip dismisses the one
 * value it names.
 */
@Composable
fun ActiveFilterChips(filter: WatchFilter, onRemove: (FacetKind, String) -> Unit) {
    if (filter.isEmpty) return

    val active = FacetKind.entries.flatMap { kind -> filter.values(kind).map { kind to it } }

    LazyRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        items(active.size, key = { "${active[it].first}-${active[it].second}" }) { index ->
            val (kind, value) = active[index]
            AssistChip(
                onClick = { onRemove(kind, value) },
                label = {
                    Text(
                        text = stringResource(
                            R.string.screen_filters_active_chip,
                            kind.label(value),
                        )
                    )
                },
            )
        }
    }
}

/**
 * A facet value's label.
 *
 * Five of these facets count schema `enum*` values and are translated the same
 * way they are everywhere else. An earlier version of this comment called all of
 * them "the owner's own data", which is true of a tag and not of a status: the
 * sheet headed a section `Durum` and listed `Owned (3)` beneath it, and the
 * dismiss chip above the grid said `Automatic: 2`, on a fully Turkish
 * interface.
 *
 * A value the schema does not know still falls through to itself, so a group
 * the owner invented reads as they typed it — and a tag, which is nothing but
 * the owner's word, has no choice list to consult at all.
 */
@Composable
private fun FacetKind.label(value: String): String = when (this) {
    FacetKind.NOT_WORN_90 -> stringResource(R.string.screen_filters_not_worn)
    FacetKind.LUG_WIDTH -> stringResource(R.string.field_value_mm, value)
    else -> choices()?.let { labelFor(value, it) }?.let { stringResource(it) } ?: value
}

/**
 * The choice list a facet's values are drawn from, or null when they are the
 * owner's own words.
 *
 * Exhaustive for the same reason [titleRes] is: a facet added later must say
 * which of the two it is rather than defaulting quietly to untranslated.
 */
private fun FacetKind.choices(): List<EnumChoice>? = when (this) {
    FacetKind.STATUS -> STATUSES
    FacetKind.STYLE -> STYLES
    FacetKind.GROUP -> GROUPS
    FacetKind.MOVEMENT_KIND -> MOVEMENT_KINDS
    FacetKind.CASE_MATERIAL -> CASE_MATERIALS
    FacetKind.LUG_WIDTH -> null
    FacetKind.TAG -> null
    FacetKind.NOT_WORN_90 -> null
}

/**
 * `FacetKind` lives in `storage/` and holds no resource id — the storage layer
 * has no business knowing about `R`. Exhaustive, so a facet added without a
 * title will not compile.
 */
private fun FacetKind.titleRes(): Int = when (this) {
    FacetKind.STATUS -> R.string.screen_filters_facet_status
    FacetKind.STYLE -> R.string.screen_filters_facet_style
    FacetKind.GROUP -> R.string.screen_filters_facet_group
    FacetKind.MOVEMENT_KIND -> R.string.screen_filters_facet_movement_kind
    FacetKind.CASE_MATERIAL -> R.string.screen_filters_facet_case_material
    FacetKind.LUG_WIDTH -> R.string.screen_filters_facet_lug_width
    FacetKind.TAG -> R.string.screen_filters_facet_tags
    FacetKind.NOT_WORN_90 -> R.string.screen_filters_facet_wear
}
