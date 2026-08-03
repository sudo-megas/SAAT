package io.github.sudomegas.saat.ui.screens

import androidx.compose.foundation.Image
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil3.compose.AsyncImagePainter
import coil3.compose.rememberAsyncImagePainter
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.ui.CalendarDay
import io.github.sudomegas.saat.ui.CalendarViewModel
import io.github.sudomegas.saat.ui.DaySelection
import io.github.sudomegas.saat.ui.calendar.DAYS_IN_WEEK
import io.github.sudomegas.saat.ui.calendar.MonthLayout
import io.github.sudomegas.saat.ui.theme.slugColour
import java.time.LocalDate
import java.time.YearMonth

/**
 * The calendar — SPEC-ANDROID 5.5.
 *
 * THE PHOTOGRAPHS ARE THE INTERFACE, which is the whole brief for this screen:
 * everything around the grid stays quiet so a month of worn days reads as a
 * mosaic of watches rather than as a form. A filled day is its watch's primary
 * photograph, square-cropped, filling the cell; the day number sits over a scrim
 * in the corner so it stays legible on a light photograph without becoming a
 * label. An empty day is a muted number and nothing else.
 *
 * Today carries a hairline border in the one accent the palette has — identity,
 * not selection, and the same restraint the rest of the app keeps.
 */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun CalendarScreen(
    viewModel: CalendarViewModel,
    modifier: Modifier = Modifier,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val pickerWatches by viewModel.pickerWatches.collectAsStateWithLifecycle()
    val pickerQuery by viewModel.pickerQuery.collectAsStateWithLifecycle()

    Column(
        modifier = modifier
            .fillMaxSize()
            // Swipe to change month, which is what a phone expects of a
            // calendar; the header arrows do the same thing for anyone who
            // would rather tap. Threshold rather than velocity so a slow,
            // deliberate drag works as well as a flick.
            .pointerInput(state.month) {
                var travelled = 0f
                detectHorizontalDragGestures(
                    onDragEnd = {
                        if (travelled <= -SWIPE_THRESHOLD) viewModel.step(1)
                        if (travelled >= SWIPE_THRESHOLD) viewModel.step(-1)
                        travelled = 0f
                    },
                ) { _, amount -> travelled += amount }
            },
    ) {
        MonthHeader(
            month = state.month,
            onPrevious = { viewModel.step(-1) },
            onNext = { viewModel.step(1) },
        )
        WeekdayHeader()
        MonthGrid(
            layout = state.layout,
            days = state.days,
            selection = state.selection,
            onTap = viewModel::onDayTapped,
            onLongPress = viewModel::onDayLongPressed,
        )

        state.selection?.let { selection ->
            RangeBar(
                days = selection.dates.size,
                onPick = viewModel::pickForSelection,
                onCancel = viewModel::cancelSelection,
            )
        }

        if (state.isLoaded && state.days.values.none { it.slug != null }) {
            // SPEC-ANDROID 5.8: an empty month plus one muted line. Shown
            // whenever the MONTH is empty rather than only when the collection
            // is, because a new owner's first calendar month is empty either
            // way and the line is what tells them the grid is tappable at all.
            Text(
                text = stringResource(R.string.screen_calendar_empty),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 32.dp, vertical = 20.dp),
            )
        }
    }

    state.picking?.let { dates ->
        DayPicker(
            dates = dates,
            watches = pickerWatches,
            query = pickerQuery,
            // Only meaningful for a single day: a span can cross several
            // watches, and marking one of them as "the" current would be a
            // claim about the others.
            currentSlug = dates.singleOrNull()?.let { state.days[it]?.slug },
            onQueryChange = viewModel::setPickerQuery,
            onPick = viewModel::assign,
            onClear = viewModel::clearPicked,
            onDismiss = viewModel::dismissPicker,
        )
    }
}

/**
 * Range mode's own bar — the state has to be visible while it lasts.
 *
 * A long press with no visible consequence would read as a missed tap, and the
 * owner would have no way to tell the span had started other than by tapping
 * again and watching it grow.
 */
@Composable
private fun RangeBar(days: Int, onPick: () -> Unit, onCancel: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = pluralStringResource(R.plurals.screen_calendar_span, days, days),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Text(
                text = stringResource(R.string.screen_calendar_range_hint),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        TextButton(onClick = onCancel) { Text(text = stringResource(R.string.action_cancel)) }
        TextButton(onClick = onPick) { Text(text = stringResource(R.string.action_pick_watch)) }
    }
}

@Composable
private fun MonthHeader(month: YearMonth, onPrevious: () -> Unit, onNext: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 8.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        TextButton(onClick = onPrevious) {
            Text(text = stringResource(R.string.action_previous_month))
        }
        Text(
            text = stringResource(
                R.string.screen_calendar_month,
                stringResource(monthNameRes(month.monthValue)),
                month.year.toString(),
            ),
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurface,
        )
        TextButton(onClick = onNext) {
            Text(text = stringResource(R.string.action_next_month))
        }
    }
}

/**
 * Monday first — SPEC-ANDROID 5.5, and not the platform default.
 *
 * From resources rather than from `DayOfWeek.getDisplayName`, which needs a
 * `Locale`: the default is the system locale hard rule 7 forbids reading, and
 * `Locale.ENGLISH` would survive AM11's Turkish sweep untranslated.
 */
