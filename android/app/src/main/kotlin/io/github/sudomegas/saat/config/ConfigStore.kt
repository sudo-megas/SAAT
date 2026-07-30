package io.github.sudomegas.saat.config

import dev.eav.tomlkt.Toml
import io.github.sudomegas.saat.storage.writeAtomically
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
            ConfigLoad(decode(file.readText()))
        } catch (e: Exception) {
            // Defaults so the app still starts, and the message intact so the
            // UI can show it. Never a silent fallback.
            ConfigLoad(AppConfig(), "${file.name}: ${e.message ?: e::class.simpleName}")
        }
    }

    /** @throws Exception if the write fails; the caller surfaces it. */
    fun save(config: AppConfig) {
        setAsideIfUnreadable()

        val dto = ConfigDto(
            theme = ThemeSection(
                mode = config.themeMode.name.lowercase(),
                dynamic_color = config.dynamicColor,
            ),
            language = LanguageSection(code = config.language),
        )
        writeAtomically(file, toml.encodeToString(dto))
    }

    private fun decode(text: String): AppConfig {
        // The BOM is stripped rather than tolerated because it cannot be: this
        // parser rejects a leading U+FEFF, and a config that gains one from a
        // Windows editor is otherwise a valid file that silently reads as no
        // file at all — and would now be set aside as broken when it is not.
        // The desktop reads its own config as `utf-8-sig` for exactly this, and
        // reads `watch.toml` as plain `utf-8`; the asymmetry is theirs and this
        // matches both halves of it.
        val dto = toml.decodeFromString<ConfigDto>(text.removePrefix(BOM))
        return AppConfig(
            themeMode = dto.theme?.mode?.toThemeMode() ?: ThemeMode.SYSTEM,
            dynamicColor = dto.theme?.dynamic_color ?: true,
            language = dto.language?.code ?: AppConfig.DEFAULT_LANGUAGE,
        )
    }

    /**
     * Move a `config.toml` this app cannot read out of the way, rather than
     * writing defaults over it.
     *
     * [load] answers a broken file with defaults so the app still starts — and
     * the next setting the owner touches used to write those defaults straight
     * over the file, taking their language and theme with it. There is no
     * `backups/` snapshot behind this one the way there is behind a `watch.toml`,
     * so those bytes were simply gone, over a typo they had not fixed yet.
     *
     * The alternative — refuse to save until the file is repaired — leaves the
     * app unable to change its own theme over a file most owners will never have
     * opened. Moving aside is what deletion already does elsewhere in the app:
     * never erase, put it somewhere it can be read.
     *
     * Asked at save time rather than remembered from [load], so it holds however
     * this store is called, including without a load first.
     */
    private fun setAsideIfUnreadable() {
        if (!file.exists()) return
        if (runCatching { decode(file.readText()) }.isSuccess) return

        val rescued = rescuePath()
        // A rename is one syscall and keeps no second copy. If it fails, a copy
        // is enough — the write below replaces the original either way. If BOTH
        // fail this throws, and not writing is the right outcome: the caller
        // surfaces it, and nothing was destroyed to get there.
        if (!file.renameTo(rescued)) file.copyTo(rescued)
    }

    /** `config.toml.broken`, then `-2`: a second break never lands on the first. */
    private fun rescuePath(): File {
        var candidate = File(file.parentFile, "$FILE_NAME$BROKEN_SUFFIX")
        var n = 2
        while (candidate.exists()) {
            candidate = File(file.parentFile, "$FILE_NAME$BROKEN_SUFFIX-$n")
            n += 1
        }
        return candidate
    }

    private fun String.toThemeMode(): ThemeMode? {
        val value = this
        return ThemeMode.entries.firstOrNull { it.name.equals(value, ignoreCase = true) }
    }

    companion object {
        const val FILE_NAME = "config.toml"

        /** What an unreadable `config.toml` is renamed to instead of being replaced. */
        const val BROKEN_SUFFIX = ".broken"

        /** Escaped rather than typed: a literal BOM in this file would be invisible. */
        private const val BOM = "\uFEFF"
    }
}
