package io.github.sudomegas.saat.ui

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavDestination
import androidx.navigation.NavDestination.Companion.hasRoute
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.toRoute
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import io.github.sudomegas.saat.SaatApplication
import io.github.sudomegas.saat.ui.nav.CalendarRoute
import io.github.sudomegas.saat.ui.nav.DetailRoute
import io.github.sudomegas.saat.ui.nav.FormRoute
import io.github.sudomegas.saat.ui.nav.GridRoute
import io.github.sudomegas.saat.ui.nav.SettingsRoute
import io.github.sudomegas.saat.ui.nav.SpecsRoute
import io.github.sudomegas.saat.ui.nav.TopLevelDestination
import io.github.sudomegas.saat.ui.screens.CalendarScreen
import io.github.sudomegas.saat.ui.screens.DetailScreen
import io.github.sudomegas.saat.ui.screens.FormScreen
import io.github.sudomegas.saat.ui.screens.GridScreen
import io.github.sudomegas.saat.ui.screens.SettingsScreen
import io.github.sudomegas.saat.ui.screens.SpecsScreen

@Composable
fun SaatApp(app: SaatApplication, viewModel: SettingsViewModel) {
    val navController = rememberNavController()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val config by viewModel.config.collectAsStateWithLifecycle()
    val error by viewModel.error.collectAsStateWithLifecycle()

    val gridViewModel: GridViewModel = viewModel(factory = GridViewModel.factory(app))

    // Only the error is collected, not the whole CollectionState: the shell has
    // no interest in the watches themselves, and observing them here would
    // recompose the navigation bar every time the collection changed.
    val writeError by remember(app) {
        app.watchRepository.state
            .map { it.writeError }
            .distinctUntilChanged()
    }.collectAsStateWithLifecycle(initialValue = null)

    val snackbarHostState = remember { SnackbarHostState() }

    // Hard rule 6: never silently swallow an exception. The host is wired from
    // the first commit so AM2 onward has somewhere to report to rather than
    // inventing one per screen.
    LaunchedEffect(error) {
        error?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.clearError()
        }
    }

    // The other half of hard rule 6, and the half AM2 built but had nowhere to
    // put: a failed write leaves the edit in memory and its message in the
    // repository. Until now nothing read it.
    LaunchedEffect(writeError) {
        writeError?.let {
            snackbarHostState.showSnackbar(it)
            app.watchRepository.clearWriteError()
        }
    }

    // SPEC-ANDROID 5.1: detail, form and compare are full screens pushed ABOVE
    // the tabs. Hiding the bar is also the honest answer to "which tab is
    // selected while Detail is open" — none is, and dimming one into a lie was
    // the alternative. `matchesTab` stays exhaustive over the four tabs, and the
    // routes AM4 and AM5 add join the list here rather than there.
    val onFullScreenRoute = backStackEntry?.destination?.hierarchy
        ?.any { node ->
            node.hasRoute(DetailRoute::class) || node.hasRoute(FormRoute::class)
        } == true

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        bottomBar = {
            if (onFullScreenRoute) return@Scaffold
            NavigationBar {
                TopLevelDestination.entries.forEach { destination ->
                    val selected = backStackEntry?.destination?.hierarchy
                        ?.any { node -> node.matchesTab(destination) } == true
                    NavigationBarItem(
                        selected = selected,
                        onClick = {
                            navController.navigate(destination.route) {
                                // Keep one entry per tab and restore where the
                                // user left off, so the system back gesture
                                // always means back and never exit-with-lost-
                                // state (SPEC-ANDROID 5.1).
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = {},
                        label = { Text(stringResource(destination.labelRes)) },
                        alwaysShowLabel = true,
                    )
                }
            }
        },
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = GridRoute,
            modifier = Modifier.padding(innerPadding),
        ) {
            composable<GridRoute> {
                GridScreen(
                    viewModel = gridViewModel,
                    onOpenWatch = { slug -> navController.navigate(DetailRoute(slug)) },
                    onAddWatch = { navController.navigate(FormRoute()) },
                )
            }
            composable<DetailRoute> { entry ->
                val slug = entry.toRoute<DetailRoute>().slug
                // Keyed by slug so opening a second watch from a future
                // cross-link builds its own ViewModel rather than reusing the
                // first one's — a ViewModel is scoped to the back stack entry,
                // and two entries for the same route class would otherwise
                // share a store keyed only by type.
                DetailScreen(
                    viewModel = viewModel(
                        key = slug,
                        factory = DetailViewModel.factory(app, slug),
                    ),
                    snackbarHostState = snackbarHostState,
                    onBack = { navController.popBackStack() },
                    onEdit = { navController.navigate(FormRoute(slug)) },
                )
            }
            composable<FormRoute> { entry ->
                val slug = entry.toRoute<FormRoute>().slug
                FormScreen(
                    viewModel = viewModel(
                        // Keyed so add and edit, and two different edits, never
                        // share a state holder: a ViewModel is scoped to the
                        // back stack entry but stored by type within it.
                        key = slug ?: ADD_WATCH_KEY,
                        factory = FormViewModel.factory(app, slug),
                    ),
                    snackbarHostState = snackbarHostState,
                    onClose = { navController.popBackStack() },
                    onSaved = { saved ->
                        // Adding lands on the new watch's page; editing goes
                        // back to the page it was opened from. Either way the
                        // form is off the stack, so back does not return to it.
                        if (slug == null) {
                            navController.popBackStack()
                            navController.navigate(DetailRoute(saved))
                        } else {
                            navController.popBackStack()
                        }
                    },
                )
            }
            composable<SpecsRoute> { SpecsScreen() }
            composable<CalendarRoute> { CalendarScreen() }
            composable<SettingsRoute> {
                SettingsScreen(
                    config = config,
                    repository = app.watchRepository,
                    onThemeModeChange = viewModel::setThemeMode,
                    onDynamicColorChange = viewModel::setDynamicColor,
                )
            }
        }
    }
}

/** The ViewModel key for the add form, which has no slug to be keyed by. */
private const val ADD_WATCH_KEY = "add"

private fun NavDestination.matchesTab(destination: TopLevelDestination): Boolean =
    when (destination) {
        TopLevelDestination.GRID -> hasRoute(GridRoute::class)
        TopLevelDestination.SPECS -> hasRoute(SpecsRoute::class)
        TopLevelDestination.CALENDAR -> hasRoute(CalendarRoute::class)
        TopLevelDestination.SETTINGS -> hasRoute(SettingsRoute::class)
    }