@Composable
private fun WeekdayHeader() {
    Row(modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp)) {
        WEEKDAY_LABELS.forEach { label ->
            Text(
                text = stringResource(label),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                modifier = Modifier.weight(1f),
            )
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun MonthGrid(
    layout: MonthLayout,
    days: Map<LocalDate, CalendarDay>,
    selection: DaySelection?,
    onTap: (LocalDate) -> Unit,
    onLongPress: (LocalDate) -> Unit,
) {
    // A plain Column of Rows rather than a LazyVerticalGrid: a month is at most
    // six rows and every one of them is on screen, so laziness would buy
    // nothing and would take away the even cell sizing that comes free here.
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 8.dp),
    ) {
        layout.cells.chunked(DAYS_IN_WEEK).forEach { week ->
            Row(modifier = Modifier.fillMaxWidth()) {
                week.forEach { date ->
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .aspectRatio(1f)
                            .padding(2.dp),
                    ) {
                        // Looked up rather than required. The state's initial
                        // value has a layout and an empty map — the flow has
                        // not emitted yet — and there is a frame in which the
                        // grid is composed against it. A missing entry is just
                        // an empty day, which is what it would be anyway.
                        if (date != null) {
                            DayCell(
                                day = days[date] ?: emptyDay(date),
                                isSelected = selection?.contains(date) == true,
                                onTap = { onTap(date) },
                                onLongPress = { onLongPress(date) },
                            )
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun DayCell(
    day: CalendarDay,
    isSelected: Boolean,
    onTap: () -> Unit,
    onLongPress: () -> Unit,
) {
    val shape = MaterialTheme.shapes.extraSmall

    Box(
        modifier = Modifier
            .fillMaxSize()
            .clip(shape)
            .background(MaterialTheme.colorScheme.surfaceContainer)
            .then(
                // Selection wins over today's marker while a span is being
                // chosen: for those few seconds the question on screen is
                // "which days", and today is not one of the answers.
                when {
                    isSelected ->
                        Modifier.border(SELECTION_BORDER, MaterialTheme.colorScheme.tertiary, shape)
                    day.isToday ->
                        Modifier.border(HAIRLINE_TODAY, MaterialTheme.colorScheme.primary, shape)
                    else -> Modifier
                }
            )
            .combinedClickable(onClick = onTap, onLongClick = onLongPress),
    ) {
        // A watch with no photograph still has to be visibly a worn day. Its
        // identity hue fills the cell instead — the same colour the year view
        // gives it, so the two screens agree about which watch a cell is
        // about. Without this, a photo-less collection's calendar is
        // indistinguishable from an empty one, which is how this was found:
        // the demo pair carries no photographs by design.
        if (day.slug != null && day.image == null) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(slugColour(day.slug, isSystemInDarkTheme()))
            )
        }
        if (day.image != null) DayPhoto(day)

        Text(
            text = day.date.dayOfMonth.toString(),
            style = MaterialTheme.typography.labelSmall,
            // White over a scrim once the cell is filled, whatever fills it:
            // the hue and the photograph are both arbitrary backgrounds and
            // neither can be assumed to suit the theme's onSurface.
            color = if (day.slug != null) Color.White else MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier
                .align(Alignment.TopStart)
                .then(
                    // A scrim only where there is a photograph under it. On an
                    // empty cell it would be a box around a number for no
                    // reason.
                    if (day.slug != null) {
                        Modifier.background(SCRIM, MaterialTheme.shapes.extraSmall)
                    } else {
                        Modifier
                    }
                )
                .padding(horizontal = 3.dp),
        )
    }
}

@Composable
private fun DayPhoto(day: CalendarDay) {
    val painter = rememberAsyncImagePainter(model = day.image)
    val state by painter.state.collectAsState()

    if (state !is AsyncImagePainter.State.Error) {
        Image(
            painter = painter,
            contentDescription = null,
            // Square-cropped and filling the cell — SPEC-ANDROID 5.5. A photo
            // composed at 4:5 for the grid still reads as its watch here.
            contentScale = ContentScale.Crop,
            modifier = Modifier.fillMaxSize(),
        )
    }
}

/** A day with nothing on it, for the frame before the collection has loaded. */
private fun emptyDay(date: LocalDate) =
    CalendarDay(date = date, slug = null, image = null, isToday = false)

/** Enough of a drag to mean it, and short enough not to need a flick. */
private const val SWIPE_THRESHOLD = 120f

private val HAIRLINE_TODAY = 1.5.dp

/** Heavier than today's hairline, because a selection is a thing in progress. */
private val SELECTION_BORDER = 3.dp

/** Just enough to keep a day number legible over a pale photograph. */
private val SCRIM = Color(0x99000000)

private val WEEKDAY_LABELS = intArrayOf(
    R.string.screen_calendar_weekday_mon,
    R.string.screen_calendar_weekday_tue,
    R.string.screen_calendar_weekday_wed,
    R.string.screen_calendar_weekday_thu,
    R.string.screen_calendar_weekday_fri,
    R.string.screen_calendar_weekday_sat,
    R.string.screen_calendar_weekday_sun,
)

/** The month names AM4's twelve-month strip already owns, reused here. */
internal fun monthNameRes(monthValue: Int): Int = when (monthValue) {
    1 -> R.string.screen_month_short_jan
    2 -> R.string.screen_month_short_feb
    3 -> R.string.screen_month_short_mar
    4 -> R.string.screen_month_short_apr
    5 -> R.string.screen_month_short_may
    6 -> R.string.screen_month_short_jun
    7 -> R.string.screen_month_short_jul
    8 -> R.string.screen_month_short_aug
    9 -> R.string.screen_month_short_sep
    10 -> R.string.screen_month_short_oct
    11 -> R.string.screen_month_short_nov
    else -> R.string.screen_month_short_dec
}
