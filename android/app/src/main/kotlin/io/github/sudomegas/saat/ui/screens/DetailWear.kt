package io.github.sudomegas.saat.ui.screens

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.wrapContentWidth
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.ui.detail.MonthDensity
import io.github.sudomegas.saat.ui.detail.WearStats

/**
 * The wear section: the stats line, the twelve-month strip, and the one button.
 *
 * The BUTTON is always here; the line and the strip are not. SPEC-ANDROID 5.6
 * hides them for a watch that has never been worn, and the button is how a
 * watch stops never having been worn — so hiding it with them would be hiding
 * the only way out of that state.
 */
@Composable
internal fun WearSection(
    stats: WearStats?,
    onWoreToday: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        // SPEC-ANDROID 5.6: one tap, no dialog. A confirmation on an action this
        // small, this reversible and this often-repeated would be ceremony, and
        // pressing it twice in a day is already a visible no-op rather than a
        // mistake worth guarding.
        Button(onClick = onWoreToday) {
            Text(text = stringResource(R.string.action_wore_this_today))
        }

        if (stats != null) {
            Text(
                text = wearLine(stats),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            TwelveMonthStrip(stats.months)
        }
    }
}

/**
 * `Last worn 02.08.2026 · 1 day ago · Worn 14 times this year · Longest streak
 * 5 days`.
 *
 * Assembled from separate plural resources rather than one template with
 * embedded counts, which is the same shape the desktop settled on: a language
 * that inflects the noun cannot be served by "%d days" with the word frozen
 * outside the plural.
 */
@Composable
private fun wearLine(stats: WearStats): String {
    val parts = buildList {
        add(stringResource(R.string.screen_detail_wear_last, stats.lastWorn))
        when {
            stats.daysSince == 0 -> add(stringResource(R.string.screen_detail_wear_today))
            // A day recorded ahead of today gives a negative interval. "-3 days
            // ago" is not a thing, and the date on the line already says what
            // happened, so the interval simply drops out.
            stats.daysSince > 0 -> add(
                pluralStringResource(
                    R.plurals.screen_detail_wear_days_ago,
                    stats.daysSince,
                    stats.daysSince,
                )
            )
        }
        add(
            pluralStringResource(
                R.plurals.screen_detail_wear_this_year,
                stats.timesThisYear,
                stats.timesThisYear,
            )
        )
        add(
            pluralStringResource(
                R.plurals.screen_detail_wear_streak,
                stats.longestStreak,
                stats.longestStreak,
            )
        )
    }
    return parts.joinToString(stringResource(R.string.screen_detail_separator))
}

/**
 * This watch's worn days over the trailing twelve months — a density strip, not
 * a navigable calendar. A port of the desktop's `_TwelveMonthStrip`.
 *
 * One block per month, each block a bar with a hairline tick per worn day
 * placed proportionally along it. The point is the shape of a year at a glance:
 * a watch worn in bursts looks different from one worn every other week, and
 * neither reads that way as a number.
 */
@Composable
private fun TwelveMonthStrip(months: List<MonthDensity>) {
    val block = MaterialTheme.colorScheme.surfaceContainerHigh
    val tick = MaterialTheme.colorScheme.primary

    Column(modifier = Modifier.fillMaxWidth()) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(3.dp),
            modifier = Modifier
                .fillMaxWidth()
                .height(STRIP_HEIGHT),
        ) {
            months.forEach { month ->
                Canvas(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxSize()
                        .background(block),
                ) {
                    month.wornDays.forEach { day ->
                        // Centred within the day's share of the block, so the
                        // first and last of a month sit inside it rather than on
                        // its edges — the desktop's (day - 0.5) / daysInMonth.
                        val x = ((day - 0.5f) / month.daysInMonth) * size.width
                        drawLine(
                            color = tick,
                            start = Offset(x, TICK_INSET),
                            end = Offset(x, size.height - TICK_INSET),
                            strokeWidth = 1.dp.toPx(),
                        )
                    }
                }
            }
        }

        // Labelled every third month rather than every month. Twelve
        // three-letter labels across a phone leaves about 24dp each, which
        // clips at any raised font scale; four labels never clip, and the strip
        // still reads as a year. Each sits centred on its own block and is
        // allowed to measure past it, which is safe because its neighbours are
        // empty.
        Row(
            horizontalArrangement = Arrangement.spacedBy(3.dp),
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 4.dp),
        ) {
            months.forEachIndexed { index, month ->
                Box(modifier = Modifier.weight(1f), contentAlignment = Alignment.Center) {
                    if (index % LABEL_EVERY == 0) {
                        Text(
                            text = stringResource(month.labelRes),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            softWrap = false,
                            modifier = Modifier.wrapContentWidth(unbounded = true),
                        )
                    }
                }
            }
        }
    }
}

private val STRIP_HEIGHT = 28.dp
private const val TICK_INSET = 3f
private const val LABEL_EVERY = 3
