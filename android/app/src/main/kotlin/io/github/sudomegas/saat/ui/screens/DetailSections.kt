package io.github.sudomegas.saat.ui.screens

import androidx.annotation.StringRes
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
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
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImagePainter
import coil3.compose.rememberAsyncImagePainter
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.ui.detail.CompatibleStrapCard
import io.github.sudomegas.saat.ui.detail.DetailPage
import io.github.sudomegas.saat.ui.detail.LogLine
import io.github.sudomegas.saat.ui.detail.Sparkline
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
internal fun LazyListScope.detailSections(
    page: DetailPage,
    /** AM9c. Empty for most watches, and the section vanishes with it. */
    compatibleStraps: List<CompatibleStrapCard>,
    onOpenWatch: (String) -> Unit,
) {
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

    // Straight after the watch's own straps, which is where the question comes
    // up: having just read what is on it, "what else would fit" is the next
    // thought. Hidden entirely when nothing matches — SPEC-ANDROID 5.6.
    if (compatibleStraps.isNotEmpty()) {
        item(key = "strap-compat-header") {
            SectionHeader(R.string.screen_detail_group_strap_compat)
        }
        itemsIndexed(
            compatibleStraps,
            // Owner slug AND position: one watch can legitimately contribute two
            // straps of the same width, and a slug-only key would collide.
            key = { index, card -> "compat-${card.ownerSlug}-$index" },
        ) { _, card ->
            CompatibleStrapBlock(card = card, onOpenWatch = onOpenWatch)
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
        // Above the readings, not below: the chart is the summary and the list
        // is the evidence. Absent entirely under three plottable readings —
        // `timingSparkline` is null then and this item is never emitted.
        page.timingSparkline?.let { chart ->
            item(key = "timing-sparkline") { TimingSparkline(chart) }
        }
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
            // `: List<String>` is load-bearing, here and at every other join in
            // this file. `material` is a SpecValue and `colour` a String, so
            // without it `listOfNotNull` infers List<Any> and `joinToString`
            // reaches for SpecValue's data-class toString — which is how
            // `EnumValue(value=Steel, labelRes=null)` came to be printed on the
            // detail page of a shipping build. Naming the type makes that a
            // compile error rather than something only a phone can notice.
            val description: List<String> = listOfNotNull(
                strap.material?.let { specValueText(it) },
                strap.colour,
            )
            Text(
                text = description.takeIf { it.isNotEmpty() }
                    ?.joinToString(stringResource(R.string.screen_detail_separator))
                    ?: stringResource(R.string.field_absent),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
            val detail: List<String> = listOfNotNull(
                strap.widthMm?.let { stringResource(R.string.field_value_mm, it.toString()) },
                strap.clasp?.let { specValueText(it) },
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

/**
 * A strap belonging to another watch — AM9c.
 *
 * The same layout as the watch's own straps, plus the line naming whose it is
 * and a tap that goes there. Tappable BECAUSE it names another watch: the row
 * is about a thing that lives somewhere else, and being able to go and look at
 * that watch is the only action it could sensibly offer.
 *
 * The fitted mark is not drawn here even when the strap is fitted on its own
 * watch. On this page "fitted" means "on the watch you are looking at", and
 * repeating the flag from a different watch's context would be the one piece of
 * genuinely misleading information the section could carry.
 */
@Composable
private fun CompatibleStrapBlock(card: CompatibleStrapCard, onOpenWatch: (String) -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onOpenWatch(card.ownerSlug) }
            .semantics { role = Role.Button }
            .padding(horizontal = 16.dp, vertical = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (card.strap.image != null) {
            StrapPhoto(card.strap)
        }
        Column(modifier = Modifier.weight(1f)) {
            val description: List<String> = listOfNotNull(
                card.strap.material?.let { specValueText(it) },
                card.strap.colour,
            )
            Text(
                text = description.takeIf { it.isNotEmpty() }
                    ?.joinToString(stringResource(R.string.screen_detail_separator))
                    ?: stringResource(R.string.field_absent),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Text(
                text = stringResource(
                    R.string.screen_detail_strap_compat_owner,
                    card.ownerBrand,
                    card.ownerModel,
                ),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
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
        val heading: List<String> = listOfNotNull(
            entry.date,
            entry.kind?.let { specValueText(it) },
        )
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
 * Deviation over time — AM9b, drawn with Compose primitives.
 *
 * NO CHARTING LIBRARY, which AM9's brief forbids and which would in any case be
 * a dependency bought for one polyline and one straight rule. `Canvas` and a
 * `Path` are the whole implementation.
 *
 * Every decision about WHAT to draw was taken in [sparkline] and tested there.
 * This function knows only how to turn a unit square into pixels: the geometry
 * arrives normalised, and the vertical padding keeps the line's peaks off the
 * edge without changing the shape.
 *
 * The zero rule is drawn in the hairline colour that carries every other
 * division on this page, and the trend in the accent — so the reading is "how
 * far from the rule, and which side", in any palette dynamic colour produces.
 */
@Composable
private fun TimingSparkline(chart: Sparkline) {
    val rule = MaterialTheme.colorScheme.outlineVariant
    val trend = MaterialTheme.colorScheme.primary
    val label = stringResource(R.string.screen_detail_timing_chart)

    Canvas(
        modifier = Modifier
            .fillMaxWidth()
            .height(SPARKLINE_HEIGHT)
            .padding(horizontal = 16.dp, vertical = 6.dp)
            // The chart is not readable by a screen reader, so it says what it
            // is rather than being an unlabelled rectangle. The readings
            // themselves follow as text immediately beneath.
            .semantics { contentDescription = label },
    ) {
        val usableHeight = size.height - 2 * SPARKLINE_PADDING_PX
        fun y(normalised: Float) = SPARKLINE_PADDING_PX + normalised * usableHeight

        drawLine(
            color = rule,
            start = Offset(0f, y(chart.zeroY)),
            end = Offset(size.width, y(chart.zeroY)),
            strokeWidth = 1f,
        )

        // One Path rather than a drawLine per segment, so the joins between
        // segments are mitred instead of showing a notch at every reading.
        val path = Path()
        chart.points.forEachIndexed { index, point ->
            val x = point.x * size.width
            val py = y(point.y)
            if (index == 0) path.moveTo(x, py) else path.lineTo(x, py)
        }
        drawPath(
            path = path,
            color = trend,
            style = Stroke(
                width = SPARKLINE_STROKE_PX,
                cap = StrokeCap.Round,
                join = StrokeJoin.Round,
            ),
        )
    }
}

/** The desktop's `SPARKLINE_HEIGHT`, in dp rather than pixels. */
private val SPARKLINE_HEIGHT = 48.dp

/** The desktop's `pad = 4`, keeping the extremes off the top and bottom edges. */
private const val SPARKLINE_PADDING_PX = 4f

private const val SPARKLINE_STROKE_PX = 3f

/**
 * One timing reading, as a plain line.
 *
 * The readings stay even once the sparkline is drawn: the chart shows the shape
 * and this shows the positions and dates, which the chart deliberately does not
 * encode.
 */
@Composable
private fun TimingBlock(reading: TimingLine) {
    val parts: List<String> = listOfNotNull(
        reading.date,
        reading.deviation,
        reading.position?.let { specValueText(it) },
    )
    Text(
        text = parts.takeIf { it.isNotEmpty() }
            ?.joinToString(stringResource(R.string.screen_detail_separator))
            ?: stringResource(R.string.field_absent),
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurface,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 3.dp),
    )
}
