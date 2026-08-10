package io.github.sudomegas.saat.ui.screens

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImagePainter
import coil3.compose.rememberAsyncImagePainter
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.ui.PickerWatch
import io.github.sudomegas.saat.ui.formatDate
import java.io.File
import java.time.LocalDate

/**
 * The day picker — SPEC-ANDROID 5.5.
 *
 * ONE SHEET FOR EVERY CASE. Tapping an empty day, tapping a filled day and
 * finishing a long-press range all open this, because they are the same
 * question: which watch was on the wrist. A filled day arrives with its current
 * watch marked and a Clear action; an empty one simply has neither marked nor
 * anything to clear.
 *
 * Picking is one tap and there is no confirm step. The one-watch-per-day rule
 * may move the day off another watch, and it does so SILENTLY — the brief
 * forbids prompting about it, and the desktop does not either. A calendar you
 * have to argue with is a calendar that never gets a year of backlog entered.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DayPicker(
    dates: List<LocalDate>,
    watches: List<PickerWatch>,
    query: String,
    /** The watch currently on the day, when exactly one day is being picked. */
    currentSlug: String?,
    onQueryChange: (String) -> Unit,
    onPick: (String) -> Unit,
    onClear: () -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
    ) {
        Column(modifier = Modifier.fillMaxWidth().padding(bottom = 24.dp)) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = title(dates),
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                // Offered whenever anything in the span is filled — for a range
                // that is how you undo a mis-dragged week without picking a
                // watch you did not wear.
                if (currentSlug != null || dates.size > 1) {
                    TextButton(onClick = onClear) {
                        Text(text = stringResource(R.string.action_clear_day))
                    }
                }
            }

            OutlinedTextField(
                value = query,
                onValueChange = onQueryChange,
                placeholder = { Text(text = stringResource(R.string.action_search)) },
                singleLine = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
            )

            LazyColumn(
                contentPadding = PaddingValues(bottom = 8.dp),
                // Bounded so the sheet cannot grow past the screen on a large
                // collection; the list scrolls inside it instead.
                modifier = Modifier.heightIn(max = 420.dp),
            ) {
                items(items = watches, key = { it.slug }) { watch ->
                    PickerRow(
                        watch = watch,
                        isCurrent = watch.slug == currentSlug,
                        onClick = { onPick(watch.slug) },
                    )
                }
            }
        }
    }
}

@Composable
private fun PickerRow(watch: PickerWatch, isCurrent: Boolean, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        PickerThumbnail(watch.image)
        Column(modifier = Modifier.weight(1f).padding(start = 12.dp)) {
            Text(
                text = watch.brand,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = watch.model,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        if (isCurrent) {
            Text(
                text = stringResource(R.string.screen_calendar_current),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.primary,
            )
        }
    }
}

/** [size] defaults to the picker row's own size; PickForMeSheet.kt asks for a larger one for its reveal. */
@Composable
internal fun PickerThumbnail(file: File?, size: androidx.compose.ui.unit.Dp = 44.dp) {
    val painter = rememberAsyncImagePainter(model = file)
    val state by painter.state.collectAsState()

    Box(
        modifier = Modifier
            .size(size)
            .background(MaterialTheme.colorScheme.surfaceContainerHigh)
            .border(androidx.compose.ui.unit.Dp.Hairline, MaterialTheme.colorScheme.outlineVariant),
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

/** One date reads as itself; a span reads as how long it is. */
@Composable
private fun title(dates: List<LocalDate>): String =
    if (dates.size == 1) {
        formatDate(dates.single())
    } else {
        pluralStringResource(R.plurals.screen_calendar_span, dates.size, dates.size)
    }
