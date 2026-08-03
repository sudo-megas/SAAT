package io.github.sudomegas.saat.ui.screens

import androidx.annotation.StringRes
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TriStateCheckbox
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.state.ToggleableState
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.ui.form.EnumChoice
import io.github.sudomegas.saat.ui.formatDate
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

/**
 * The form's field vocabulary — SPEC-ANDROID 5.7.
 *
 * Built once here and used by every group, so that "numeric fields get numeric
 * keyboards and unit suffixes inside the field" is a property of the widget
 * rather than something forty call sites have to remember. The alternative,
 * forty hand-written `OutlinedTextField`s, is forty chances for one of them to
 * open the wrong keyboard.
 */

/**
 * A collapsible group header — NOT a tab, and that is the spec's own reasoning:
 * "Tabs on a phone hide what is unfilled; a scroll shows the whole shape of the
 * record."
 *
 * Groups open by default. A form that starts fully collapsed hides the shape it
 * exists to show, and the owner would have to open nine sections to find out
 * that eight of them are empty.
 */
@Composable
fun FormSection(
    @StringRes titleRes: Int,
    expanded: Boolean,
    onToggle: () -> Unit,
    content: @Composable () -> Unit,
) {
    Column(modifier = Modifier.fillMaxWidth()) {
        HorizontalDivider(
            thickness = Dp.Hairline,
            color = MaterialTheme.colorScheme.outlineVariant,
        )
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(onClick = onToggle)
                .padding(horizontal = 16.dp, vertical = 14.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = stringResource(titleRes),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = stringResource(
                    if (expanded) R.string.action_collapse else R.string.action_expand
                ),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.primary,
            )
        }
        if (expanded) {
            Column(
                modifier = Modifier.padding(start = 16.dp, end = 16.dp, bottom = 12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                content()
            }
        }
    }
}

/** A plain text field. [suffixRes] puts the unit INSIDE the field, per 5.7. */
@Composable
fun FormText(
    @StringRes labelRes: Int,
    value: String,
    onChange: (String) -> Unit,
    modifier: Modifier = Modifier,
    keyboard: KeyboardType = KeyboardType.Text,
    @StringRes suffixRes: Int? = null,
    singleLine: Boolean = true,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        label = { Text(text = stringResource(labelRes)) },
        suffix = suffixRes?.let { { Text(text = stringResource(it)) } },
        keyboardOptions = KeyboardOptions(keyboardType = keyboard),
        singleLine = singleLine,
        modifier = modifier.fillMaxWidth(),
    )
}

/**
 * A whole number. `KeyboardType.Number` offers digits only.
 *
 * Nothing filters the keystrokes. A field that silently refuses characters is a
 * field that appears broken, and a value that will not parse is simply absent at
 * save time — validation may advise, it may never obstruct (5.7).
 */
@Composable
fun FormInt(
    @StringRes labelRes: Int,
    value: String,
    onChange: (String) -> Unit,
    @StringRes suffixRes: Int? = null,
) = FormText(labelRes, value, onChange, keyboard = KeyboardType.Number, suffixRes = suffixRes)

/**
 * A decimal. `KeyboardType.Decimal` adds the separator key.
 *
 * The value is parsed with `toDoubleOrNull`, which accepts `.` and not `,` — so
 * a phone whose keyboard offers a comma would produce an unparseable figure.
 * Commas are rewritten to full stops on the way in rather than rejected, which
 * is the only behaviour that is right for both keyboards.
 */
@Composable
fun FormDecimal(
    @StringRes labelRes: Int,
    value: String,
    onChange: (String) -> Unit,
    @StringRes suffixRes: Int? = null,
    signed: Boolean = false,
) = FormText(
    labelRes = labelRes,
    value = value,
    onChange = { onChange(it.replace(',', '.')) },
    keyboard = if (signed) KeyboardType.Number else KeyboardType.Decimal,
    suffixRes = suffixRes,
)

