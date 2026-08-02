package io.github.sudomegas.saat

import java.io.File

/**
 * Reading Kotlin sources as evidence, for the handful of rules that are about
 * the shape of the code rather than its behaviour.
 *
 * Several of SPEC-ANDROID's hard rules are structural — "never reads the system
 * locale", "the demo fixture is not referenced from shared code" — and the
 * cheapest honest guard for those is to look at the sources. A scan cannot prove
 * a call runs; it proves nobody deleted or added one, which is the regression
 * being guarded against.
 *
 * Shared because both [LocalePolicyTest] and [GridPolicyTest] need the same
 * comment handling, and getting it wrong in one place only would be worse than
 * not having it.
 */
object SourceScan {

    fun kotlinFiles(root: String): Sequence<File> =
        File(root).walkTopDown().filter { it.isFile && it.extension == "kt" }

    /**
     * The file's lines with comments blanked out, so that prose ABOUT a rule is
     * never mistaken for a breach of it.
     *
     * Not a nicety. The two clearest explanations in this codebase — why `Slugs`
     * avoids `lowercase(Locale.getDefault())`, and why `MainActivity` cannot use
     * the framework's `LocaleManager` — both name APIs the locale scan forbids.
     * A plain text search fails on the documentation and passes on nothing,
     * which would teach the next person to delete the comments rather than keep
     * the rule.
     *
     * Line numbers are preserved (blanked, not dropped) so failure messages
     * still point at the right line.
     */
    fun codeLines(file: File): List<IndexedValue<String>> {
        var inBlock = false
        return file.readLines().withIndex().map { (index, raw) ->
            val code = StringBuilder()
            var i = 0
            while (i < raw.length) {
                val pair = if (i + 1 < raw.length) raw.substring(i, i + 2) else ""
                when {
                    inBlock -> if (pair == "*/") { inBlock = false; i += 2 } else i++
                    pair == "/*" -> { inBlock = true; i += 2 }
                    pair == "//" -> i = raw.length
                    else -> { code.append(raw[i]); i++ }
                }
            }
            IndexedValue(index, code.toString())
        }
    }

    /** `file.kt:12  the offending line`, for a readable assertion message. */
    fun offenders(root: String, predicate: (String) -> Boolean): List<String> =
        kotlinFiles(root).flatMap { file ->
            codeLines(file)
                .filter { (_, line) -> predicate(line) }
                .map { (i, line) -> "${file.name}:${i + 1}  ${line.trim()}" }
        }.toList()
}
