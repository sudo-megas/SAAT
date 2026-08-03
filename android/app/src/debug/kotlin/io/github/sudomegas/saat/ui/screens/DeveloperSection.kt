package io.github.sudomegas.saat.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import io.github.sudomegas.saat.R
import android.appwidget.AppWidgetManager
import android.content.ComponentName
import io.github.sudomegas.saat.devtools.DemoWatches
import io.github.sudomegas.saat.widget.TodayWidgetProvider
import io.github.sudomegas.saat.storage.WatchRepository
import kotlinx.coroutines.launch

/**
 * The debug half of the twin. `src/release` holds one with the same signature
 * and an empty body, which is what lets `SettingsScreen` in `src/main` call this
 * unconditionally without ever naming the `devtools` package.
 *
 * That indirection is the whole point: `src/main` cannot see `src/debug`, so if
 * the generator were referenced directly from a shared file the release build
 * would not compile. Routing through a per-variant composable makes the absence
 * structural instead of conditional, and `GridPolicyTest` asserts that no file
 * under `src/main` mentions `devtools` so it stays that way.
 *
 * No ViewModel. `WatchRepository.create` and `delete` already move to the I/O
 * dispatcher themselves, and this is debug glue that ships to nobody — giving it
 * the ceremony of a state holder would imply it deserved one.
 */
@Composable
fun DeveloperSection(repository: WatchRepository) {
    val scope = rememberCoroutineScope()

    Column(modifier = Modifier.fillMaxWidth()) {
        HorizontalDivider(
            modifier = Modifier.padding(vertical = 8.dp),
            color = MaterialTheme.colorScheme.outlineVariant,
        )
        Text(
            text = stringResource(R.string.settings_demo_watches),
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        )
        Text(
            text = stringResource(R.string.settings_demo_watches_summary),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(horizontal = 16.dp),
        )
        Row(modifier = Modifier.padding(horizontal = 8.dp)) {
            TextButton(onClick = { scope.launch { DemoWatches.generate(repository) } }) {
                Text(text = stringResource(R.string.action_add_demo_watches))
            }
            TextButton(onClick = { scope.launch { DemoWatches.clear(repository) } }) {
                Text(text = stringResource(R.string.action_clear_demo_watches))
            }
        }

        // AM8. Placing a widget otherwise means driving the launcher's own
        // long-press menu, which is launcher-specific and not scriptable — and
        // the widget is the one part of this app whose runtime behaviour cannot
        // be checked from a unit test at all, because it draws in another
        // process. Debug-only, like everything else in this file.
        val context = LocalContext.current
        TextButton(
            onClick = {
                val manager = context.getSystemService(AppWidgetManager::class.java)
                val provider = ComponentName(context, TodayWidgetProvider::class.java)
                if (manager?.isRequestPinAppWidgetSupported == true) {
                    manager.requestPinAppWidget(provider, null, null)
                }
            },
            modifier = Modifier.padding(horizontal = 8.dp),
        ) {
            Text(text = stringResource(R.string.action_demo_pin_widget))
        }
    }
}
