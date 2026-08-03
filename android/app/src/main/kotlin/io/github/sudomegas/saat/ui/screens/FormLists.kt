package io.github.sudomegas.saat.ui.screens

import androidx.annotation.StringRes
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.ui.form.CLASPS
import io.github.sudomegas.saat.ui.form.EnumChoice
import io.github.sudomegas.saat.ui.form.LOG_KINDS
import io.github.sudomegas.saat.ui.form.LogFormState
import io.github.sudomegas.saat.ui.form.StrapFormState
import io.github.sudomegas.saat.ui.form.TIMING_POSITIONS
import io.github.sudomegas.saat.ui.form.TimingFormState

/**
 * The four list-shaped fields: tags, complications, straps, log and timing.
 *
 * Every one is add-a-row / edit-in-place / remove-a-row rather than a modal
 * sub-editor. A dialog over a form is a second place to lose what you typed, and
 * these rows are two or three fields each.
 */

/**
 * A list of plain strings — tags, and dial complications.
 *
 * Duplicates are silently ignored rather than rejected with a message, matching
 * the desktop's `_add_current`: adding "daily" twice is a slip, not an error
 * worth interrupting anyone about.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun StringListEditor(
    @StringRes labelRes: Int,
    values: List<String>,
    suggestions: List<EnumChoice>,
    onChange: (List<String>) -> Unit,
) {
    var typed by remember { mutableStateOf("") }

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (suggestions.isEmpty()) {
                OutlinedTextField(
                    value = typed,
                    onValueChange = { typed = it },
                    label = { Text(text = stringResource(labelRes)) },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
            } else {
                FormEnum(
                    labelRes = labelRes,
                    value = typed,
                    choices = suggestions,
                    onChange = { typed = it },
                    modifier = Modifier.weight(1f),
                )
            }
            TextButton(
                onClick = {
                    val value = typed.trim()
                    if (value.isNotEmpty() && value !in values) onChange(values + value)
                    typed = ""
                },
            ) {
                Text(text = stringResource(R.string.action_add))
            }
        }

        // Chips, because these are short values and there can be a dozen of
        // them. Tapping one removes it — the only action a chip in a form has.
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.fillMaxWidth(),
        ) {
            values.forEach { value ->
                FilterChip(
                    selected = true,
                    onClick = { onChange(values - value) },
                    label = { Text(text = value) },
                )
            }
        }
    }
}

/**
 * The straps.
 *
 * AT MOST ONE FITTED, enforced the moment it is ticked rather than at save:
 * ticking a strap unticks whichever other one claimed it, so the invariant is
 * true of what is on screen and not only of what reaches disk. Unticking is
 * never blocked — a watch with no strap fitted is an ordinary thing, a watch
 * with two is not.
 */
@Composable
fun StrapsEditor(
    straps: List<StrapFormState>,
    materials: List<EnumChoice>,
    images: List<String>,
    onChange: (List<StrapFormState>) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        straps.forEachIndexed { index, strap ->
            RowCard(onRemove = { onChange(straps.filterIndexed { i, _ -> i != index }) }) {
                fun edit(transform: (StrapFormState) -> StrapFormState) {
                    onChange(straps.mapIndexed { i, s -> if (i == index) transform(s) else s })
                }

                FormEnum(
                    labelRes = R.string.field_strap_material,
                    value = strap.material,
                    choices = materials,
                    onChange = { value -> edit { it.copy(material = value) } },
                )
                FormText(
                    labelRes = R.string.field_strap_colour,
                    value = strap.colour,
                    onChange = { value -> edit { it.copy(colour = value) } },
                )
                FormInt(
                    labelRes = R.string.field_strap_width,
                    value = strap.widthMm,
                    onChange = { value -> edit { it.copy(widthMm = value) } },
                    suffixRes = R.string.field_suffix_mm,
                )
                FormEnum(
                    labelRes = R.string.field_strap_clasp,
                    value = strap.clasp,
                    choices = CLASPS,
                    onChange = { value -> edit { it.copy(clasp = value) } },
                )
                if (images.isNotEmpty()) {
                    FormEnum(
                        labelRes = R.string.field_strap_image,
                        value = strap.image,
                        choices = images.map { EnumChoice(it) },
                        onChange = { value -> edit { it.copy(image = value) } },
                    )
                }
                FormBoolean(
                    labelRes = R.string.field_strap_fitted,
                    value = strap.fitted,
                    onChange = { fitted ->
                        onChange(
                            straps.mapIndexed { i, s ->
                                when {
                                    i == index -> s.copy(fitted = fitted)
                                    // Ticking this one unticks the rest. Only
                                    // when ticking: unticking must not disturb
                                    // a strap it has nothing to do with.
                                    fitted -> s.copy(fitted = false)
                                    else -> s
                                }
                            }
                        )
                    },
                )
            }
        }
        TextButton(onClick = { onChange(straps + StrapFormState()) }) {
            Text(text = stringResource(R.string.action_add_strap))
        }
    }
}

