package io.github.sudomegas.saat.ui.screens

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil3.compose.AsyncImagePainter
import coil3.compose.rememberAsyncImagePainter
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.ui.DetailViewModel
import io.github.sudomegas.saat.ui.WearMessage
import io.github.sudomegas.saat.ui.detail.DetailPage
import io.github.sudomegas.saat.ui.detail.SpecValue
import io.github.sudomegas.saat.ui.detail.WearStats
import io.github.sudomegas.saat.ui.formatMeasurement
import java.io.File

/**
 * One watch, in full — SPEC-ANDROID 5.6.
 *
 * A full screen pushed above the tabs, so the bottom bar is gone while it is
 * open and the system back gesture means the same thing the top bar's arrow
 * does.
 *
 * A `LazyColumn` rather than a scrolling `Column`, for a reason that only shows
 * on a real collection: a watch with a long log and a dozen timing readings
 * composes every row of both at once in a plain column, including the ones
 * nobody scrolls to, and each strap card holds a decoded photograph.
 *
 * Everything rendered here was decided by [io.github.sudomegas.saat.ui.detail
 * .detailPage] before this composable ran. Which groups exist, which rows carry
 * an em-dash and what order the log is in are properties of that function and
 * are tested as plain JUnit; this file's job is to put them on screen.
 */
