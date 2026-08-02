package io.github.sudomegas.saat.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.config.ThemeMode
import io.github.sudomegas.saat.ui.theme.SaatTheme

/**
 * What the app is, for as long as the collection is empty — which, since SAAT
 * ships empty by rule, is the very first thing anyone sees.
 *
 * SPEC-ANDROID 5.8, held to literally: a line saying the collection is empty, a
 * sentence saying the data is plain TOML the owner can export at any time, and
 * one primary button. No illustration, no mascot, no exclamation marks. The
 * desktop earns a live painted watch dial here; Android deliberately does not
 * copy it, because the owner chose system feel over porting the desktop's
 * identity (SPEC-ANDROID 6).
 *
 * The second line is not filler. It is the promise the whole project rests on —
 * that this is your data in files you can take somewhere else — and the empty
 * state is the one screen with room to say it.
 */
@Composable
fun CollectionEmptyState(
    onAddWatch: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = stringResource(R.string.screen_grid_empty_title),
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurface,
            textAlign = TextAlign.Center,
        )
        Text(
            text = stringResource(R.string.screen_grid_empty_body),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
            modifier = Modifier
                .padding(top = 8.dp)
                .widthIn(max = 320.dp),
        )
        Button(
            onClick = onAddWatch,
            modifier = Modifier.padding(top = 24.dp),
        ) {
            Text(text = stringResource(R.string.action_add_watch))
        }
    }
}

// The milestone asks for this screen to be reviewed in light and dark. Both
// previews pin dynamicColor = false: dynamic colour is the wallpaper's palette
// and has no fixed appearance to review, while these two are the constants the
// contrast tests actually measure.

@Preview(name = "Empty state — light", showBackground = true)
@Composable
private fun CollectionEmptyStateLightPreview() {
    SaatTheme(mode = ThemeMode.LIGHT, dynamicColor = false) {
        Surface { CollectionEmptyState(onAddWatch = {}) }
    }
}

@Preview(name = "Empty state — dark", showBackground = true)
@Composable
private fun CollectionEmptyStateDarkPreview() {
    SaatTheme(mode = ThemeMode.DARK, dynamicColor = false) {
        Surface { CollectionEmptyState(onAddWatch = {}) }
    }
}
