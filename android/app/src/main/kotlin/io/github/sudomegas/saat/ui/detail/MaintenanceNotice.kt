package io.github.sudomegas.saat.ui.detail

import androidx.annotation.StringRes
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.storage.MAINTENANCE_DUE_SOON_DAYS
import io.github.sudomegas.saat.storage.Watch
import io.github.sudomegas.saat.storage.nextServiceDue
import io.github.sudomegas.saat.ui.formatDate
import java.time.LocalDate

/**
 * The line at the top of the detail page when something wants doing — SPEC.md
 * §4, AM9b.
 *
 * A port of the desktop's `maintenance_due_text`, with the same two-sentence
 * vocabulary and the same silence. THE SILENCE IS THE FEATURE. Nothing is
 * emitted when there is no baseline to project from, nothing when the interval
 * is blank, and nothing when the date is comfortably ahead — most watches will
 * never carry a service interval at all, and a catalogue that nagged about them
 * would be a catalogue the owner stopped opening.
 *
 * [message] is a resource and its date argument rather than a finished string,
 * for the same reason [SpecValue.Resource] is: the vocabulary is the app's and
 * AM11 translates it, while the date has already been through `formatDate` and
 * is data.
 */
data class MaintenanceNotice(
    @StringRes val messageRes: Int,
    /** The due date, already formatted DD.MM.YYYY. */
    val date: String,
    /** Past its date, as opposed to merely approaching it. */
    val isOverdue: Boolean,
)

/**
 * Everything currently wanting attention, in the order it is worth reading.
 *
 * A LIST, THOUGH AM9b ASKS FOR "A SINGLE LINE". The brief's sentence is about
 * not building a banner, and it is written for the service clock; the very next
 * sentence gives `battery_due` the same treatment, and the two can legitimately
 * both be due on a watch that has an interval AND a battery date. Suppressing
 * one of them to honour a word count would mean the page knew something it did
 * not say. In practice this returns nothing at all for most watches, one line
 * for a few, and two for the rare mecha-quartz whose owner tracks both.
 *
 * Overdue sorts above due-soon: if only one line is read, it should be the one
 * that is already late.
 */
fun maintenanceNotices(watch: Watch, today: LocalDate): List<MaintenanceNotice> = listOfNotNull(
    notice(
        due = watch.nextServiceDue(),
        today = today,
        overdueRes = R.string.screen_detail_service_overdue,
        dueRes = R.string.screen_detail_service_due,
    ),
    notice(
        due = watch.maintenance.batteryDue,
        today = today,
        overdueRes = R.string.screen_detail_battery_overdue,
        dueRes = R.string.screen_detail_battery_due,
    ),
).sortedByDescending { it.isOverdue }

/**
 * One clock's line, or null when that clock is silent.
 *
 * The threshold is [MAINTENANCE_DUE_SOON_DAYS] and is inclusive of the boundary
 * day, matching `isMaintenanceDue` — a date exactly ninety days out is due, and
 * having the notice and the accent dot disagree by one day would be the sort of
 * bug nobody reports and everybody notices.
 */
private fun notice(
    due: LocalDate?,
    today: LocalDate,
    @StringRes overdueRes: Int,
    @StringRes dueRes: Int,
): MaintenanceNotice? {
    if (due == null) return null
    if (due.isAfter(today.plusDays(MAINTENANCE_DUE_SOON_DAYS))) return null

    val overdue = due.isBefore(today)
    return MaintenanceNotice(
        messageRes = if (overdue) overdueRes else dueRes,
        date = formatDate(due),
        isOverdue = overdue,
    )
}
