package io.github.sudomegas.saat.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.ui.LoadFailure

/**
 * The files the loader could not read, named above the grid.
 *
 * SPEC-ANDROID hard rule 6 — never silently swallow an exception — and 3's
 * "never a crash, never silent". AM2 already does the hard half: a malformed
 * `watch.toml` stays in the collection carrying its error rather than vanishing,
 * so the count here is trustworthy. This is only the part that says so out loud.
 *
 * Rendered as a quiet line rather than a dialog. A dialog would demand a
 * response to something the owner can only fix in a text editor, and would do it
 * on every launch until they did.
 */
@Composable
fun LoadFailureNotice(
    failures: List<LoadFailure>,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
) {
    if (failures.isEmpty()) return

    val collectionFolderUnreadable = stringResource(R.string.error_watches_dir_unreadable)

    Column(modifier = modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(start = 16.dp, top = 8.dp, end = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = pluralStringResource(
                    R.plurals.screen_grid_notice_title,
                    failures.size,
                    failures.size,
                ),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.onSurface,
            )
            TextButton(onClick = onDismiss) {
                Text(text = stringResource(R.string.action_dismiss))
            }
        }

        failures.forEach { failure ->
            // A null slug is the collection folder itself, not a watch. Naming
            // it by its directory would announce a watch called "watches".
            val line = if (failure.slug == null) {
                collectionFolderUnreadable
            } else {
                stringResource(R.string.error_watch_unreadable, failure.slug, failure.message)
            }
            Text(
                text = line,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(start = 16.dp, end = 16.dp, bottom = 4.dp),
            )
        }

        HorizontalDivider(
            color = MaterialTheme.colorScheme.outlineVariant,
            modifier = Modifier.padding(top = 8.dp),
        )
    }
}
