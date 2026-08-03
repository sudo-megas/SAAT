package io.github.sudomegas.saat.ui.screens

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.storage.WatchSort

/**
 * Search and sort, per SPEC-ANDROID 5.1: "a top app bar on Grid and Specs
 * carries search and the sort menu".
 *
 * Text rather than icons throughout. `material-icons-core` is not on the
 * classpath — the Compose BOM pins a version but `material3` does not depend on
 * it — and adding an artifact to draw a magnifying glass is a poor trade against
 * a design language whose stated rule is "no decoration beyond Material
 * defaults". AM4's back affordance is the first control that will genuinely need
 * one, and that is the milestone to decide it in.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GridTopBar(
    query: String,
    sort: WatchSort,
    onQueryChange: (String) -> Unit,
    onSortChange: (WatchSort) -> Unit,
    /** AM6b: the sheet is reachable from the top bar on Grid AND Specs. */
    onOpenFilters: () -> Unit,
    /** Tinted while anything is filtered, so a closed sheet is never silent. */
    hasActiveFilters: Boolean,
) {
    TopAppBar(
        title = {
            TextField(
                value = query,
                onValueChange = onQueryChange,
                placeholder = { Text(text = stringResource(R.string.action_search)) },
                singleLine = true,
                // ImeAction.Search rather than Done: the filtering is already
                // live, so the key only dismisses the keyboard, but naming it
                // correctly is what a screen reader announces.
                keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(
                    imeAction = ImeAction.Search,
                ),
                trailingIcon = {
                    if (query.isNotEmpty()) {
                        TextButton(onClick = { onQueryChange("") }) {
                            Text(text = stringResource(R.string.action_clear_search))
                        }
                    }
                },
                // The field is the bar's title, so it must not paint its own
                // container or the bar grows a second surface inside itself.
                colors = TextFieldDefaults.colors(
                    focusedContainerColor = Color.Transparent,
                    unfocusedContainerColor = Color.Transparent,
                    disabledContainerColor = Color.Transparent,
                    focusedIndicatorColor = Color.Transparent,
                    unfocusedIndicatorColor = Color.Transparent,
                ),
                modifier = Modifier.fillMaxWidth(),
            )
        },
        actions = {
            TextButton(onClick = onOpenFilters) {
                Text(
                    text = stringResource(R.string.action_filter),
                    // The one accent the palette has, which SaatRoles already
                    // names for active filters. The chips below the bar say
                    // WHAT is filtered; this says THAT something is.
                    color = if (hasActiveFilters) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
                )
            }
            SortMenu(sort = sort, onSortChange = onSortChange)
        },
    )
}

@Composable
private fun SortMenu(sort: WatchSort, onSortChange: (WatchSort) -> Unit) {
    var expanded by remember { mutableStateOf(false) }

    TextButton(onClick = { expanded = true }) {
        Text(
            text = stringResource(sort.labelRes()),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }

    DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
        WatchSort.entries.forEach { option ->
            DropdownMenuItem(
                text = {
                    Text(
                        text = stringResource(option.labelRes()),
                        // The active order is tinted with the one accent the
                        // palette has; SaatRoles names gilt for "active filters".
                        color = if (option == sort) {
                            MaterialTheme.colorScheme.primary
                        } else {
                            MaterialTheme.colorScheme.onSurface
                        },
                    )
                },
                onClick = {
                    expanded = false
                    onSortChange(option)
                },
            )
        }
    }
}

/**
 * `WatchSort` lives in `storage/` and holds no resource id — the storage layer
 * has no business knowing about `R`. The mapping is exhaustive, so adding an
 * order without a label will not compile.
 */
private fun WatchSort.labelRes(): Int = when (this) {
    WatchSort.BRAND -> R.string.action_sort_brand
    WatchSort.MODEL -> R.string.action_sort_model
    WatchSort.ACQUIRED -> R.string.action_sort_acquired
    WatchSort.LEAST_WORN -> R.string.action_sort_least_worn
}
