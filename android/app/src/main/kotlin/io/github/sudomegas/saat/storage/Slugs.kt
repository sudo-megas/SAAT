package io.github.sudomegas.saat.storage

/**
 * A watch's folder name, derived from brand + model. A direct port of the
 * desktop's `saat/storage.py`, not a reimplementation — SPEC-ANDROID 3 requires
 * a collection to move in both directions between the two apps, and a slug
 * generated differently on each platform is a watch that duplicates itself the
 * first time it crosses.
 *
 * The slug is an identifier, not a live mirror: editing brand or model later
 * does not rename the folder (docs/schema.md).
 */

/** Anything outside `[a-z0-9]`, in runs, becomes a single hyphen. */
private val SLUG_INVALID = Regex("[^a-z0-9]+")

/**
 * Windows refuses these as a whole filename component, on every drive, with or
 * without an extension: they are DOS device names that predate long filenames.
 * A slug is a directory name, so `con` or `lpt1` would be an unwritable folder,
 * and the brand and model producing one need not be exotic once the character
 * class above has reduced whatever was typed to `[a-z0-9-]`.
 *
 * Guarded on Android too, where none of it applies, for the reason the
 * case-insensitive collision check below exists: a folder Linux and Android
 * create happily and Windows cannot open is a collection that stops being
 * portable the moment it is copied across.
 */
private val WINDOWS_RESERVED_NAMES: Set<String> = buildSet {
    addAll(listOf("con", "prn", "aux", "nul"))
    for (n in 1..9) {
        add("com$n")
        add("lpt$n")
    }
}

/**
 * Windows' path limit is 260 characters by default and a slug is only one
 * component of a path that also holds the data directory, `watches/` and a
 * filename. Brand and model are free text with no length limit of their own, so
 * a pasted product description would otherwise become a directory nothing
 * downstream could write into. Truncation can create a collision; [uniqueSlug]
 * already resolves those.
 */
private const val SLUG_MAX_LENGTH = 80

private const val SLUG_FALLBACK = "watch"

/**
 * A directory name safe on every filesystem either app runs on.
 *
 * THE TURKISH DOTLESS-I TRAP, which is why this uses [String.lowercase] with no
 * argument. Kotlin's no-argument `lowercase()` is locale-independent — it maps
 * with the root locale, exactly as Python's `str.lower()` does. The deprecated
 * `toLowerCase()` and any `lowercase(Locale.getDefault())` are not: on a phone
 * set to Turkish they map `I` to the dotless `ı`, which is not in `[a-z0-9]` and
 * would be swallowed by the character class — so `Seiko SKX007` would slug as
 * `seko-skx007` on a Turkish phone and `seiko-skx007` everywhere else, and the
 * same watch would exist twice the first time the collection moved. The owner's
 * phone is a Turkish phone, so this is the live case, not the theoretical one.
 * `SlugTest` proves the independence by flipping the default locale rather than
 * by trusting this comment.
 */
fun slugify(brand: String, model: String): String {
    var base = "$brand $model".trim().lowercase()
    base = SLUG_INVALID.replace(base, "-").trim('-')

    if (base.length > SLUG_MAX_LENGTH) {
        base = base.take(SLUG_MAX_LENGTH).trimEnd('-')
    }
    if (base.isEmpty()) return SLUG_FALLBACK
    if (base in WINDOWS_RESERVED_NAMES) {
        // Suffixed rather than rejected: the owner typed a real brand and model,
        // and the folder name is an implementation detail they should not have
        // to work around.
        return "$base-$SLUG_FALLBACK"
    }
    return base
}

/**
 * Disambiguate against what is already on disk, case-INSENSITIVELY, resolving
 * with `-2`, `-3`.
 *
 * [slugify] lowercases, so two generated slugs can never differ only by case —
 * the exposure is hand-authored folders, which SPEC.md §3 explicitly supports.
 * A folder someone created as `Seiko-SKX007` beside a generated `seiko-skx007`
 * is two watches on ext4 and one on NTFS: on Windows the second save would open
 * the first watch's folder and overwrite it. Compared case-insensitively on
 * every platform so a collection stays loadable in both directions, which costs
 * at most one extra distinct slug in a case that would otherwise have silently
 * produced two folders a Windows user could never separate.
 */
fun uniqueSlug(brand: String, model: String, existing: Set<String>): String {
    val base = slugify(brand, model)
    val taken = existing.mapTo(mutableSetOf()) { it.lowercase() }

    if (base.lowercase() !in taken) return base
    var n = 2
    while ("$base-$n".lowercase() in taken) n += 1
    return "$base-$n"
}

/**
 * SPEC-ANDROID 3: the loader skips any entry whose name starts with `_` or `.`.
 * That is what makes the desktop's `watches/_template.toml` a template rather
 * than a watch, and it is why a real `watch.toml` must never gain an underscore.
 */
fun isHiddenEntry(name: String): Boolean = name.startsWith("_") || name.startsWith(".")
