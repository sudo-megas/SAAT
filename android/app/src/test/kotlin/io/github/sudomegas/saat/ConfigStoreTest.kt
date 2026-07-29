package io.github.sudomegas.saat

import io.github.sudomegas.saat.config.AppConfig
import io.github.sudomegas.saat.config.ConfigStore
import io.github.sudomegas.saat.config.ThemeMode
import io.github.sudomegas.saat.config.writeAtomically
import org.junit.Assert.assertEquals
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
