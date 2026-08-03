package io.github.sudomegas.saat.ui.screens

import androidx.annotation.StringRes
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil3.compose.AsyncImagePainter
import coil3.compose.rememberAsyncImagePainter
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.ui.CompareViewModel
import io.github.sudomegas.saat.ui.compare.CompareColumn
import io.github.sudomegas.saat.ui.compare.CompareGroup
import io.github.sudomegas.saat.ui.compare.CompareRow
import io.github.sudomegas.saat.ui.compare.RowContrast
import io.github.sudomegas.saat.ui.detail.SpecValue

/**
 * Two watches, side by side — SPEC-ANDROID 5.4.
 *
 * THE COLUMN HEADER DOES NOT SCROLL. Everything below it is one long list of
 * attributes, and a comparison whose column headings have scrolled off the top
 * is two anonymous columns of text: the reader has to remember which watch is
 * on the left. So the header sits outside the `LazyColumn` and the rows scroll
 * under it.
 *
 * All the classification happened before this file ran — see
 * [io.github.sudomegas.saat.ui.compare.comparePage]. What is left here is
 * exactly one decision, made twice: which colour a row's values take.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CompareScreen(
    viewModel: CompareViewModel,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val backLabel = stringResource(R.string.action_back)

    Scaffold(
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            TopAppBar(
                title = { Text(text = stringResource(R.string.screen_compare_title)) },
                navigationIcon = {
                    IconButton(
                        onClick = onBack,
                        modifier = Modifier.semantics { contentDescription = backLabel },
                    ) {
                        BackChevron(tint = MaterialTheme.colorScheme.onSurface)
                    }
                },
            )
        },
        modifier = modifier,
    ) { innerPadding ->
        val page = state.page

        Column(modifier = Modifier.padding(innerPadding)) {
            when {
                // Deleted from under the page while it sat on the back stack.
                // Said plainly rather than shown as an empty comparison.
                state.isMissing -> Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(32.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = stringResource(R.string.screen_compare_missing),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                    )
                }

                // Not read yet — blank, not a claim. Same rule as the grid's.
                page == null -> Unit

                else -> {
                    CompareHeader(left = page.left, right = page.right)
                    LazyColumn(
                        contentPadding = PaddingValues(bottom = 24.dp),
                        modifier = Modifier.fillMaxSize(),
                    ) {
                        page.groups.forEach { group ->
                            item(key = "group-${group.titleRes}") {
                                CompareSectionHeader(group.titleRes)
                            }
                            compareRows(group)
                        }
                    }
                }
            }
        }
    }
}

/**
 * Keyed by group AND label: `field_brand` is unique within Identity but the
 * same `labelRes` could legitimately appear in two groups one day, and a
 * duplicate key is a crash rather than a cosmetic problem.
 */
private fun LazyListScope.compareRows(group: CompareGroup) {
    group.rows.forEach { row ->
        item(key = "row-${group.titleRes}-${row.labelRes}") {
            CompareRowLine(row)
        }
    }
}

/** The two watches, pinned above the scrolling attributes. */
@Composable
private fun CompareHeader(left: CompareColumn, right: CompareColumn) {
    Column {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // The label column is reserved in the header too, so the two
            // photographs sit exactly above the two value columns they belong
            // to rather than being centred over the whole width.
            Box(modifier = Modifier.width(LABEL_COLUMN_WIDTH))
            CompareHeaderColumn(column = left, modifier = Modifier.weight(1f))
            CompareHeaderColumn(column = right, modifier = Modifier.weight(1f))
        }
        HorizontalDivider(
            thickness = Dp.Hairline,
            color = MaterialTheme.colorScheme.outlineVariant,
        )
    }
}

@Composable
private fun CompareHeaderColumn(column: CompareColumn, modifier: Modifier = Modifier) {
    Column(modifier = modifier) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(COLUMN_IMAGE_HEIGHT)
                .background(MaterialTheme.colorScheme.surfaceContainerHigh),
        ) {
            ColumnImage(column)
        }
        Text(
            text = column.brand,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(top = 6.dp),
        )
        Text(
            text = column.model,
            style = MaterialTheme.typography.titleSmall,
            color = MaterialTheme.colorScheme.onSurface,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

/**
 * The photograph, or nothing at all.
 *
 * No placeholder measurements here, unlike the grid's tile: the diameter and lug
 * width are rows further down this very screen, and printing them in the header
 * as well would put the same figure on screen twice — once where it can be
 * compared and once where it cannot.
 */
@Composable
private fun ColumnImage(column: CompareColumn) {
    val image = column.image ?: return
    val painter = rememberAsyncImagePainter(model = image)
    val state by painter.state.collectAsState()

    if (state is AsyncImagePainter.State.Error) return
    Image(
        painter = painter,
        contentDescription = null,
        contentScale = ContentScale.Crop,
        modifier = Modifier.fillMaxSize(),
    )
}

/** Same hairline-above-the-title rule as the detail page's spec groups. */
@Composable
private fun CompareSectionHeader(@StringRes titleRes: Int) {
    Column(modifier = Modifier.padding(top = 16.dp)) {
        HorizontalDivider(
            thickness = Dp.Hairline,
            color = MaterialTheme.colorScheme.outlineVariant,
        )
        Text(
            text = stringResource(titleRes),
            style = MaterialTheme.typography.titleSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 4.dp),
        )
    }
}

/**
 * One attribute across both watches.
 *
 * THE DIMMING IS THE WHOLE SCREEN. A row both watches agree on is information
 * the owner does not need — it is why they look the same — so it recedes to
 * `onSurfaceVariant`, and the rows that differ keep `onSurface` and read at a
 * glance down the page. An absent value is muted regardless, because an em-dash
 * at full contrast would shout about a field nobody filled in.
 */
@Composable
private fun CompareRowLine(row: CompareRow) {
    val differs = row.contrast == RowContrast.DIFFERS

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 3.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Text(
            text = stringResource(row.labelRes),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.width(LABEL_COLUMN_WIDTH),
        )
        CompareValue(value = row.left, differs = differs, modifier = Modifier.weight(1f))
        CompareValue(value = row.right, differs = differs, modifier = Modifier.weight(1f))
    }
}

@Composable
private fun CompareValue(
    value: SpecValue?,
    differs: Boolean,
    modifier: Modifier = Modifier,
) {
    Text(
        text = specValueText(value),
        style = MaterialTheme.typography.bodyMedium,
        color = if (differs && value != null) {
            MaterialTheme.colorScheme.onSurface
        } else {
            MaterialTheme.colorScheme.onSurfaceVariant
        },
        modifier = modifier,
    )
}

/**
 * Narrower than the detail page's 132dp: this screen carries two value columns
 * where that one carries a single full-width value, and the labels here are the
 * same words. Values wrap rather than the label being allowed to squeeze them.
 */
private val LABEL_COLUMN_WIDTH = 96.dp

private val COLUMN_IMAGE_HEIGHT = 120.dp