@Composable
fun DetailScreen(
    viewModel: DetailViewModel,
    snackbarHostState: SnackbarHostState,
    onBack: () -> Unit,
    onEdit: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val message by viewModel.message.collectAsStateWithLifecycle()
    val page = state.page

    // Resolved in composition, not inside the effect: `stringResource` needs a
    // composable scope, and reaching for a Context from the coroutine instead is
    // the habit that leaves an untranslatable literal behind — which
    // StringsConventionTest's regex cannot see, because it only inspects
    // Text/Button/Label call sites.
    val text = when (val current = message) {
        null -> null
        WearMessage.Recorded -> stringResource(R.string.screen_detail_wear_recorded)
        WearMessage.AlreadyRecorded -> stringResource(R.string.screen_detail_wear_already)
        is WearMessage.Moved ->
            stringResource(R.string.screen_detail_wear_moved, current.from)
    }

    LaunchedEffect(text) {
        text?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearMessage()
        }
    }

    DetailScaffold(
        title = page?.let { "${it.brand} ${it.model}" }.orEmpty(),
        onBack = onBack,
        // No Edit action on a watch that did not load: the form would open
        // blank and saving it would overwrite a file nobody could read.
        onEdit = onEdit.takeIf { page != null },
        modifier = modifier,
    ) { innerPadding ->
        val error = state.loadError
        when {
            page != null -> DetailBody(
                page = page,
                wear = state.wear,
                onWoreToday = viewModel::woreToday,
                contentPadding = innerPadding,
            )

            // Hard rule 6: the parse error reaches the screen with its message
            // intact, rather than this page going blank for a watch whose folder
            // is plainly there.
            error != null -> DetailNotice(
                text = stringResource(R.string.screen_detail_unreadable, state.slug, error),
                modifier = Modifier.padding(innerPadding),
            )

            state.isMissing -> DetailNotice(
                text = stringResource(R.string.screen_detail_missing),
                modifier = Modifier.padding(innerPadding),
            )

            // The collection has not finished loading. Blank rather than a
            // spinner, the same choice the grid makes: "we have not looked yet"
            // is not news.
            else -> Unit
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DetailScaffold(
    title: String,
    onBack: () -> Unit,
    onEdit: (() -> Unit)?,
    modifier: Modifier = Modifier,
    content: @Composable (PaddingValues) -> Unit,
) {
    val backLabel = stringResource(R.string.action_back)

    Scaffold(
        // The shell's Scaffold already consumed the system bars — MainActivity
        // calls enableEdgeToEdge — so a nested default would count them twice.
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            TopAppBar(
                title = {
                    Text(text = title, maxLines = 1, overflow = TextOverflow.Ellipsis)
                },
                navigationIcon = {
                    IconButton(
                        onClick = onBack,
                        modifier = Modifier.semantics { contentDescription = backLabel },
                    ) {
                        BackChevron(tint = MaterialTheme.colorScheme.onSurface)
                    }
                },
                actions = {
                    // SPEC-ANDROID 5.6 puts Edit and Delete at the bottom of
                    // the page. On a phone the bottom of a long scroll is a
                    // place you have to travel to, and the top bar is where
                    // every other screen's actions already are; Delete stays
                    // at the bottom in AM5c, where its distance is a feature.
                    onEdit?.let {
                        TextButton(onClick = it) {
                            Text(text = stringResource(R.string.action_edit_watch))
                        }
                    }
                },
            )
        },
        modifier = modifier,
        content = content,
    )
}

/**
 * The back affordance, drawn rather than imported.
 *
 * `androidx.compose.material:material-icons-*` is not on SPEC-ANDROID 2.1's
 * approved list, and Material 3 1.4 no longer brings it in transitively — so an
 * arrow would cost a new dependency under hard rule 5 for the sake of one
 * glyph. Six lines of `Canvas` is the cheaper answer, and it is the answer the
 * navigation bar already took when it shipped with no icons at all.
 *
 * Mirrored under RTL, because a back arrow pointing the wrong way is not a
 * decoration, it is a wrong instruction. Turkish reads left to right, so this
 * costs nothing today and is right on the day it does not.
 *
 * Internal rather than private since AM5: the form is the second full screen
 * pushed above the tabs and carries the same affordance, and two hand-drawn
 * chevrons would eventually differ by a pixel.
 */
@Composable
internal fun BackChevron(tint: Color, modifier: Modifier = Modifier) {
    Canvas(modifier.size(24.dp)) {
        val mirrored = layoutDirection == LayoutDirection.Rtl
        fun x(fraction: Float) = size.width * (if (mirrored) 1f - fraction else fraction)

        val chevron = Path().apply {
            moveTo(x(0.62f), size.height * 0.22f)
            lineTo(x(0.36f), size.height * 0.50f)
            lineTo(x(0.62f), size.height * 0.78f)
        }
        drawPath(
            path = chevron,
            color = tint,
            style = Stroke(
                width = 2.dp.toPx(),
                cap = StrokeCap.Round,
                join = StrokeJoin.Round,
            ),
        )
    }
}

@Composable
private fun DetailNotice(text: String, modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .fillMaxSize()
            .padding(32.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun DetailBody(
    page: DetailPage,
    wear: WearStats?,
    onWoreToday: () -> Unit,
    contentPadding: PaddingValues,
) {
    LazyColumn(
        contentPadding = contentPadding,
        modifier = Modifier.fillMaxSize(),
    ) {
        item(key = "gallery") { Gallery(page) }
        item(key = "header") { DetailHeader(page) }

        // Before the spec groups, which is the order SPEC-ANDROID 5.6 lists:
        // the wear line and the button come first, and the specs follow. A
        // watch's daily use is what the owner opens this page for; its lug
        // width is what they come back to check.
        item(key = "wear") { WearSection(stats = wear, onWoreToday = onWoreToday) }

        detailSections(page)

        // The page ends where the content does. A trailing spacer keeps the
        // last line clear of the gesture bar on a phone that draws one.
        item(key = "tail") { Box(Modifier.height(24.dp)) }
    }
}

/**
 * Large primary image, thumbnail strip beneath, tap a thumb to view it large.
 *
 * READ-ONLY, and that is a decision rather than an omission: choosing which
 * photograph is primary is an edit, and edits belong to AM5's form. Tapping a
 * thumbnail changes what this screen shows and nothing on disk.
 */
@Composable
private fun Gallery(page: DetailPage) {
    // Survives rotation, and is re-clamped on every composition rather than
    // trusted: the collection is shared and live, so an edit made elsewhere can
    // shorten this list underneath a saved index.
    var shown by rememberSaveable(page.slug) { mutableIntStateOf(0) }
    val index = shown.coerceIn(0, (page.images.size - 1).coerceAtLeast(0))
    val current = page.images.getOrNull(index)

    Column {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .then(
                    if (current != null) {
                        // The desktop's portrait crop, the same box the grid
                        // card uses, so a photograph composed for one is
                        // composed for both.
                        Modifier.aspectRatio(4f / 5f)
                    } else {
                        // A watch with no photograph gets a SHORT tile, not the
                        // full crop. Measured on the phone: a 4:5 box holding
                        // two lines of text takes three fifths of the first
                        // screen and pushes the brand, the model and every spec
                        // below the fold — so the page opens on a large empty
                        // rectangle. The grid keeps 4:5 for its tile because a
                        // mosaic has to stay even; a page does not.
                        Modifier.height(PHOTOLESS_TILE_HEIGHT)
                    },
                )
                .background(MaterialTheme.colorScheme.surfaceContainerHigh),
        ) {
            PrimaryImage(file = current, page = page)
        }

        if (page.images.size > 1) {
            LazyRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                itemsIndexed(page.images) { position, file ->
                    Thumbnail(
                        file = file,
                        selected = position == index,
                        onClick = { shown = position },
                    )
                }
            }
        }
    }
}

private val PHOTOLESS_TILE_HEIGHT = 160.dp

/**
 * `ContentScale.Fit`, not `Crop` — the opposite of the grid card, on purpose.
 *
 * A card is a tile in a mosaic and cropping keeps the mosaic even. This is the
 * one place the owner comes to LOOK at the watch, and cutting the lugs off a
 * photograph they framed themselves is not a thing a detail page should do. The
 * desktop makes the same split: `fit_pixmap` for the primary, `cropped_pixmap`
 * for the thumbnails.
 */
@Composable
private fun PrimaryImage(file: File?, page: DetailPage) {
    if (file == null) {
        PhotoPlaceholder(page)
        return
    }

    val painter = rememberAsyncImagePainter(model = file)
    val state by painter.state.collectAsState()

    // A filename in `images` with no file behind it is a real possibility in a
    // hand-edited collection. Rather than stat the file on the main thread, let
    // the decode fail and fall back to the tile a photo-less watch gets.
    if (state is AsyncImagePainter.State.Error) {
        PhotoPlaceholder(page)
    } else {
        Image(
            painter = painter,
            contentDescription = null,
            contentScale = ContentScale.Fit,
            modifier = Modifier.fillMaxSize(),
        )
    }
}

@Composable
private fun Thumbnail(file: File, selected: Boolean, onClick: () -> Unit) {
    val painter = rememberAsyncImagePainter(model = file)
    val state by painter.state.collectAsState()

    Box(
        modifier = Modifier
            .size(64.dp)
            .background(MaterialTheme.colorScheme.surfaceContainerHigh)
            // The shown thumb is marked with a hairline, not a scrim or a scale
            // — SPEC-ANDROID 6, "no decoration beyond Material defaults".
            .border(
                width = if (selected) 2.dp else Dp.Hairline,
                color = if (selected) {
                    MaterialTheme.colorScheme.primary
                } else {
                    MaterialTheme.colorScheme.outlineVariant
                },
            )
            .clickable(onClick = onClick),
    ) {
        if (state !is AsyncImagePainter.State.Error) {
            Image(
                painter = painter,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        }
    }
}

/**
 * What a watch with no photograph shows on its own page: the same two
 * measurements the grid's tile carries, at the size this screen has room for.
 */
@Composable
private fun PhotoPlaceholder(page: DetailPage) {
    val absent = stringResource(R.string.field_absent)
    val diameter = page.diameterMm
        ?.let { stringResource(R.string.field_value_mm, formatMeasurement(it)) }
        ?: absent
    val lugs = page.lugWidthMm
        ?.let { stringResource(R.string.screen_grid_placeholder_lugs, it.toString()) }
        ?: absent

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = diameter,
            style = MaterialTheme.typography.headlineSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        Text(
            text = lugs,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
    }
}

/**
 * Brand as overline, model as title, then the identity fields no spec group
 * covers — reference, style, group, status, storage, rating, tags, serial.
 *
 * One line of text rather than a block of labelled rows, which is what the
 * desktop does too: a page that opened with nine rows of filing before reaching
 * the movement would bury the watch under its own paperwork.
 */
@Composable
private fun DetailHeader(page: DetailPage) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(
            text = page.brand,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = page.nickname
                ?.let { stringResource(R.string.screen_detail_title_nickname, page.model, it) }
                ?: page.model,
            style = MaterialTheme.typography.headlineSmall,
            color = MaterialTheme.colorScheme.onSurface,
        )

        val separator = stringResource(R.string.screen_detail_separator)
        val meta = page.meta.map { specValueText(it) }
        if (meta.isNotEmpty()) {
            Text(
                text = meta.joinToString(separator),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        if (page.tags.isNotEmpty()) {
            Text(
                text = stringResource(R.string.screen_detail_tags, page.tags.joinToString(", ")),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        page.serial?.let {
            Text(
                text = stringResource(R.string.screen_detail_serial, it),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

/**
 * A value, resolved. [SpecValue.Plain] is the owner's own words and never
 * passes through the resource table; a null is the muted em-dash SPEC-ANDROID 4
 * asks for.
 */
@Composable
internal fun specValueText(value: SpecValue?): String = when (value) {
    null -> stringResource(R.string.field_absent)
    is SpecValue.Plain -> value.text
    is SpecValue.Resource ->
        if (value.args.isEmpty()) {
            stringResource(value.templateRes)
        } else {
            stringResource(value.templateRes, *value.args.toTypedArray())
        }
}
