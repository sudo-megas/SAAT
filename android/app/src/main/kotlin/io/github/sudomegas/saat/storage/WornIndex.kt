package io.github.sudomegas.saat.storage

import java.time.LocalDate

/**
 * The date-to-watch index — SPEC-ANDROID 5.5.
 *
 * BUILT IN MEMORY, AT LOAD, FROM EACH WATCH'S OWN `worn` LIST. There is no
 * central wear log and there must not be one: this milestone's brief forbids
 * centralising it "for efficiency", and the reason is that a watch folder is
 * then a complete record. Deleting a watch takes its days with it for free, the
 * exported ZIP needs no second file, and a hand-edited `watch.toml` cannot
 * disagree with an index nobody can see. A few hundred watches with a few
 * thousand days between them is a map built in microseconds; the "efficiency"
 * would buy nothing and cost the property the whole storage format exists for.
 *
 * OWNED WATCHES ONLY, matching the desktop's `build_worn_index`. A watch that is
 * Sold, Gifted, Incoming or on a Wishlist is not on anybody's wrist, so it does
 * not hold days in the calendar. Note this is the INDEX's rule, not the wear
 * path's: `WatchRepository.assignWorn` still strips a day from a non-Owned watch
 * that holds one, because a stale claim should be released rather than left to
 * shadow a new assignment.
 *
 * A day claimed by two watches — only reachable by hand-editing two files —
 * resolves to the last one in slug order rather than throwing. The calendar
 * shows one watch per day because that is what it can draw; the files still say
 * what they say, and the next assignment to that day tidies both.
 */
fun List<WatchRecord>.wornIndex(): Map<LocalDate, WatchRecord> {
    val index = HashMap<LocalDate, WatchRecord>()
    ownedWatches().forEach { record ->
        record.watch!!.worn.forEach { day -> index[day] = record }
    }
    return index
}

/**
 * Owned watches only — the choke point [wornIndex] and "Pick for me"
 * (`storage/Selection.kt`) both read through, matching the desktop's
 * `owned_watches()`.
 */
fun List<WatchRecord>.ownedWatches(): List<WatchRecord> =
    filter { record ->
        val watch = record.watch
        watch != null && watch.status == Watch.STATUS_OWNED
    }
