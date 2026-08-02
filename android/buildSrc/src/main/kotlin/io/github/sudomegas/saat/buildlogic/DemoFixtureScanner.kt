package io.github.sudomegas.saat.buildlogic

/**
 * One reason a build was judged to contain — or to be missing — the demo-watch
 * fixture.
 */
data class DemoFixtureFinding(val rule: String, val detail: String)

/**
 * Decides whether a compiled variant carries the debug-only demo-watch fixture.
 *
 * SPEC-ANDROID hard rule 1 permits exactly one exception to "no demo watches":
 * a developer action present in debug builds only, with "a test asserts the
 * mechanism is absent from release builds". This is that test's engine.
 *
 * A pure function over strings and bytes, with no Gradle and no AGP types, for
 * the same reason `ManifestPolicyScanner` is: buildSrc deliberately carries no
 * AGP dependency, and a pure scanner is unit-testable in plain JUnit while the
 * variant wiring stays in the app's build script.
 *
 * Three independent signals, because one is easy to defeat by accident:
 *
 *  1. a compiled class under the `devtools` package;
 *  2. the marker string `SAAT Demo` in a class's constant pool, which catches
 *     the fixture being moved to another package;
 *  3. a string resource whose name contains `demo` in the variant's R.txt,
 *     which catches the strings surviving even if the code does not.
 *
 * Signal 2 is a plain byte search. Java class files hold their string constants
 * in modified UTF-8, which is byte-identical to ASCII for this marker.
 */
object DemoFixtureScanner {

    /** The package the fixture lives in, as it appears in a class file path. */
    const val DEVTOOLS_PATH = "io/github/sudomegas/saat/devtools/"

    /** `DemoWatches.DEMO_BRAND`. Kept in step by DemoWatchesTest. */
    const val MARKER = "SAAT Demo"

    /** Debug-only string resources are all named to contain this. */
    const val RESOURCE_TOKEN = "demo"

    private val markerBytes = MARKER.toByteArray(Charsets.UTF_8)

    fun isDevtoolsClass(path: String): Boolean =
        path.replace('\\', '/').contains(DEVTOOLS_PATH)

    fun containsMarker(bytes: ByteArray): Boolean {
        if (markerBytes.isEmpty() || bytes.size < markerBytes.size) return false
        outer@ for (start in 0..bytes.size - markerBytes.size) {
            for (offset in markerBytes.indices) {
                if (bytes[start + offset] != markerBytes[offset]) continue@outer
            }
            return true
        }
        return false
    }

    /**
     * String-resource names in an R.txt that look like the debug-only fixture's.
     *
     * R.txt lines are `<type> <class> <name> <value>`, e.g.
     * `int string action_add_demo_watches 0x7f0e0001`. Only `string` and
     * `plurals` entries are considered — a drawable or an id happening to
     * contain "demo" is not what this rule is about.
     */
    fun demoResourceNames(symbolList: String): List<String> =
        symbolList.lineSequence()
            .mapNotNull { line ->
                val parts = line.trim().split(' ')
                if (parts.size < 3) return@mapNotNull null
                val kind = parts[1]
                val name = parts[2]
                if (kind != "string" && kind != "plurals") return@mapNotNull null
                name.takeIf { it.contains(RESOURCE_TOKEN, ignoreCase = true) }
            }
            .distinct()
            .sorted()
            .toList()
}
