package io.github.sudomegas.saat.ui.screens

import androidx.compose.runtime.Composable
import io.github.sudomegas.saat.storage.WatchRepository

/**
 * The release twin of the debug developer section: nothing at all.
 *
 * SPEC-ANDROID hard rule 1 — "release APKs ship empty, always". The demo-watch
 * generator lives in `src/debug` and is therefore not compiled into this
 * variant; this file exists so that `SettingsScreen`, which is shared, still has
 * a `DeveloperSection` to call.
 *
 * An empty body rather than a flag check, deliberately. `isMinifyEnabled` is
 * false for release, so a `BuildConfig.DEBUG` guard would leave the generator
 * and its strings sitting in the shipped DEX, unreachable but present — and a
 * test could then only ever assert "present but disabled", which is not what the
 * rule asks anyone to prove.
 */
@Composable
@Suppress("UNUSED_PARAMETER")
fun DeveloperSection(repository: WatchRepository) = Unit
