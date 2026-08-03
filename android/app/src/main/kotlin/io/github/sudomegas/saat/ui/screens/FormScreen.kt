package io.github.sudomegas.saat.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.ui.FormViewModel
import io.github.sudomegas.saat.ui.form.ACCURACY_UNITS
import io.github.sudomegas.saat.ui.form.BEZELS
import io.github.sudomegas.saat.ui.form.CASEBACKS
import io.github.sudomegas.saat.ui.form.CASE_MATERIALS
import io.github.sudomegas.saat.ui.form.COMPLICATIONS
import io.github.sudomegas.saat.ui.form.CONDITIONS
import io.github.sudomegas.saat.ui.form.CROWNS
import io.github.sudomegas.saat.ui.form.CRYSTALS
import io.github.sudomegas.saat.ui.form.EnumChoice
import io.github.sudomegas.saat.ui.form.GROUPS
import io.github.sudomegas.saat.ui.form.INDICES
import io.github.sudomegas.saat.ui.form.MOVEMENT_KINDS
import io.github.sudomegas.saat.ui.form.STATUSES
import io.github.sudomegas.saat.ui.form.STRAP_MATERIALS
import io.github.sudomegas.saat.ui.form.STYLES
import io.github.sudomegas.saat.ui.form.WatchFormState
import io.github.sudomegas.saat.ui.form.existingListValues
import io.github.sudomegas.saat.ui.form.existingValues
import io.github.sudomegas.saat.ui.form.plusExisting
import kotlinx.coroutines.launch

