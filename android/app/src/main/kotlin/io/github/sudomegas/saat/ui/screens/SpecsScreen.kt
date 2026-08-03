package io.github.sudomegas.saat.ui.screens

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil3.compose.AsyncImagePainter
import coil3.compose.rememberAsyncImagePainter
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.storage.FacetKind
import io.github.sudomegas.saat.ui.SpecsRow
import io.github.sudomegas.saat.ui.SpecsViewModel
import io.github.sudomegas.saat.ui.specs.SpecsPreset
import java.io.File

/**
 * The Specs list — SPEC-ANDROID 5.3, the desktop's table rethought for a hand.
 *
 * A chip row of presets, then one row per watch. The desktop's columns could not
 * survive a six-inch portrait screen, but the point of them could: studying the
 * whole collection against ONE family of attributes at a time.
 *
 * The preset's cells sit on their own line BELOW the name rather than beside it,
 * which is the layout decision this screen turns on. Sharing the line with a
 * thumbnail and two lines of text leaves about 50dp per cell, and "Stainless
 * Steel" in 50dp is the ellipsis soup the brief warns about. At full width each
 * cell gets half as much again, and the figures the tabular alignment exists for
 * — 41 mm, 200 m — fit comfortably.
 */
@Composable
fun SpecsScreen(
    viewModel: SpecsViewModel,
    onOpenWatch: (String) -> Unit,
    onOpenFilters: () -> Unit,
    onRemoveFilter: (FacetKind, String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    Scaffold(
        // The shell's Scaffold already consumed the system bars.
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            if (!state.isCollectionEmpty) {
                GridTopBar(
                    query = state.query,
                    sort = state.sort,
                    onQueryChange = viewModel::setQuery,
                    onSortChange = viewModel::setSort,
                    onOpenFilters = onOpenFilters,
                    hasActiveFilters = !state.filter.isEmpty,
                )
            }
        },
        modifier = modifier,
    ) { innerPadding ->
        Column(modifier = Modifier.padding(innerPadding)) {
            when {
                !state.isLoaded -> Unit

                state.isCollectionEmpty -> SpecsNotice(R.string.screen_specs_empty)

                else -> {
                    ActiveFilterChips(filter = state.filter, onRemove = onRemoveFilter)
                    PresetChips(active = state.preset, onSelect = viewModel::setPreset)
                    if (state.hasNoMatches) {
                        SpecsNotice(R.string.screen_grid_no_matches)
                    } else {
                        SpecsRows(rows = state.rows, onOpenWatch = onOpenWatch)
                    }
                }
            }
        }
    }
}

@Composable
private fun PresetChips(active: SpecsPreset, onSelect: (SpecsPreset) -> Unit) {
    LazyRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        items(items = SpecsPreset.entries, key = { it.token }) { preset ->
            FilterChip(
                selected = preset == active,
                onClick = { onSelect(preset) },
                label = { Text(text = stringResource(preset.labelRes)) },
            )
        }
    }
}

@Composable
private fun SpecsRows(rows: List<SpecsRow>, onOpenWatch: (String) -> Unit) {
    LazyColumn(modifier = Modifier.fillMaxSize()) {
        items(items = rows, key = { it.slug }) { row ->
            SpecsListRow(row = row, onOpen = { onOpenWatch(row.slug) })
            HorizontalDivider(
                thickness = Dp.Hairline,
                color = MaterialTheme.colorScheme.outlineVariant,
            )
        }
    }
}

@Composable
private fun SpecsListRow(row: SpecsRow, onOpen: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onOpen)
            .padding(horizontal = 16.dp, vertical = 10.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Thumbnail(row.image)
            Column(modifier = Modifier.padding(start = 12.dp)) {
                Text(
                    text = row.brand,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = row.model,
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onSurface,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            row.cells.forEach { cell ->
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.Top,
                ) {
                    // ALWAYS TWO LINES, which is the whole of the alignment.
                    //
                    // Measured on the phone, in two passes. At one line,
                    // "Lug-to-Lug" and "Water Resistance" truncate into the
                    // ellipsis soup this milestone's brief warns about. At
                    // "up to two", they wrap — but then "Diameter" still takes
                    // one line and its figure sits a line higher than its
                    // neighbour's, so the column of figures the preset exists
                    // for no longer reads as a column.
                    //
                    // minLines == maxLines reserves the same height for every
                    // label whatever it says, so every figure in the row starts
                    // at the same y. It is the same trick the grid card uses to
                    // make every card in a row the same height, and for the
                    // same reason: alignment by construction rather than by
                    // luck of the vocabulary.
                    Text(
                        text = stringResource(cell.labelRes),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        minLines = 2,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        text = specValueText(cell.value),
                        // Monospace for the figures so the digits line up down
                        // the column, which is the whole reason the desktop's
                        // table had columns. It costs nothing on the text cells
                        // and is what makes 41 mm and 200 m readable as a set.
                        style = MaterialTheme.typography.bodySmall.copy(
                            fontFamily = FontFamily.Monospace,
                        ),
                        color = if (cell.value == null) {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        } else {
                            MaterialTheme.colorScheme.onSurface
                        },
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
    }
}

@Composable
private fun Thumbnail(file: File?) {
    val painter = rememberAsyncImagePainter(model = file)
    val state by painter.state.collectAsState()

    Box(
        modifier = Modifier
            .size(48.dp)
            .background(MaterialTheme.colorScheme.surfaceContainerHigh),
    ) {
        if (file != null && state !is AsyncImagePainter.State.Error) {
            Image(
                painter = painter,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        }
    }
}

@Composable
private fun SpecsNotice(labelRes: Int) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(32.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = stringResource(labelRes),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
    }
}
