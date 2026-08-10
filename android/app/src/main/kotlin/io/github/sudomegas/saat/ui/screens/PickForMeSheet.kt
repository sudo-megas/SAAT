package io.github.sudomegas.saat.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.storage.PickerMode
import io.github.sudomegas.saat.ui.PickForMeState
import io.github.sudomegas.saat.ui.PickerWatch

private val SPACING = 16.dp

/**
 * "Pick for me" — SPEC-ANDROID 5.5, ported from the desktop's
 * `saat/ui/today_picker.py`. Additive to [DayPicker]; the two are
 * mutually exclusive at the ViewModel level (see `CalendarViewModel`).
 *
 * NO TUMBLE, NO SETTLE ANIMATION. The desktop dialog dramatises its pick with
 * a die that rolls before landing; SPEC-ANDROID §6 rules that out for Android
 * outright ("no celebratory animation... no decoration beyond Material
 * defaults"), so the reveal here is the chosen watch, shown plainly the
 * instant the sheet composes.
 *
 * Three branches on [PickForMeState.owned]'s size, matching the desktop's own
 * `TodayPickerDialog.__init__`: none (a message, nothing to pick), exactly
 * one (a name and a single confirm button — no mode toggle, no re-roll,
 * since there is nothing to roll between), and several (the full mode toggle
 * plus re-roll).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PickForMeSheet(
    state: PickForMeState,
    onModeChange: (PickerMode) -> Unit,
    onReroll: () -> Unit,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
                .padding(bottom = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = stringResource(R.string.screen_calendar_pick_for_me_title),
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Spacer(modifier = Modifier.height(SPACING))

            when {
                state.owned.isEmpty() -> EmptyPickForMe()
                state.owned.size == 1 -> SingleWatchPickForMe(watch = state.owned.single(), onConfirm = onConfirm)
                else -> MultiWatchPickForMe(
                    state = state,
                    onModeChange = onModeChange,
                    onReroll = onReroll,
                    onConfirm = onConfirm,
                )
            }
        }
    }
}

@Composable
private fun EmptyPickForMe() {
    Text(
        text = stringResource(R.string.screen_calendar_pick_for_me_empty),
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        textAlign = TextAlign.Center,
    )
}

@Composable
private fun SingleWatchPickForMe(watch: PickerWatch, onConfirm: () -> Unit) {
    Text(
        text = stringResource(R.string.screen_calendar_pick_for_me_only, watch.brand, watch.model),
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurface,
        textAlign = TextAlign.Center,
    )
    Spacer(modifier = Modifier.height(SPACING))
    Button(onClick = onConfirm) {
        Text(text = stringResource(R.string.action_wore_this_today))
    }
}

@Composable
private fun MultiWatchPickForMe(
    state: PickForMeState,
    onModeChange: (PickerMode) -> Unit,
    onReroll: () -> Unit,
    onConfirm: () -> Unit,
) {
    // The app's one selection-among-N idiom (SettingsScreen's theme choice),
    // laid out in a row rather than stacked to fit a sheet instead of a
    // settings page — not a new control vocabulary (FilterChip/SegmentedButton
    // appear nowhere else in the app).
    Row(modifier = Modifier.selectableGroup(), horizontalArrangement = Arrangement.Center) {
        PickerModeOption(
            label = stringResource(R.string.action_picker_mode_random),
            selected = state.mode == PickerMode.RANDOM,
            onClick = { onModeChange(PickerMode.RANDOM) },
        )
        PickerModeOption(
            label = stringResource(R.string.action_picker_mode_weighted),
            selected = state.mode == PickerMode.WEIGHTED,
            onClick = { onModeChange(PickerMode.WEIGHTED) },
        )
    }
    Spacer(modifier = Modifier.height(SPACING))

    val chosen = state.chosen
    if (chosen != null) {
        PickerThumbnail(chosen.image, size = REVEAL_THUMBNAIL_SIZE)
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = chosen.brand,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = chosen.model,
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurface,
        )
    }
    Spacer(modifier = Modifier.height(SPACING))

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        TextButton(onClick = onReroll) {
            Text(text = stringResource(R.string.action_reroll))
        }
        // Disabled rather than assumed non-null: the chosen watch can in
        // principle be deleted or lose Owned status while the sheet is open
        // (see PickForMeState's doc comment).
        Button(onClick = onConfirm, enabled = chosen != null) {
            Text(text = stringResource(R.string.action_wore_this_today))
        }
    }
}

@Composable
private fun PickerModeOption(label: String, selected: Boolean, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .selectable(selected = selected, onClick = onClick, role = Role.RadioButton)
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(selected = selected, onClick = null)
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(start = 4.dp),
        )
    }
}

private val REVEAL_THUMBNAIL_SIZE: Dp = 96.dp