/**
 * Add and edit — SPEC-ANDROID 5.7.
 *
 * ONE SCROLLING PAGE with collapsible group headers, in spec order. Not tabs and
 * not a wizard, and the spec gives the reason: "Tabs on a phone hide what is
 * unfilled; a scroll shows the whole shape of the record." The same screen
 * serves both operations, so there is one layout to keep right rather than two
 * that drift.
 *
 * A plain `Column` with `verticalScroll` rather than a `LazyColumn`, which is
 * the opposite of the detail page's choice and for the opposite reason: a lazy
 * list disposes the composables that scroll off it, and a text field that is
 * disposed loses its cursor position and its IME state. The form is bounded —
 * nine groups and their rows — so composing all of it is affordable, and it is
 * the only version where scrolling back to a field finds it as you left it.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FormScreen(
    viewModel: FormViewModel,
    snackbarHostState: SnackbarHostState,
    onClose: () -> Unit,
    onSaved: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val isReady by viewModel.isReady.collectAsStateWithLifecycle()
    val collection by viewModel.collection.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    val backLabel = stringResource(R.string.action_back)

    var confirmingDiscard by rememberSaveable { mutableStateOf(false) }

    // SPEC-ANDROID 5.7: "Backing out with unsaved changes prompts." Both ways
    // out are the same way out — the system back gesture and the top bar's
    // arrow — because a prompt one of them skips is a prompt that does not
    // exist.
    val leave = { if (viewModel.isDirty) confirmingDiscard = true else onClose() }
    BackHandler(enabled = true) { leave() }

    Scaffold(
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = stringResource(
                            if (viewModel.isEditing) R.string.screen_form_title_edit
                            else R.string.screen_form_title_add
                        ),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                },
                navigationIcon = {
                    IconButton(
                        onClick = leave,
                        modifier = Modifier.semantics { contentDescription = backLabel },
                    ) {
                        BackChevron(tint = MaterialTheme.colorScheme.onSurface)
                    }
                },
                actions = {
                    TextButton(
                        // The ONLY thing that can block a save: brand and model.
                        // SPEC-ANDROID 5.7 is explicit that nothing else may.
                        enabled = state.canSave && isReady,
                        onClick = {
                            scope.launch {
                                val slug = viewModel.save()
                                if (slug != null) onSaved(slug)
                            }
                        },
                    ) {
                        Text(text = stringResource(R.string.action_save))
                    }
                },
            )
        },
        modifier = modifier,
    ) { innerPadding ->
        FormBody(
            state = state,
            collection = collection,
            onChange = viewModel::update,
            contentPadding = innerPadding,
        )
    }

    if (confirmingDiscard) {
        AlertDialog(
            onDismissRequest = { confirmingDiscard = false },
            title = { Text(text = stringResource(R.string.screen_form_discard_title)) },
            text = { Text(text = stringResource(R.string.screen_form_discard_body)) },
            confirmButton = {
                TextButton(onClick = {
                    confirmingDiscard = false
                    onClose()
                }) {
                    Text(
                        text = stringResource(R.string.action_discard),
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            },
            // Staying in the form is the safe answer, so it is the one on the
            // right — the desktop makes Cancel the default button for the same
            // reason. Nothing here throws work away by accident.
            dismissButton = {
                TextButton(onClick = { confirmingDiscard = false }) {
                    Text(text = stringResource(R.string.action_keep_editing))
                }
            },
        )
    }
}

@Composable
private fun FormBody(
    state: WatchFormState,
    collection: List<Watch>,
    onChange: ((WatchFormState) -> WatchFormState) -> Unit,
    contentPadding: PaddingValues,
) {
    // Which groups are open survives rotation but is not persisted further: it
    // is a reading position, not a preference.
    val open = rememberSaveable(saver = OpenGroupsSaver) { mutableStateOf(ALL_GROUPS) }
    fun toggle(group: String) {
        open.value = if (group in open.value) open.value - group else open.value + group
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(contentPadding)
            .verticalScroll(rememberScrollState()),
    ) {
        FormSection(R.string.screen_form_group_identity, IDENTITY in open.value, { toggle(IDENTITY) }) {
            FormText(R.string.field_brand, state.brand, { v -> onChange { it.copy(brand = v) } })
            FormText(R.string.field_model, state.model, { v -> onChange { it.copy(model = v) } })
            FormText(R.string.field_reference, state.reference, { v -> onChange { it.copy(reference = v) } })
            FormText(R.string.field_nickname, state.nickname, { v -> onChange { it.copy(nickname = v) } })
            FormText(R.string.field_serial, state.serial, { v -> onChange { it.copy(serial = v) } })
            FormEnum(
                R.string.field_group,
                state.group,
                GROUPS.plusExisting(existingValues(collection) { it.group }),
                { v -> onChange { it.copy(group = v) } },
            )
            FormEnum(
                R.string.field_style,
                state.style,
                STYLES.plusExisting(existingValues(collection) { it.style }),
                { v -> onChange { it.copy(style = v) } },
            )
            FormFixedEnum(R.string.field_status, state.status, STATUSES) { v ->
                onChange { it.copy(status = v) }
            }
            FormText(R.string.field_storage, state.storage, { v -> onChange { it.copy(storage = v) } })
            FormInt(R.string.field_rating, state.rating, { v -> onChange { it.copy(rating = v) } })
            StringListEditor(R.string.field_tags, state.tags, emptyList()) { v ->
                onChange { it.copy(tags = v) }
            }
        }

        FormSection(R.string.screen_form_group_movement, MOVEMENT in open.value, { toggle(MOVEMENT) }) {
            FormText(R.string.field_caliber, state.caliber, { v -> onChange { it.copy(caliber = v) } })
            FormEnum(
                R.string.field_kind,
                state.kind,
                MOVEMENT_KINDS.plusExisting(existingValues(collection) { it.movement.kind }),
                { v -> onChange { it.copy(kind = v) } },
            )
            // SPEC-ANDROID 5.7: the group swaps power reserve for battery life
            // when kind is Quartz or Solar. Neither value is cleared by the
            // swap — a Mecha-quartz owner who filled both keeps both, and the
            // detail page shows whichever is recorded.
            if (state.usesBattery) {
                FormDecimal(
                    R.string.field_battery_life,
                    state.batteryLifeYears,
                    { v -> onChange { it.copy(batteryLifeYears = v) } },
                    suffixRes = R.string.field_suffix_years,
                )
            } else {
                FormDecimal(
                    R.string.field_power_reserve,
                    state.powerReserveHours,
                    { v -> onChange { it.copy(powerReserveHours = v) } },
                    suffixRes = R.string.field_suffix_hours,
                )
            }
            FormDecimal(
                R.string.field_accuracy_min,
                state.accuracyMin,
                { v -> onChange { it.copy(accuracyMin = v) } },
                suffixRes = R.string.field_suffix_sec,
                signed = true,
            )
            FormDecimal(
                R.string.field_accuracy_max,
                state.accuracyMax,
                { v -> onChange { it.copy(accuracyMax = v) } },
                suffixRes = R.string.field_suffix_sec,
                signed = true,
            )
            FormEnum(
                R.string.field_accuracy_unit,
                state.accuracyUnit,
                ACCURACY_UNITS,
                { v -> onChange { it.copy(accuracyUnit = v) } },
            )
            FormInt(R.string.field_jewels, state.jewels, { v -> onChange { it.copy(jewels = v) } })
            FormInt(
                R.string.field_frequency,
                state.bph,
                { v -> onChange { it.copy(bph = v) } },
                suffixRes = R.string.field_suffix_bph,
            )
            FormTristate(R.string.field_hacking, state.hacking) { v -> onChange { it.copy(hacking = v) } }
            FormTristate(R.string.field_handwinding, state.handwinding) { v ->
                onChange { it.copy(handwinding = v) }
            }
            FormText(R.string.field_origin, state.origin, { v -> onChange { it.copy(origin = v) } })
        }

        FormSection(R.string.screen_form_group_case, CASE in open.value, { toggle(CASE) }) {
            FormDecimal(
                R.string.field_diameter, state.diameterMm,
                { v -> onChange { it.copy(diameterMm = v) } }, R.string.field_suffix_mm,
            )
            FormDecimal(
                R.string.field_lug_to_lug, state.lugToLugMm,
                { v -> onChange { it.copy(lugToLugMm = v) } }, R.string.field_suffix_mm,
            )
            FormDecimal(
                R.string.field_thickness, state.thicknessMm,
                { v -> onChange { it.copy(thicknessMm = v) } }, R.string.field_suffix_mm,
            )
            FormInt(
                R.string.field_lug_width, state.lugWidthMm,
                { v -> onChange { it.copy(lugWidthMm = v) } }, R.string.field_suffix_mm,
            )
            FormEnum(
                R.string.field_case_material,
                state.caseMaterial,
                CASE_MATERIALS.plusExisting(existingValues(collection) { it.case.material }),
                { v -> onChange { it.copy(caseMaterial = v) } },
            )
            FormEnum(
                R.string.field_crystal,
                state.crystal,
                CRYSTALS.plusExisting(existingValues(collection) { it.case.crystal }),
                { v -> onChange { it.copy(crystal = v) } },
            )
            FormEnum(
                R.string.field_crown,
                state.crown,
                CROWNS.plusExisting(existingValues(collection) { it.case.crown }),
                { v -> onChange { it.copy(crown = v) } },
            )
            FormEnum(
                R.string.field_bezel,
                state.bezel,
                BEZELS.plusExisting(existingValues(collection) { it.case.bezel }),
                { v -> onChange { it.copy(bezel = v) } },
            )
            FormEnum(
                R.string.field_caseback,
                state.caseback,
                CASEBACKS.plusExisting(existingValues(collection) { it.case.caseback }),
                { v -> onChange { it.copy(caseback = v) } },
            )
            // Accepts m, bar or atm and stores metres — SPEC-ANDROID 5.7. The
            // unit is a choice beside the figure rather than three fields,
            // because the file only ever holds one of them.
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Box(modifier = Modifier.weight(2f)) {
                    FormInt(
                        R.string.field_water_resistance,
                        state.waterResistance,
                        { v -> onChange { it.copy(waterResistance = v) } },
                    )
                }
                Box(modifier = Modifier.weight(1f)) {
                    FormFixedEnum(
                        R.string.field_water_resistance_unit,
                        state.waterResistanceUnit,
                        // Not translated: these are unit tokens the conversion
                        // table is keyed on, not vocabulary.
                        WatchFormState.WATER_RESISTANCE_UNITS.map { EnumChoice(it) },
                    ) { v -> onChange { it.copy(waterResistanceUnit = v) } }
                }
            }
            FormDecimal(
                R.string.field_weight, state.weightG,
                { v -> onChange { it.copy(weightG = v) } }, R.string.field_suffix_grams,
            )
        }

        FormSection(R.string.screen_form_group_dial, DIAL in open.value, { toggle(DIAL) }) {
            FormText(R.string.field_dial_colour, state.dialColour, { v -> onChange { it.copy(dialColour = v) } })
            FormText(R.string.field_dial_material, state.dialMaterial, { v -> onChange { it.copy(dialMaterial = v) } })
            FormEnum(
                R.string.field_indices,
                state.indices,
                INDICES.plusExisting(existingValues(collection) { it.dial.indices }),
                { v -> onChange { it.copy(indices = v) } },
            )
            FormText(R.string.field_lume, state.lume, { v -> onChange { it.copy(lume = v) } })
            StringListEditor(
                R.string.field_complications,
                state.complications,
                COMPLICATIONS.plusExisting(existingListValues(collection) { it.dial.complications }),
            ) { v -> onChange { it.copy(complications = v) } }
        }

        FormSection(R.string.screen_form_group_straps, STRAPS in open.value, { toggle(STRAPS) }) {
            StrapsEditor(
                straps = state.straps,
                materials = STRAP_MATERIALS.plusExisting(
                    existingListValues(collection) { watch -> watch.straps.mapNotNull { it.material } },
                ),
                images = state.images,
            ) { v -> onChange { it.copy(straps = v) } }
        }

        FormSection(R.string.screen_form_group_acquisition, ACQUISITION in open.value, { toggle(ACQUISITION) }) {
            FormDate(R.string.field_acquired, state.acquiredOn) { v -> onChange { it.copy(acquiredOn = v) } }
            FormDecimal(R.string.field_price, state.price, { v -> onChange { it.copy(price = v) } })
            FormDecimal(R.string.field_target_price, state.targetPrice, { v -> onChange { it.copy(targetPrice = v) } })
            FormDate(R.string.field_target_date, state.targetDate) { v -> onChange { it.copy(targetDate = v) } }
            FormText(R.string.field_currency, state.currency, { v -> onChange { it.copy(currency = v) } })
            FormEnum(
                R.string.field_seller,
                state.seller,
                // No suggestion list of its own: sellers.toml is a desktop
                // concept SPEC-ANDROID never adopted, so the only suggestions
                // are the sellers this collection already names.
                emptyList<EnumChoice>().plusExisting(existingValues(collection) { it.acquisition.seller }),
                { v -> onChange { it.copy(seller = v) } },
            )
            FormText(R.string.field_url, state.url, { v -> onChange { it.copy(url = v) } })
            FormEnum(
                R.string.field_condition,
                state.condition,
                CONDITIONS,
                onChange = { v -> onChange { it.copy(condition = v) } },
            )
            FormTristate(R.string.field_box_and_papers, state.boxAndPapers) { v ->
                onChange { it.copy(boxAndPapers = v) }
            }
            FormDate(R.string.field_warranty_until, state.warrantyUntil) { v ->
                onChange { it.copy(warrantyUntil = v) }
            }
        }

        FormSection(R.string.screen_form_group_maintenance, MAINTENANCE in open.value, { toggle(MAINTENANCE) }) {
            FormDecimal(
                R.string.field_service_interval, state.serviceIntervalYears,
                { v -> onChange { it.copy(serviceIntervalYears = v) } }, R.string.field_suffix_years,
            )
            FormDate(R.string.field_battery_due, state.batteryDue) { v -> onChange { it.copy(batteryDue = v) } }
        }

        FormSection(R.string.screen_form_group_log, LOG in open.value, { toggle(LOG) }) {
            LogEditor(state.log) { v -> onChange { it.copy(log = v) } }
        }

        FormSection(R.string.screen_form_group_timing, TIMING in open.value, { toggle(TIMING) }) {
            TimingEditor(state.timing) { v -> onChange { it.copy(timing = v) } }
        }

        FormSection(R.string.screen_form_group_notes, NOTES in open.value, { toggle(NOTES) }) {
            FormText(
                R.string.field_notes,
                state.notes,
                { v -> onChange { it.copy(notes = v) } },
                singleLine = false,
            )
        }

        Box(Modifier.height(32.dp))
    }
}

private const val IDENTITY = "identity"
private const val MOVEMENT = "movement"
private const val CASE = "case"
private const val DIAL = "dial"
private const val STRAPS = "straps"
private const val ACQUISITION = "acquisition"
private const val MAINTENANCE = "maintenance"
private const val LOG = "log"
private const val TIMING = "timing"
private const val NOTES = "notes"

/**
 * Every group open to begin with. A form that starts collapsed hides the shape
 * of the record, which is the one thing SPEC-ANDROID 5.7 chose a scroll over
 * tabs to show.
 */
private val ALL_GROUPS = setOf(
    IDENTITY, MOVEMENT, CASE, DIAL, STRAPS, ACQUISITION, MAINTENANCE, LOG, TIMING, NOTES,
)

/** A `Set<String>` is not one of the types the default saver handles. */
private val OpenGroupsSaver =
    androidx.compose.runtime.saveable.listSaver<androidx.compose.runtime.MutableState<Set<String>>, String>(
        save = { it.value.toList() },
        restore = { androidx.compose.runtime.mutableStateOf(it.toSet()) },
    )
