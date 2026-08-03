package io.github.sudomegas.saat.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.ui.detail.deleteConfirmed

/**
 * Delete, at the bottom of the page — SPEC-ANDROID 5.6.
 *
 * The whole gesture is deliberately slow: scroll past the entire record, tap
 * Delete, then type the model name exactly. Nothing about it can happen by
 * accident, which is the point — this is the one action in the app that removes
 * something the owner cannot get back from anywhere else.
 *
 * It is not, however, destruction. `WatchStore.delete` MOVES both of the
 * watch's folders — its record and its photographs — into `backups/deleted/`,
 * rejoined into the one self-contained shape the desktop and the exported ZIP
 * both use. The dialog says so, because "this cannot be undone" would be untrue
 * and the truth is more reassuring than the scare.
 */
@Composable
internal fun DeleteSection(model: String, onDelete: () -> Unit) {
    var confirming by rememberSaveable { mutableStateOf(false) }

    Column(modifier = Modifier.padding(top = 24.dp)) {
        HorizontalDivider(
            thickness = Dp.Hairline,
            color = MaterialTheme.colorScheme.outlineVariant,
        )
        TextButton(
            onClick = { confirming = true },
            modifier = Modifier.padding(start = 8.dp, top = 8.dp),
        ) {
            Text(
                text = stringResource(R.string.action_delete_watch),
                color = MaterialTheme.colorScheme.error,
            )
        }
    }

    if (confirming) {
        DeleteDialog(
            model = model,
            onDismiss = { confirming = false },
            onConfirm = {
                confirming = false
                onDelete()
            },
        )
    }
}

@Composable
private fun DeleteDialog(model: String, onDismiss: () -> Unit, onConfirm: () -> Unit) {
    // Not rememberSaveable: a half-typed confirmation is not state worth
    // restoring, and a rotation is a fine moment to have to mean it again.
    var typed by rememberSaveable { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(text = stringResource(R.string.screen_detail_delete_title)) },
        text = {
            Column {
                Text(text = stringResource(R.string.screen_detail_delete_body, model))
                OutlinedTextField(
                    value = typed,
                    onValueChange = { typed = it },
                    singleLine = true,
                    // The guard is an EXACT match, matching the desktop, so the
                    // keyboard must not quietly retype what was entered. A model
                    // name is not a sentence and autocapitalising it, or
                    // "correcting" SARB033, would make a strict rule feel broken
                    // rather than strict.
                    keyboardOptions = KeyboardOptions(
                        capitalization = KeyboardCapitalization.None,
                        autoCorrectEnabled = false,
                    ),
                    label = { Text(text = stringResource(R.string.field_model)) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 12.dp),
                )
            }
        },
        confirmButton = {
            TextButton(enabled = deleteConfirmed(typed, model), onClick = onConfirm) {
                Text(
                    text = stringResource(R.string.action_delete_watch),
                    color = MaterialTheme.colorScheme.error,
                )
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(text = stringResource(R.string.action_cancel))
            }
        },
    )
}
