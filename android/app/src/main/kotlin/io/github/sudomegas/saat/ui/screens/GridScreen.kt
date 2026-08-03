package io.github.sudomegas.saat.ui.screens

import android.content.res.Configuration
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.storage.FacetKind
import io.github.sudomegas.saat.ui.GridViewModel
import io.github.sudomegas.saat.ui.WatchCard

/**
 * The collection.
 *
 * Owns its own `Scaffold` rather than borrowing the shell's. The floating action
 * button — and, from AM3b, the search field and sort menu — are chrome bound to
 * THIS screen's state, and hoisting them into `SaatApp` would make the shell
 * depend on this ViewModel now and on a Specs ViewModel in AM6. A screen that
 * owns its chrome also cannot forget to declare it, which a `when` over routes
 * in the shell would invite at every milestone that adds a destination.
 */
@Composable
fun GridScreen(
    viewModel: GridViewModel,
    onOpenWatch: (String) -> Unit,
    onAddWatch: () -> Unit,
    onOpenFilters: () -> Unit,
    onRemoveFilter: (FacetKind, String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    Scaffold(
        // The shell's Scaffold already consumed the system bars — MainActivity
        // calls enableEdgeToEdge — so a nested default would count them twice.
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            // Nothing to search or sort in an empty collection, and the empty
            // state is specified to be quiet.
            if (!state.isCollectionEmpty) {
                GridTopBar(
                    query = state.query,
                    sort = state.sort,
                    onQueryChange = viewModel::setQuery,
                    onSortChange = viewModel::setSort,
                    onOpenFilters = onOpenFilters,
                    hasActiveFilters = !state.filter.isEmpty,
                )
            }
        },
        floatingActionButton = {
            // SPEC-ANDROID 5.1 calls the FAB "the one primary-weight control in
            // the app". While the collection is empty the empty state's own
            // button IS that control, so showing both would put two of them on
            // the quietest screen in the app.
            if (!state.isCollectionEmpty) {
                ExtendedFloatingActionButton(onClick = onAddWatch) {
                    Text(text = stringResource(R.string.action_add_watch))
                }
            }
        },
        modifier = modifier,
    ) { innerPadding ->
        Column(modifier = Modifier.padding(innerPadding)) {
            LoadFailureNotice(
                failures = state.failures,
                onDismiss = viewModel::dismissFailures,
            )

            ActiveFilterChips(filter = state.filter, onRemove = onRemoveFilter)

            when {
                // Not read yet. Deliberately blank rather than the empty state:
                // "you have no watches" and "we have not looked yet" are
                // different claims, and CollectionState.isLoaded exists so the
                // grid never has to guess which one is true.
                !state.isLoaded -> Unit

                state.isCollectionEmpty ->
                    CollectionEmptyState(onAddWatch = onAddWatch)

                // A search that found nothing is NOT the collection being empty.
                // Offering "add your first watch" here would be the app lying
                // about what it holds.
                state.hasNoMatches -> Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(32.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = stringResource(R.string.screen_grid_no_matches),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                    )
                }

                else -> WatchGrid(cards = state.cards, onOpenWatch = onOpenWatch)
            }
        }
    }
}

@Composable
private fun WatchGrid(cards: List<WatchCard>, onOpenWatch: (String) -> Unit) {
    // Two portrait, three landscape (SPEC-ANDROID 5.2). Keyed off orientation
    // rather than a width breakpoint, and with no upper clamp, so a tablet in
    // landscape is never capped at two.
    val landscape =
        LocalConfiguration.current.orientation == Configuration.ORIENTATION_LANDSCAPE
    val columns = if (landscape) 3 else 2

    LazyVerticalGrid(
        columns = GridCells.Fixed(columns),
        // The bottom inset clears the extended FAB, which floats above the
        // content and would otherwise sit on the last row.
        contentPadding = PaddingValues(start = 12.dp, top = 12.dp, end = 12.dp, bottom = 88.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        modifier = Modifier.fillMaxSize(),
    ) {
        items(items = cards, key = { it.slug }) { card ->
            WatchGridCard(card = card, onOpen = onOpenWatch)
        }
    }
}
