package io.github.sudomegas.saat.config

import io.github.sudomegas.saat.storage.WatchSort
import io.github.sudomegas.saat.ui.specs.SpecsPreset

/** Theme choice, per SPEC-ANDROID 5.10. Stored in `config.toml`. */
enum class ThemeMode { SYSTEM, LIGHT, DARK }

/**
 * Everything `config.toml` holds. SPEC-ANDROID 3 names theme, language, last
 * view and sort choices; [sort] arrived with AM3, the milestone that owns the
 * grid's sort menu, and [specsPreset] with AM6. Last view still waits for the
 * screen that owns it.
 *
 * [language] is written from AM1 even though nothing reads it until AM11.
 * SPEC-ANDROID hard rule 7 requires that the app never infer its language from
 * the system locale, and on Android that is not a default you inherit — Android
 * resource resolution follows the system locale the moment `values-tr/` exists.
 * So the English default has to be recorded explicitly on first run and
 * re-applied at every process start. Owning the key from the first commit means
 * AM11 adds a language *picker*, not a migration.
 */
data class AppConfig(
    val themeMode: ThemeMode = ThemeMode.SYSTEM,
    val dynamicColor: Boolean = true,
    val language: String = DEFAULT_LANGUAGE,
    val sort: WatchSort = WatchSort.DEFAULT,
    /** The Specs list's active preset — AM6, SPEC-ANDROID 5.3. */
    val specsPreset: SpecsPreset = SpecsPreset.DEFAULT,
) {
    companion object {
        const val DEFAULT_LANGUAGE = "en"
    }
}
