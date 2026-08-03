package io.github.sudomegas.saat.ui.screens

import androidx.annotation.StringRes
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import io.github.sudomegas.saat.R

/**
 * AM1 ships the shell, not the screens. Each destination states its own name
 * and nothing else — deliberately, so the milestone's diff stays readable.
 *
 * Grid became real in AM3, Detail in AM4, Specs in AM6, each moving to its own
 * file as it did. Calendar follows in AM7, and this file goes with it.
 */
@Composable
private fun Placeholder(@StringRes labelRes: Int) {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Text(
            text = stringResource(labelRes),
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
fun CalendarScreen() = Placeholder(R.string.screen_calendar_placeholder)