/**
 * An `enum*` field: the schema's suggestions, plus every value the collection
 * already uses, plus whatever the owner types — SPEC.md §4.
 *
 * EDITABLE, always. "The owner will buy something you did not anticipate" is in
 * the spec verbatim, and a closed dropdown would make the app argue with the
 * collection it exists to record. What is stored is [EnumChoice.value], the
 * canonical English; what is shown is its label. Free text is stored as typed.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FormEnum(
    @StringRes labelRes: Int,
    value: String,
    choices: List<EnumChoice>,
    onChange: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var expanded by remember { mutableStateOf(false) }

    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = it },
        modifier = modifier.fillMaxWidth(),
    ) {
        OutlinedTextField(
            value = value,
            onValueChange = onChange,
            label = { Text(text = stringResource(labelRes)) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            singleLine = true,
            modifier = Modifier
                .menuAnchor(MenuAnchorType.PrimaryEditable)
                .fillMaxWidth(),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            choices.forEach { choice ->
                DropdownMenuItem(
                    text = { Text(text = choice.label()) },
                    onClick = {
                        // The canonical value, never the label. A Turkish build
                        // shows Turkish here and writes the same English file
                        // the desktop writes — hard rule 7.
                        onChange(choice.value)
                        expanded = false
                    },
                )
            }
        }
    }
}

/** A closed list — only `status`, which the desktop also treats as a real enum. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FormFixedEnum(
    @StringRes labelRes: Int,
    value: String,
    choices: List<EnumChoice>,
    onChange: (String) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    val shown = choices.firstOrNull { it.value == value }?.label() ?: value

    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = it },
        modifier = Modifier.fillMaxWidth(),
    ) {
        OutlinedTextField(
            value = shown,
            onValueChange = {},
            readOnly = true,
            label = { Text(text = stringResource(labelRes)) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            singleLine = true,
            modifier = Modifier
                .menuAnchor(MenuAnchorType.PrimaryNotEditable)
                .fillMaxWidth(),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            choices.forEach { choice ->
                DropdownMenuItem(
                    text = { Text(text = choice.label()) },
                    onClick = {
                        onChange(choice.value)
                        expanded = false
                    },
                )
            }
        }
    }
}

/**
 * A three-state checkbox: unset, yes, no.
 *
 * Absence is a value — a watch whose hacking nobody has checked is not a watch
 * that does not hack. A two-state checkbox would force every unfilled boolean to
 * claim `false`, and `WatchToml` would then write that claim into the file.
 */
@Composable
fun FormTristate(
    @StringRes labelRes: Int,
    value: Boolean?,
    onChange: (Boolean?) -> Unit,
) {
    val next = when (value) {
        null -> true
        true -> false
        false -> null
    }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onChange(next) }
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        TriStateCheckbox(
            state = when (value) {
                true -> ToggleableState.On
                false -> ToggleableState.Off
                null -> ToggleableState.Indeterminate
            },
            // Null: the row owns the click, so a screen reader announces the
            // label rather than a bare checkbox with no name.
            onClick = null,
        )
        Column(modifier = Modifier.padding(start = 12.dp)) {
            Text(
                text = stringResource(labelRes),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Text(
                text = stringResource(
                    when (value) {
                        true -> R.string.field_value_yes
                        false -> R.string.field_value_no
                        null -> R.string.field_value_unset
                    }
                ),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

/**
 * A plain two-state checkbox, for the one boolean that has no third state.
 *
 * `Strap.fitted` is not nullable in the model — matching the desktop's `fitted:
 * bool = False` — because a strap that does not say it is fitted is not fitted,
 * and there is no absence worth rendering. Every other boolean on a watch uses
 * [FormTristate] instead.
 */
@Composable
fun FormBoolean(
    @StringRes labelRes: Int,
    value: Boolean,
    onChange: (Boolean) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onChange(!value) }
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Checkbox(checked = value, onCheckedChange = null)
        Text(
            text = stringResource(labelRes),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.padding(start = 12.dp),
        )
    }
}

/**
 * A date, through the Material picker, displayed `DD.MM.YYYY` — SPEC-ANDROID 4.
 *
 * Read-only as a text field: a typed date has half a dozen ambiguous forms and
 * the picker has none. Clearing is its own action, because a date field with no
 * way back to empty is a field that can only ever be wrong once.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FormDate(
    @StringRes labelRes: Int,
    value: LocalDate?,
    onChange: (LocalDate?) -> Unit,
) {
    var picking by rememberSaveable { mutableStateOf(false) }

    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(modifier = Modifier.weight(1f)) {
            OutlinedTextField(
                value = value?.let(::formatDate).orEmpty(),
                onValueChange = {},
                readOnly = true,
                label = { Text(text = stringResource(labelRes)) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            // An overlay rather than a trailing icon button: the whole field
            // should open the picker, and `readOnly` still consumes taps.
            Box(
                modifier = Modifier
                    .matchParentSize()
                    .clickable { picking = true },
            )
        }
        if (value != null) {
            TextButton(onClick = { onChange(null) }) {
                Text(text = stringResource(R.string.action_clear))
            }
        }
    }

    if (picking) {
        // UTC throughout: the picker speaks epoch millis and a `worn` entry is a
        // plain calendar date with no time and no zone (SPEC-ANDROID 4). Reading
        // it back in the device's zone would land on the previous day west of
        // Greenwich.
        val state = rememberDatePickerState(
            initialSelectedDateMillis = value?.toEpochDay()?.times(MILLIS_PER_DAY),
        )
        DatePickerDialog(
            onDismissRequest = { picking = false },
            confirmButton = {
                TextButton(onClick = {
                    state.selectedDateMillis?.let {
                        onChange(Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate())
                    }
                    picking = false
                }) {
                    Text(text = stringResource(R.string.action_confirm))
                }
            },
            dismissButton = {
                TextButton(onClick = { picking = false }) {
                    Text(text = stringResource(R.string.action_cancel))
                }
            },
        ) {
            DatePicker(state = state)
        }
    }
}

private const val MILLIS_PER_DAY = 86_400_000L

/** The label for a choice: its resource when the schema knows it, else as typed. */
@Composable
internal fun EnumChoice.label(): String =
    labelRes?.let { stringResource(it) } ?: value
