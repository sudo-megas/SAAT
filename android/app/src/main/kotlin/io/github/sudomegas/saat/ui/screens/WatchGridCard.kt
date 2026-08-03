package io.github.sudomegas.saat.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImagePainter
import coil3.compose.rememberAsyncImagePainter
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.ui.WatchCard
import io.github.sudomegas.saat.ui.formatMeasurement
import io.github.sudomegas.saat.ui.detail.SpecValue
import io.github.sudomegas.saat.ui.form.EnumChoice
import io.github.sudomegas.saat.ui.form.MOVEMENT_KINDS
import io.github.sudomegas.saat.ui.form.STYLES
import io.github.sudomegas.saat.ui.form.labelFor

/**
 * One watch in the grid.
 *
 * EVERY CARD IS THE SAME HEIGHT, and that is a structural property rather than
 * something to eyeball. `LazyVerticalGrid` sizes a row to its tallest item and
 * does not stretch the others — `fillMaxHeight()` is a no-op there, because
 * items are measured with unbounded height. So the height is made deterministic
 * instead: a fixed 4:5 image box, and three text slots whose `minLines` equals
 * their `maxLines`. A one-word model and a five-word model then produce
 * identical cards, and they stay identical at any system font scale because
 * every card scales together.
 *
 * The colours are not the Material defaults, deliberately. This theme maps
 * `surfaceContainerLow` — what M3's `Card` reaches for — to `plate`, the same
 * colour as the grid background, and neutralises `surfaceTint` so elevation
 * adds no tint either. A default `Card` would therefore be invisible. The
 * hairline border carries the structure, which is the desktop's restraint
 * (SPEC-ANDROID 6: "hairline dividers, no decoration beyond Material defaults").
 */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun WatchGridCard(
    card: WatchCard,
    onOpen: (String) -> Unit,
    modifier: Modifier = Modifier,
    /** AM9: long-press enters selection mode, which Compare is reached from. */
    isSelected: Boolean = false,
    selectionMode: Boolean = false,
    onToggleSelect: (String) -> Unit = {},
) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainer,
        ),
        // The selected card is marked by its BORDER rather than by a tick
        // floating over the photograph. SPEC-ANDROID 6 asks for "no decoration
        // beyond Material defaults", and the hairline is already the thing that
        // carries structure on this screen — making it thick and accent-coloured
        // says "picked" without covering the watch, which is what the owner is
        // looking at while deciding.
        border = if (isSelected) {
            BorderStroke(SELECTED_BORDER, MaterialTheme.colorScheme.primary)
        } else {
            BorderStroke(Dp.Hairline, MaterialTheme.colorScheme.outlineVariant)
        },
        // combinedClickable rather than clickable, for the long press. Once a
        // selection exists a plain tap TOGGLES instead of opening: a tap that
        // navigated away mid-selection would throw away the other pick, and
        // every list on the platform behaves this way.
        modifier = modifier
            .fillMaxWidth()
            .combinedClickable(
                onClick = {
                    if (selectionMode) onToggleSelect(card.slug) else onOpen(card.slug)
                },
                onLongClick = { onToggleSelect(card.slug) },
            )
            .semantics {
                role = if (selectionMode) Role.Checkbox else Role.Button
                // `isSelected`, not `selected`: inside this receiver scope the
                // bare name would be ambiguous with the semantics property it
                // is being assigned to.
                selected = isSelected
            },
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                // The desktop's portrait crop. 4:5 is width ÷ height.
                .aspectRatio(4f / 5f),
        ) {
            CardImage(card)
            MaintenanceDot(card)
        }

        Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp)) {
            Text(
                text = card.brand,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                minLines = 1,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = card.model,
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.onSurface,
                minLines = 2,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = metadataLine(card),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                minLines = 1,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

/**
 * The photograph, falling back to the placeholder tile.
 *
 * `contentDescription` is null on purpose: the card's own brand and model lines
 * already name the watch to a screen reader, and a description repeating them
 * would be read twice.
 */
@Composable
private fun CardImage(card: WatchCard) {
    if (card.image == null) {
        PlaceholderTile(card)
        return
    }

    val painter = rememberAsyncImagePainter(model = card.image)
    val state by painter.state.collectAsState()

    // A filename in `images` with no file behind it is a real possibility in a
    // hand-edited collection. Rather than stat every card on the main thread,
    // let the decode fail and show the same tile a photo-less watch gets.
    if (state is AsyncImagePainter.State.Error) {
        PlaceholderTile(card)
    } else {
        Image(
            painter = painter,
            contentDescription = null,
            contentScale = ContentScale.Crop,
            modifier = Modifier.fillMaxSize(),
        )
    }
}

/**
 * What a watch with no photograph shows: its two most identifying measurements,
 * set in the middle. Informative rather than an empty grey box.
 *
 * Both measurements absent is a legitimate outcome, not a degenerate one — a
 * watch entered with only brand and model renders two em-dashes and still looks
 * deliberate. That is precisely the case the quartz demo fixture exercises.
 */
@Composable
private fun PlaceholderTile(card: WatchCard) {
    val absent = stringResource(R.string.field_absent)
    val diameter = card.diameterMm
        ?.let { stringResource(R.string.screen_grid_placeholder_diameter, formatMeasurement(it)) }
        ?: absent
    val lugs = card.lugWidthMm
        ?.let { stringResource(R.string.screen_grid_placeholder_lugs, it.toString()) }
        ?: absent

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.surfaceContainerHigh)
            .padding(12.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = diameter,
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        Text(
            text = lugs,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
    }
}

/**
 * The small accent dot a watch due for service or a battery carries —
 * SPEC-ANDROID 5.2, AM9b.
 *
 * A DOT, and nothing else. No badge, no count, no colour-coded severity: the
 * card's job is to make the owner open the page, and the page says what is due
 * and when. Overdue and due-soon look the same here on purpose — a grid that
 * graded its warnings would be a grid that nags, which AM9's brief forbids by
 * name.
 *
 * Over the photograph's top-right corner, with a `contentDescription` because
 * this is the one thing on the card a screen reader could not otherwise learn:
 * the brand and model lines below it say nothing about a service being due.
 */
@Composable
private fun BoxScope.MaintenanceDot(card: WatchCard) {
    if (!card.needsAttention) return
    val label = stringResource(R.string.screen_detail_maintenance_dot)

    Box(
        modifier = Modifier
            .align(Alignment.TopEnd)
            .padding(8.dp)
            .size(DOT_SIZE)
            .background(MaterialTheme.colorScheme.primary, CircleShape)
            .semantics { contentDescription = label },
    )
}

private val DOT_SIZE = 10.dp

/** Thick enough to read as a state at arm's length, not as a rendering artefact. */
private val SELECTED_BORDER = 2.dp

/**
 * `style · movement kind`, whichever of the two the owner recorded.
 *
 * No em-dash when both are missing. The em-dash convention belongs to LABELLED
 * fields, where the label says what is absent; a lone dash on an unlabelled card
 * line communicates nothing. The line still occupies its row because of
 * `minLines`, so the card height does not move.
 */
@Composable
private fun metadataLine(card: WatchCard): String {
    val style = enumLabel(card.style, STYLES)
    val kind = enumLabel(card.movementKind, MOVEMENT_KINDS)
    return when {
        style != null && kind != null ->
            stringResource(R.string.screen_grid_card_metadata, style, kind)
        style != null -> style
        kind != null -> kind
        else -> ""
    }
}

/**
 * A schema `enum*` value as the owner reads it, or as they typed it.
 *
 * The card carries these two as bare strings — it never had a [SpecValue] to
 * hand — so the label is looked up here instead. Without it the grid was the
 * one screen still saying `Field · Automatic` under a Turkish interface, while
 * the detail page above it said `Saha` and `Otomatik`.
 *
 * Null label means the schema does not know this value, and a word the owner
 * invented is shown exactly as they wrote it — the same rule
 * [SpecValue.EnumValue] follows everywhere else.
 */
@Composable
private fun enumLabel(value: String?, choices: List<EnumChoice>): String? {
    val trimmed = value?.takeIf { it.isNotBlank() } ?: return null
    return labelFor(trimmed, choices)?.let { stringResource(it) } ?: trimmed
}
