package io.github.sudomegas.saat.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.annotation.StringRes
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.config.AppConfig
import io.github.sudomegas.saat.config.ThemeMode
import io.github.sudomegas.saat.storage.WatchRepository
import io.github.sudomegas.saat.storage.exportFilename
import io.github.sudomegas.saat.ui.TransferResult
import io.github.sudomegas.saat.ui.TransferViewModel
import io.github.sudomegas.saat.ui.theme.dynamicColorAvailable
import java.time.LocalDate

@Composable
fun SettingsScreen(
    config: AppConfig,
    repository: WatchRepository,
    transferViewModel: TransferViewModel,
    onThemeModeChange: (ThemeMode) -> Unit,
    onDynamicColorChange: (Boolean) -> Unit,
    onLanguageChange: (String) -> Unit,
) {
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(vertical = 8.dp)
    ) {
        SectionHeader(stringResource(R.string.settings_theme))

        Column(Modifier.selectableGroup()) {
            ThemeMode.entries.forEach { mode ->
                val label = when (mode) {
                    ThemeMode.SYSTEM -> R.string.settings_theme_system
                    ThemeMode.LIGHT -> R.string.settings_theme_light
                    ThemeMode.DARK -> R.string.settings_theme_dark
                }
                Row(
                    Modifier
                        .fillMaxWidth()
                        .selectable(
                            selected = config.themeMode == mode,
                            onClick = { onThemeModeChange(mode) },
                            role = Role.RadioButton,
                        )
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    RadioButton(selected = config.themeMode == mode, onClick = null)
                    Text(
                        text = stringResource(label),
                        style = MaterialTheme.typography.bodyLarge,
                        modifier = Modifier.padding(start = 16.dp),
                    )
                }
            }
        }

        // Hidden entirely below Android 12 rather than shown and disabled: a
        // control that can never do anything is noise, and SPEC-ANDROID 5.10
        // scopes it to 12+ in so many words.
        if (dynamicColorAvailable) {
            HorizontalDivider(
                Modifier.padding(vertical = 8.dp),
                color = MaterialTheme.colorScheme.outlineVariant,
            )
            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(
                        text = stringResource(R.string.settings_dynamic_colour),
                        style = MaterialTheme.typography.bodyLarge,
                    )
                    Text(
                        text = stringResource(R.string.settings_dynamic_colour_summary),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(
                    checked = config.dynamicColor,
                    onCheckedChange = onDynamicColorChange,
                )
            }
        }

        HorizontalDivider(
            Modifier.padding(vertical = 8.dp),
            color = MaterialTheme.colorScheme.outlineVariant,
        )
        LanguageSection(current = config.language, onChange = onLanguageChange)

        HorizontalDivider(
            Modifier.padding(vertical = 8.dp),
            color = MaterialTheme.colorScheme.outlineVariant,
        )
        DataSection(viewModel = transferViewModel)

        // Renders the demo-watch actions in debug builds and literally nothing
        // in release: there are two DeveloperSection composables, one per build
        // type, and this file names neither the generator nor its package. See
        // src/release/.../DeveloperSection.kt for why absence beats a flag.
        DeveloperSection(repository)
    }
}

/**
 * English or Turkish, chosen explicitly — SPEC-ANDROID 5.10 and hard rule 7.
 *
 * EACH LANGUAGE IS NAMED IN ITS OWN TONGUE and neither name is translated, so
 * an owner who has just set the app to a language they cannot read can still
 * find their way back. That is the one place in the app where leaving a string
 * untranslated is the correct decision rather than an oversight.
 *
 * There is no "System" option here, and its absence is the rule rather than an
 * omission: hard rule 7 says the app never reads the system locale to choose
 * its language, and a System entry would be exactly that, offered as a feature.
 */
@Composable
private fun LanguageSection(current: String, onChange: (String) -> Unit) {
    SectionHeader(stringResource(R.string.settings_language))

    Column(Modifier.selectableGroup()) {
        LANGUAGES.forEach { (code, labelRes) ->
            Row(
                Modifier
                    .fillMaxWidth()
                    .selectable(
                        selected = current == code,
                        onClick = { onChange(code) },
                        role = Role.RadioButton,
                    )
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RadioButton(selected = current == code, onClick = null)
                Text(
                    text = stringResource(labelRes),
                    style = MaterialTheme.typography.bodyLarge,
                    modifier = Modifier.padding(start = 16.dp),
                )
            }
        }
    }
}

/**
 * The two languages v1.0 ships, as (tag, label) pairs.
 *
 * The tag is what reaches AppCompatDelegate and what `config.toml` stores; it
 * is never shown. Adding a third language means adding `values-<tag>/` and one
 * entry here, and StringsTranslationTest will then require the new folder to be
 * complete.
 */
