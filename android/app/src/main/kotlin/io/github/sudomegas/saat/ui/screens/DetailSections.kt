package io.github.sudomegas.saat.ui.screens

import androidx.annotation.StringRes
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImagePainter
import coil3.compose.rememberAsyncImagePainter
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.ui.detail.DetailPage
import io.github.sudomegas.saat.ui.detail.LogLine
import io.github.sudomegas.saat.ui.detail.SpecGroup
import io.github.sudomegas.saat.ui.detail.StrapCard
import io.github.sudomegas.saat.ui.detail.TimingLine

/**
 * The spec groups, in the model's order — SPEC-ANDROID 5.6.
 *
 * Emitted as `LazyColumn` items rather than as one composable holding a column,
 * so a long log scrolls as a list instead of composing every entry the moment
 * the page opens.
 *
 * Every section here governs its own visibility from its own emptiness, and
 * every one of those decisions was already taken in `detailPage`: a group that
 * arrives in [DetailPage.specGroups] has at least one filled row, and the four
 * list-shaped sections simply skip an empty list. Nothing renders a heading over
 * a column of dashes.
 */
internal fun LazyListScope.detailSections(page: DetailPage) {
    page.specGroups.forEach { group ->
        item(key = "group-${group.titleRes}") { SpecGroupBlock(group) }
    }

    if (page.straps.isNotEmpty()) {
        item(key = "straps-header") { SectionHeader(R.string.screen_detail_group_straps) }
        // Keyed by position, not by content: two identical black leather straps
        // is an ordinary thing for a collection to hold, and a content key would
        // collide and crash the list.
        itemsIndexed(page.straps, key = { index, _ -> "strap-$index" }) { _, strap ->
            StrapBlock(strap)
        }
    }

    if (page.log.isNotEmpty()) {
        item(key = "log-header") { SectionHeader(R.string.screen_detail_group_log) }
        itemsIndexed(page.log, key = { index, _ -> "log-$index" }) { _, entry ->
            LogBlock(entry)
        }
    }

    if (page.timing.isNotEmpty()) {
        item(key = "timing-header") { SectionHeader(R.string.screen_detail_group_timing) }
        itemsIndexed(page.timing, key = { index, _ -> "timing-$index" }) { _, reading ->
            TimingBlock(reading)
        }
    }

    page.notes?.let { notes ->
        item(key = "notes-header") { SectionHeader(R.string.screen_detail_group_notes) }
        item(key = "notes") {
            Text(
                text = notes,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
            )
        }
    }
}

/**
 * A group heading, over a hairline.
 *
 * The rule above the title rather than a box around the group: SPEC-ANDROID 6
 * asks for "hairline dividers, no decoration beyond Material defaults", and a
 * page of nine outlined cards would be nine boxes competing with the one
 * photograph the page is actually about.
 */
@Composable
private fun SectionHeader(@StringRes titleRes: Int) {
    Column(modifier = Modifier.padding(top = 20.dp)) {
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

@Composable
private fun SpecGroupBlock(group: SpecGroup) {
    Column {
        SectionHeader(group.titleRes)
        group.rows.forEach { row ->
            SpecRowLine(
                label = stringResource(row.labelRes),
                value = specValueText(row.value),
                muted = row.value == null,
            )
        }
    }
}

/**
 * Label left, value right, both on one line.
 *
 * The label column is a fixed width rather than a `weight`, so every value in
 * every group starts at the same x — a column of figures that jogs left and
 * right by a few pixels per row is harder to read down than one that does not.
 * It is a `Row` with `Alignment.Top` so a long wrapped value does not drag its
 * label down to the middle of the block.
 */
@Composable
private fun SpecRowLine(label: String, value: String, muted: Boolean) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 3.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.width(LABEL_WIDTH),
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            color = if (muted) {
                MaterialTheme.colorScheme.onSurfaceVariant
            } else {
                MaterialTheme.colorScheme.onSurface
            },
            modifier = Modifier.weight(1f),
        )
    }
}

private val LABEL_WIDTH = 132.dp

/**
 * One strap: its photograph when it has one, its own attributes, and a mark
 * when it is the strap currently on the watch.
 *
 * Strap compatibility — other watches' straps that would fit this one — is
 * SPEC-ANDROID 5.6 as well, and is deferred to AM9 by this milestone's brief.
 */
@Composable
private fun StrapBlock(strap: StrapCard) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (strap.image != null) {
            StrapPhoto(strap)
        }
        Column(modifier = Modifier.weight(1f)) {
            val description = listOfNotNull(strap.material, strap.colour)
            Text(
                text = description.takeIf { it.isNotEmpty() }
                    ?.joinToString(stringResource(R.string.screen_detail_separator))
                    ?: stringResource(R.string.field_absent),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
            val detail = listOfNotNull(
                strap.widthMm?.let { stringResource(R.string.field_value_mm, it.toString()) },
                strap.clasp,
            )
            if (detail.isNotEmpty()) {
                Text(
                    text = detail.joinToString(stringResource(R.string.screen_detail_separator)),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        if (strap.fitted) {
            Text(
                text = stringResource(R.string.screen_detail_strap_fitted),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.primary,
                textAlign = TextAlign.End,
            )
        }
    }
}

@Composable
private fun StrapPhoto(strap: StrapCard) {
    val painter = rememberAsyncImagePainter(model = strap.image)
    val state by painter.state.collectAsState()

    Box(
        modifier = Modifier
            .size(48.dp)
            .background(MaterialTheme.colorScheme.surfaceContainerHigh),
    ) {
        if (state !is AsyncImagePainter.State.Error) {
            Image(
                painter = painter,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.size(48.dp),
            )
        }
    }
}

/** One log entry: date and kind on a line, the note beneath it. Newest first. */
@Composable
private fun LogBlock(entry: LogLine) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 5.dp),
    ) {
        val heading = listOfNotNull(entry.date, entry.kind)
        Text(
            text = heading.takeIf { it.isNotEmpty() }
                ?.joinToString(stringResource(R.string.screen_detail_separator))
                ?: stringResource(R.string.field_absent),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface,
        )
        entry.note?.let {
            Text(
                text = it,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

/**
 * One timing reading, as a plain line.
 *
 * The sparkline SPEC-ANDROID 5.6 describes is AM9's, and this milestone's brief
 * says so explicitly. A list of readings is still the data; the drawing is what
 * is deferred.
 */
@Composable
private fun TimingBlock(reading: TimingLine) {
    val parts = listOfNotNull(reading.date, reading.deviation, reading.position)
    Text(
        text = parts.takeIf { it.isNotEmpty() }
            ?.joinToString(stringResource(R.string.screen_detail_separator))
            ?: stringResource(R.string.field_absent),
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurface,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 3.dp),
    )
}
