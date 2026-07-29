package io.github.sudomegas.saat.config

import dev.eav.tomlkt.Toml
import kotlinx.serialization.Serializable
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import java.io.File

/** The outcome of a load: always a usable config, plus whatever went wrong. */
data class ConfigLoad(
    val config: AppConfig,
    /**
     * Non-null when the file existed but could not be read or parsed. The
     * config is the default in that case — the app stays usable — but the
     * failure is carried out to the UI rather than logged and forgotten.
     * SPEC-ANDROID hard rule 6.
     */
    val error: String? = null,
)

/**
 * Reads and writes `config.toml`.
 *
 * Takes its root directory by injection rather than a `Context` so the tests
 * are plain JVM JUnit against a temp directory — no Robolectric, and no
 * fixture files committed to the repository (hard rule 1).
 *
 * The file shape mirrors the desktop's `config.toml` convention of one table
 * per concern. `[language] code` matches the desktop key exactly, since that is
 * the one setting both apps genuinely share. Theme does not: the desktop stores
 * `[palette] id` naming one of ten presets, and Android has System/Light/Dark
 * plus a dynamic-colour switch instead. Pretending those are the same key would
 * be a false parity.
 */
class ConfigStore(root: File) {

    private val file = File(root, FILE_NAME)

    // explicitNulls = false is required, not a preference: TOML has no null
    // literal, and tomlkt's default emits `key = null` for absent optionals —
    // a file no TOML parser will read back, including this one. See
    // TomlContractTest, which is where that was measured.
    private val toml = Toml {
        ignoreUnknownKeys = true
        explicitNulls = false
    }

    @Serializable
    private data class ThemeSection(
        val mode: String? = null,
        val dynamic_color: Boolean? = null,
    )

    @Serializable
    private data class LanguageSection(val code: String? = null)

    @Serializable
    private data class ConfigDto(
        val theme: ThemeSection? = null,
        val language: LanguageSection? = null,
    )

    fun load(): ConfigLoad {
        if (!file.exists()) return ConfigLoad(AppConfig())

        return try {
            val dto = toml.decodeFromString<ConfigDto>(file.readText())
            ConfigLoad(
                AppConfig(
                    themeMode = dto.theme?.mode?.toThemeMode() ?: ThemeMode.SYSTEM,
                    dynamicColor = dto.theme?.dynamic_color ?: true,
                    language = dto.language?.code ?: AppConfig.DEFAULT_LANGUAGE,
                )
            )
        } catch (e: Exception) {
            // Defaults so the app still starts, and the message intact so the
            // UI can show it. Never a silent fallback.
            ConfigLoad(AppConfig(), "${file.name}: ${e.message ?: e::class.simpleName}")
        }
    }

    /** @throws Exception if the write fails; the caller surfaces it. */
    fun save(config: AppConfig) {
        val dto = ConfigDto(
            theme = ThemeSection(
                mode = config.themeMode.name.lowercase(),
                dynamic_color = config.dynamicColor,
            ),
            language = LanguageSection(code = config.language),
        )
        writeAtomically(file, toml.encodeToString(dto))
    }

    private fun String.toThemeMode(): ThemeMode? {
        val value = this
        return ThemeMode.entries.firstOrNull { it.name.equals(value, ignoreCase = true) }
    }

    companion object {
        const val FILE_NAME = "config.toml"
    }
}