private val LANGUAGES = listOf(
    AppConfig.DEFAULT_LANGUAGE to R.string.settings_language_en,
    "tr" to R.string.settings_language_tr,
)

/**
 * Export and import — SPEC-ANDROID 5.10, AM10.
 *
 * The paragraph beneath the buttons is AM10c's "plain data section stating where
 * data lives, what the cloud backup covers and does not". It is deliberately
 * dull: this is the screen where an owner comes to satisfy themselves that their
 * records are not trapped, and a marketing voice here would achieve the reverse.
 *
 * The picker is launched with a filename the owner can change. Both buttons are
 * disabled while a transfer runs, because two concurrent writes to the same tree
 * is the one way this feature could actually lose data.
 */
@Composable
private fun DataSection(viewModel: TransferViewModel) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    val create = rememberLauncherForActivityResult(
        // "application/zip" rather than a wildcard: the picker then suggests the
        // right extension and other apps can see what the file is.
        ActivityResultContracts.CreateDocument(ZIP_MIME),
    ) { uri -> uri?.let(viewModel::export) }

    val open = rememberLauncherForActivityResult(
        // Two MIME types, because a ZIP arrives under either depending on which
        // app wrote it, and a file the picker greys out is a file the owner
        // cannot import however valid it is.
        ActivityResultContracts.OpenDocument(),
    ) { uri -> uri?.let(viewModel::import) }

    SectionHeader(stringResource(R.string.settings_data))

    Text(
        text = stringResource(R.string.settings_export_summary),
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
    )

    Row(
        Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        TextButton(
            onClick = { create.launch(exportFilename(LocalDate.now())) },
            enabled = !state.isRunning,
        ) {
            Text(text = stringResource(R.string.action_export_zip))
        }
        TextButton(
            onClick = { open.launch(ZIP_MIME_TYPES) },
            enabled = !state.isRunning,
        ) {
            Text(text = stringResource(R.string.action_import_zip))
        }
    }

    state.progress?.takeIf { state.isRunning }?.let { progress ->
        Text(
            text = stringResource(
                R.string.settings_transfer_working,
                progress.done,
                progress.total,
            ),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(horizontal = 16.dp),
        )
    }

    TransferOutcome(result = state.result)

    Text(
        text = stringResource(R.string.settings_data_about),
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
    )
}

/**
 * What happened, in plain figures.
 *
 * Stays on screen rather than passing as a snackbar: an export names a
 * destination the owner may want to go and look for, and a message that
 * disappears after four seconds is a message they have to repeat the operation
 * to read again.
 */
@Composable
private fun TransferOutcome(result: TransferResult?) {
    when (result) {
        null -> Unit

        is TransferResult.Exported -> Column(
            Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
        ) {
            Text(
                text = stringResource(
                    R.string.settings_export_done,
                    result.summary.watches,
                    result.summary.images,
                    result.destination,
                ),
                style = MaterialTheme.typography.bodyMedium,
            )
            // Hard rule 6 again: a folder with no watch.toml in it did not
            // travel, and the owner hears which one while they can still act.
            if (result.summary.skipped.isNotEmpty()) {
                Text(
                    text = stringResource(
                        R.string.settings_export_skipped,
                        result.summary.skipped.joinToString(", "),
                    ),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        is TransferResult.Imported -> Column(
            Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
        ) {
            Text(
                text = stringResource(
                    R.string.settings_import_done,
                    result.summary.added.size,
                    result.summary.skipped.size,
                ),
                style = MaterialTheme.typography.bodyMedium,
            )
            // Every one of the four outcomes is NAMED, not counted — SPEC-ANDROID
            // 3.2 asks for "n added, n skipped, named", and a watch that did not
            // arrive is exactly the thing the owner needs to be able to look for.
            ImportDetail(R.string.settings_import_added, result.summary.added)
            ImportDetail(R.string.settings_import_skipped, result.summary.skipped)
            ImportDetail(R.string.settings_import_malformed, result.summary.malformed)
            ImportDetail(R.string.settings_import_ignored, result.summary.ignored)
        }

        is TransferResult.Failed -> Text(
            text = stringResource(R.string.settings_transfer_failed, result.message),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.error,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
        )
    }
}

private const val ZIP_MIME = "application/zip"

/**
 * `application/octet-stream` is listed because a good many file managers hand a
 * .zip over under it, and without it the picker greys out the very file the
 * owner just exported. The archive is validated on the way in regardless of
 * what MIME type it claimed on the way through the picker.
 */
private val ZIP_MIME_TYPES = arrayOf(ZIP_MIME, "application/octet-stream")

/** One named list, or nothing at all when that outcome did not happen. */
@Composable
private fun ImportDetail(@StringRes templateRes: Int, names: List<String>) {
    if (names.isEmpty()) return
    Text(
        text = stringResource(templateRes, names.joinToString(", ")),
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

@Composable
private fun SectionHeader(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
    )
}
