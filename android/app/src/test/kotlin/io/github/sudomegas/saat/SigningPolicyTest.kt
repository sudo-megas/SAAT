package io.github.sudomegas.saat

import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Nothing secret is in this repository — AM11b.
 *
 * The `.gitignore` entries have been in place since AM1 and are the real
 * defence. This is the second one, and it guards the case `.gitignore` cannot:
 * a file added with `git add -f`, or a password pasted into the build script by
 * somebody in a hurry with a deadline. `.gitignore` stops an accident; only a
 * test stops a decision.
 *
 * The stakes are what justify a second check for something already covered.
 * Every other mistake in this project is recoverable — a bad release can be
 * re-cut, a wrong translation corrected, a lost edit restored from
 * `backups/`. **A signing key that reaches a public repository cannot be
 * un-published, and Android does not allow rotating one.** See
 * `docs/ANDROID-RELEASING.md`.
 */
class SigningPolicyTest {

    private val androidRoot = File("..")

    /** Every file under `android/`, minus build output nobody commits. */
    private fun sources(): List<File> = androidRoot.walkTopDown()
        .onEnter { it.name !in setOf("build", ".gradle", ".kotlin", ".idea") }
        .filter { it.isFile }
        .toList()

    @Test
    fun `no keystore is committed anywhere under android`() {
        val keystores = sources().filter { file ->
            file.extension in setOf("jks", "keystore") || file.name == "keystore.properties"
        }

        assertTrue(
            "signing material found in the repository: ${keystores.map { it.path }}\n" +
                "A key that has been public for one minute has been published, and " +
                "Android does not allow rotating an app signing key.",
            keystores.isEmpty(),
        )
    }

    /**
     * The build script names the four inputs and must never carry their values.
     * A literal password here would be committed the moment it worked.
     */
    @Test
    fun `the build script reads signing material from outside the tree`() {
        val script = File("build.gradle.kts").readText()

        // It must go through the environment or Gradle properties…
        assertTrue(
            "the signing config no longer reads System.getenv or a Gradle property",
            script.contains("System.getenv") && script.contains("findProperty"),
        )

        // …and must not assign any of the four names a literal.
        val assigned = Regex("""SAAT_(KEYSTORE_FILE|KEYSTORE_PASSWORD|KEY_ALIAS|KEY_PASSWORD)\s*=\s*"[^"]+"""")
            .findAll(script)
            .map { it.value }
            .toList()

        assertTrue("a signing value is hard-coded in build.gradle.kts: $assigned", assigned.isEmpty())
    }

    /** The `.gitignore` lines are load-bearing; deleting one must fail here. */
    @Test
    fun `gitignore still excludes every form of signing material`() {
        val ignored = File("../.gitignore").readText()

        listOf("*.keystore", "*.jks", "keystore.properties").forEach { pattern ->
            assertTrue(
                "android/.gitignore no longer excludes $pattern — it has done since AM1, " +
                    "before any keystore existed to be careless with",
                ignored.contains(pattern),
            )
        }
    }

    /**
     * A base64 keystore is a string and would slip past every extension check
     * above. The workflow is where one would be pasted "temporarily".
     */
    @Test
    fun `no workflow carries an inline base64 keystore`() {
        val workflows = File("../../.github/workflows").listFiles().orEmpty()

        workflows.forEach { workflow ->
            val text = workflow.readText()
            // A real keystore base64 is thousands of characters. Anything that
            // long on one line in a workflow is not configuration.
            val suspicious = text.lineSequence().filter { line ->
                line.length > 500 && Regex("""[A-Za-z0-9+/]{400,}""").containsMatchIn(line)
            }.toList()

            assertTrue(
                "${workflow.name} carries what looks like inline base64 — the keystore " +
                    "belongs in a GitHub secret, never in the tree",
                suspicious.isEmpty(),
            )
        }
    }
}
