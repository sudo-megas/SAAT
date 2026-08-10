package io.github.sudomegas.saat

import io.github.sudomegas.saat.config.AppConfig
import io.github.sudomegas.saat.config.ConfigStore
import io.github.sudomegas.saat.config.ThemeMode
import io.github.sudomegas.saat.storage.PickerMode
import io.github.sudomegas.saat.storage.WatchSort
import io.github.sudomegas.saat.storage.writeAtomically
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

/**
 * Fixtures are built in a temp directory at runtime and deleted afterwards —
 * SPEC-ANDROID hard rule 1 applies to test assets exactly as it applies to
 * shipped code, so nothing here is a committed file.
 */
class ConfigStoreTest {

    @get:Rule
    val temp = TemporaryFolder()

    private fun store() = ConfigStore(temp.root)

    @Test
    fun `absent config yields defaults and no error`() {
        val loaded = store().load()
        assertEquals(AppConfig(), loaded.config)
        assertNull("a missing file is not an error — it is first launch", loaded.error)
    }

    @Test
    fun `round-trips every setting`() {
        val written = AppConfig(
            themeMode = ThemeMode.DARK,
            dynamicColor = false,
            language = "tr",
        )
        store().save(written)
        assertEquals(written, store().load().config)
    }

    @Test
    fun `writes a file the desktop's table convention would recognise`() {
        store().save(AppConfig(themeMode = ThemeMode.LIGHT, dynamicColor = true, language = "en"))
        val text = File(temp.root, ConfigStore.FILE_NAME).readText()

        assertTrue("expected a [theme] table, got:\n$text", text.contains("[theme]"))
        assertTrue("expected a [language] table, got:\n$text", text.contains("[language]"))
        // `[language] code` is the one key the desktop also uses, deliberately
        // spelled the same way.
        assertTrue("expected `code =`, got:\n$text", Regex("""code\s*=\s*"en"""").containsMatchIn(text))
        assertTrue("TOML has no null literal", !Regex("""=\s*null\b""").containsMatchIn(text))
    }

    @Test
    fun `a malformed config falls back to defaults and surfaces the error`() {
        File(temp.root, ConfigStore.FILE_NAME).writeText("this is not = = valid toml [[[")

        val loaded = store().load()
        assertEquals("the app must still start", AppConfig(), loaded.config)
        assertNotNull("hard rule 6: never swallow it silently", loaded.error)
        assertTrue(
            "the message must name the file: ${loaded.error}",
            loaded.error!!.contains(ConfigStore.FILE_NAME),
        )
    }

    @Test
    fun `a config that will not parse is set aside, not written over`() {
        // load() answers a broken file with defaults so the app still starts,
        // and the next setting the owner touches used to write those defaults
        // straight over the file. There is no backups/ snapshot behind this one
        // the way there is behind a watch.toml, so the language and theme they
        // had chosen were simply gone, over a typo not yet fixed.
        val broken = "[language]\ncode = \"tr\"\n[theme]\nmode = \"dark\"\nthis is not toml\n"
        val file = File(temp.root, ConfigStore.FILE_NAME)
        file.writeText(broken)

        val store = store()
        assertNotNull(store.load().error)
        store.save(AppConfig(themeMode = ThemeMode.LIGHT))

        val rescued = File(temp.root, ConfigStore.FILE_NAME + ConfigStore.BROKEN_SUFFIX)
        assertTrue("the unreadable file must still exist somewhere", rescued.exists())
        assertEquals("and it must be the bytes the owner had", broken, rescued.readText())
        assertEquals(ThemeMode.LIGHT, store.load().config.themeMode)
    }

    @Test
    fun `a readable config is replaced in place, with nothing set aside`() {
        val store = store()
        store.save(AppConfig(themeMode = ThemeMode.DARK, language = "tr"))
        store.save(AppConfig(themeMode = ThemeMode.LIGHT, language = "tr"))

        assertEquals(
            "an ordinary save must not leave rescue files scattered around",
            listOf(ConfigStore.FILE_NAME),
            temp.root.listFiles().orEmpty().map { it.name },
        )
        assertEquals(ThemeMode.LIGHT, store.load().config.themeMode)
    }

    @Test
    fun `a second broken config does not land on the first rescue`() {
        val file = File(temp.root, ConfigStore.FILE_NAME)

        file.writeText("first break, code = \"tr\" [[[")
        store().save(AppConfig(themeMode = ThemeMode.DARK))

        file.writeText("second break, code = \"de\" [[[")
        store().save(AppConfig(themeMode = ThemeMode.LIGHT))

        assertEquals(
            "first break, code = \"tr\" [[[",
            File(temp.root, "${ConfigStore.FILE_NAME}${ConfigStore.BROKEN_SUFFIX}").readText(),
        )
        assertEquals(
            "second break, code = \"de\" [[[",
            File(temp.root, "${ConfigStore.FILE_NAME}${ConfigStore.BROKEN_SUFFIX}-2").readText(),
        )
    }

    @Test
    fun `a config with a byte order mark loads instead of being called broken`() {
        // A Windows editor can add one, and this parser rejects it — so without
        // the strip a perfectly good config reads as no config, and would then
        // be set aside as broken when there is nothing wrong with it. The
        // desktop reads its own config as utf-8-sig for exactly this reason.
        val file = File(temp.root, ConfigStore.FILE_NAME)
        file.writeBytes("\uFEFF[language]\ncode = \"tr\"\n".toByteArray(Charsets.UTF_8))

        val loaded = store().load()
        assertNull("a BOM is not corruption: ${loaded.error}", loaded.error)
        assertEquals("tr", loaded.config.language)

        store().save(loaded.config)
        assertFalse(
            "and nothing was set aside",
            File(temp.root, ConfigStore.FILE_NAME + ConfigStore.BROKEN_SUFFIX).exists(),
        )
    }

    @Test
    fun `an unknown key from a future version is tolerated`() {
        File(temp.root, ConfigStore.FILE_NAME).writeText(
            """
            [theme]
            mode = "dark"
            dynamic_color = false
            some_future_key = 42

            [a_future_section]
            whatever = true
            """.trimIndent()
        )

        val loaded = store().load()
        assertNull("unknown keys are not an error", loaded.error)
        assertEquals(ThemeMode.DARK, loaded.config.themeMode)
        assertEquals(false, loaded.config.dynamicColor)
    }

    @Test
    fun `an unrecognised theme mode falls back rather than throwing`() {
        File(temp.root, ConfigStore.FILE_NAME).writeText("[theme]\nmode = \"solarized\"\n")
        assertEquals(ThemeMode.SYSTEM, store().load().config.themeMode)
    }

    // ---- the sort choice, added in AM3 -----------------------------------

    @Test
    fun `the sort choice round-trips`() {
        val store = store()
        store.save(AppConfig(sort = WatchSort.LEAST_WORN))

        assertEquals(WatchSort.LEAST_WORN, store.load().config.sort)
    }

    @Test
    fun `a config with no grid table yields the default sort`() {
        writeAtomically(File(temp.root, ConfigStore.FILE_NAME), "[theme]\nmode = \"dark\"\n")

        val loaded = store().load()
        assertEquals(WatchSort.DEFAULT, loaded.config.sort)
        assertNull("an absent preference is not an error", loaded.error)
    }

    @Test
    fun `an unrecognised sort token falls back rather than throwing`() {
        // Same leniency the theme mode already gets: a config written by a later
        // version must not stop this one from starting.
        writeAtomically(
            File(temp.root, ConfigStore.FILE_NAME),
            "[grid]\nsort = \"by_moon_phase\"\n",
        )

        val loaded = store().load()
        assertEquals(WatchSort.DEFAULT, loaded.config.sort)
        assertNull(loaded.error)
    }

    // ---- the picker mode, added for "Pick for me" --------------------------

    @Test
    fun `the picker mode round-trips`() {
        val store = store()
        store.save(AppConfig(pickerMode = PickerMode.WEIGHTED))

        assertEquals(PickerMode.WEIGHTED, store.load().config.pickerMode)
    }

    @Test
    fun `a config with no picker table yields the default mode`() {
        writeAtomically(File(temp.root, ConfigStore.FILE_NAME), "[theme]\nmode = \"dark\"\n")

        val loaded = store().load()
        assertEquals(PickerMode.DEFAULT, loaded.config.pickerMode)
        assertNull("an absent preference is not an error", loaded.error)
    }

    @Test
    fun `an unrecognised picker mode token falls back rather than throwing`() {
        // Same leniency the sort/theme tokens already get: a config written by
        // a later version must not stop this one from starting.
        writeAtomically(
            File(temp.root, ConfigStore.FILE_NAME),
            "[picker]\nmode = \"coin_flip\"\n",
        )

        val loaded = store().load()
        assertEquals(PickerMode.DEFAULT, loaded.config.pickerMode)
        assertNull(loaded.error)
    }

    @Test
    fun `writing one preference does not disturb the others`() {
        // The regression ConfigState exists to prevent. ConfigStore.save writes
        // the WHOLE file from one AppConfig, so two holders of two stale
        // snapshots would silently overwrite each other's keys — change the
        // sort, then the theme, and the sort quietly reverts.
        val store = store()

        store.save(AppConfig(themeMode = ThemeMode.DARK, language = "tr", sort = WatchSort.MODEL))
        val reloaded = store.load().config
        assertEquals(ThemeMode.DARK, reloaded.themeMode)
        assertEquals("tr", reloaded.language)
        assertEquals(WatchSort.MODEL, reloaded.sort)

        // Now change only the theme, the way a settings screen would, carrying
        // the rest of the config forward.
        store.save(reloaded.copy(themeMode = ThemeMode.LIGHT))
        val afterThemeChange = store.load().config
        assertEquals(ThemeMode.LIGHT, afterThemeChange.themeMode)
        assertEquals("the sort must survive a theme change", WatchSort.MODEL, afterThemeChange.sort)
        assertEquals("tr", afterThemeChange.language)
    }

    @Test
    fun `atomic write leaves no temp files behind`() {
        val target = File(temp.root, "example.toml")
        writeAtomically(target, "a = 1\n")
        writeAtomically(target, "a = 2\n")

        assertEquals("a = 2\n", target.readText())
        val strays = temp.root.listFiles()!!.filter { it.name.endsWith(".tmp") }
        assertTrue("temp files left behind: $strays", strays.isEmpty())
    }

    @Test
    fun `atomic write replaces content wholesale rather than truncating`() {
        val target = File(temp.root, "example.toml")
        writeAtomically(target, "aaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")
        writeAtomically(target, "b\n")
        assertEquals("b\n", target.readText())
    }
}