@Composable
fun LogEditor(entries: List<LogFormState>, onChange: (List<LogFormState>) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        entries.forEachIndexed { index, entry ->
            RowCard(onRemove = { onChange(entries.filterIndexed { i, _ -> i != index }) }) {
                fun edit(transform: (LogFormState) -> LogFormState) {
                    onChange(entries.mapIndexed { i, e -> if (i == index) transform(e) else e })
                }

                FormDate(
                    labelRes = R.string.field_log_date,
                    value = entry.date,
                    onChange = { value -> edit { it.copy(date = value) } },
                )
                FormEnum(
                    labelRes = R.string.field_log_kind,
                    value = entry.kind,
                    choices = LOG_KINDS,
                    onChange = { value -> edit { it.copy(kind = value) } },
                )
                FormText(
                    labelRes = R.string.field_log_note,
                    value = entry.note,
                    onChange = { value -> edit { it.copy(note = value) } },
                    singleLine = false,
                )
            }
        }
        TextButton(onClick = { onChange(entries + LogFormState()) }) {
            Text(text = stringResource(R.string.action_add_log_entry))
        }
    }
}

@Composable
fun TimingEditor(readings: List<TimingFormState>, onChange: (List<TimingFormState>) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        readings.forEachIndexed { index, reading ->
            RowCard(onRemove = { onChange(readings.filterIndexed { i, _ -> i != index }) }) {
                fun edit(transform: (TimingFormState) -> TimingFormState) {
                    onChange(readings.mapIndexed { i, r -> if (i == index) transform(r) else r })
                }

                FormDate(
                    labelRes = R.string.field_timing_date,
                    value = reading.date,
                    onChange = { value -> edit { it.copy(date = value) } },
                )
                FormDecimal(
                    labelRes = R.string.field_timing_deviation,
                    value = reading.deviationSec,
                    onChange = { value -> edit { it.copy(deviationSec = value) } },
                    suffixRes = R.string.field_suffix_sec,
                    // A watch running slow is the whole point of the reading, so
                    // the keyboard has to offer a minus sign.
                    signed = true,
                )
                FormEnum(
                    labelRes = R.string.field_timing_position,
                    value = reading.position,
                    choices = TIMING_POSITIONS,
                    onChange = { value -> edit { it.copy(position = value) } },
                )
            }
        }
        TextButton(onClick = { onChange(readings + TimingFormState()) }) {
            Text(text = stringResource(R.string.action_add_timing_reading))
        }
    }
}

/** One entry in a list field: its fields, and the one action a row has. */
@Composable
private fun RowCard(onRemove: () -> Unit, content: @Composable () -> Unit) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainer,
        ),
        border = BorderStroke(Dp.Hairline, MaterialTheme.colorScheme.outlineVariant),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            content()
            Row(horizontalArrangement = Arrangement.End, modifier = Modifier.fillMaxWidth()) {
                TextButton(onClick = onRemove) {
                    Text(
                        text = stringResource(R.string.action_remove),
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
        }
    }
}
