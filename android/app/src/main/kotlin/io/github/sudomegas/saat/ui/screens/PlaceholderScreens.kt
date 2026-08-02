package io.github.sudomegas.saat.ui.screens

import androidx.annotation.StringRes
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
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
 * Grid became real in AM3 and has moved to GridScreen.kt. Specs follows in AM6,
 * Calendar in AM7.
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
fun SpecsScreen() = Placeholder(R.string.screen_specs_placeholder)

@Composable
fun CalendarScreen() = Placeholder(R.string.screen_calendar_placeholder)

/**
 * Where a grid card lands until AM4 builds the real page.
 *
 * Shows the slug it was given, which is the point of having it now: it proves
 * the argument survives the round trip through the route, and it makes a
 * sideloaded debug build useful for checking that the right card opened.
 */
@Composable
fun DetailScreen(slug: String) {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = stringResource(R.string.screen_detail_placeholder),
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Text(
                text = slug,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
