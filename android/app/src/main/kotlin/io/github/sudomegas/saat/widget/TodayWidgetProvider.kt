package io.github.sudomegas.saat.widget

import android.app.AlarmManager
import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.os.LocaleList
import android.view.View
import android.widget.RemoteViews
import androidx.appcompat.app.AppCompatDelegate
import io.github.sudomegas.saat.MainActivity
import io.github.sudomegas.saat.R
import io.github.sudomegas.saat.SaatApplication
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId

/**
 * The home-screen widget — SPEC-ANDROID 5.9.
 *
 * IT SHOWS TODAY AND NOTHING ELSE: the watch recorded for today with its
 * photograph and name, or "Nothing recorded today" in the same quiet voice the
 * app's other empty states use. One size, resizable, done properly — four sizes
 * done badly is what this milestone's brief warns against. It sits there: no
 * notification, no reminder, no badge, all three of which the brief forbids.
 *
 * WHY THIS IS REMOTEVIEWS AND NOT GLANCE, against SPEC-ANDROID 2.1's approved
 * list. Every published Glance version declares `androidx.work:work-runtime`,
 * and `GlanceAppWidget`'s CONSTRUCTOR resolves `androidx.work.CoroutineWorker` —
 * it is the class itself, not an optional path something could exclude. That
 * was measured rather than assumed: with the dependency excluded the widget
 * crashed on a real phone with `NoClassDefFoundError` before drawing a pixel.
 *
 * Keeping WorkManager would mean shipping WAKE_LOCK, ACCESS_NETWORK_STATE,
 * RECEIVE_BOOT_COMPLETED and FOREGROUND_SERVICE — hard rule 2 forbids every one
 * of them, and `verifyReleaseManifestPolicy` found all four the moment Glance
 * went in — plus `androidx.sqlite`, which hard rule 4 forbids by name. The hard
 * rules say "non-negotiable, do not improve past them"; §2.1 is a dependency
 * budget written before anyone checked what Glance drags in. So the widget is
 * plain RemoteViews, which needs no dependency at all, and SPEC-ANDROID 2.1
 * should be corrected the way AM3 corrected the media path.
 */
class TodayWidgetProvider : AppWidgetProvider() {

    override fun onUpdate(
        context: Context,
        manager: AppWidgetManager,
        appWidgetIds: IntArray,
    ) {
        val app = context.applicationContext as SaatApplication
        val today = app.watchRepository.state.value.records.todayWatch(LocalDate.now(), app.paths)

        appWidgetIds.forEach { id -> manager.updateAppWidget(id, render(context, today)) }

        // Re-armed on every draw, so a missed alarm — a reboot, a force-stop —
        // repairs itself the next time the widget is updated, with no boot
        // receiver of its own.
        MidnightRefresh.schedule(context)
    }

    /**
     * The widget's content.
     *
     * Read from the repository's CURRENT value rather than awaited. An
     * AppWidgetProvider's onUpdate is a broadcast and has milliseconds, not the
     * coroutine scope a suspend read would need — and the answer is never wrong
     * for long: the app updates every widget whenever today's assignment
     * changes, so a widget drawn before the collection finished loading is
     * redrawn the moment it has.
     */
    private fun render(context: Context, today: TodayWatch?): RemoteViews =
        RemoteViews(context.packageName, R.layout.widget_today).apply {
            if (today == null) {
                // Pushed across rather than left to the layout's android:text.
                // A RemoteViews tree is inflated in the LAUNCHER's process, so
                // `@string/screen_widget_nothing_today` in widget_today.xml is
                // resolved against the DEVICE's locale and knows nothing about
                // this app's. On a Turkish phone with the app set to English the
                // widget read "Bugün için kayıt yok" beside an entirely English
                // app — hard rule 7, on the one surface the rule's machinery
                // cannot reach by itself.
                setTextViewText(
                    R.id.widget_empty,
                    context.inAppLanguage().getString(R.string.screen_widget_nothing_today),
                )
                setViewVisibility(R.id.widget_empty, View.VISIBLE)
                setViewVisibility(R.id.widget_caption, View.GONE)
                setViewVisibility(R.id.widget_photo, View.GONE)
                // On the ROOT, not on a child. A watch with no photograph
                // hides the ImageView, and a hidden child cannot be tapped —
                // found on the phone, where tapping the empty half of the
                // widget fell straight through to the launcher. The root is
                // always there whatever is visible inside it.
                setOnClickPendingIntent(R.id.widget_root, pickerPendingIntent(context))
                return@apply
            }

            setViewVisibility(R.id.widget_empty, View.GONE)
            setViewVisibility(R.id.widget_caption, View.VISIBLE)
            setTextViewText(R.id.widget_brand, today.brand)
            setTextViewText(R.id.widget_model, today.model)

            // Decoded here, and small. A widget draws in the LAUNCHER'S process
            // and cannot open this app's private files, so the bitmap crosses a
            // Binder transaction — whose buffer is about a megabyte, and a
            // modern phone photo is several times that raw.
            val bitmap = today.image?.let { widgetBitmap(it) }
            if (bitmap == null) {
                setViewVisibility(R.id.widget_photo, View.GONE)
            } else {
                setViewVisibility(R.id.widget_photo, View.VISIBLE)
                setImageViewBitmap(R.id.widget_photo, bitmap)
            }

            setOnClickPendingIntent(R.id.widget_root, detailPendingIntent(context, today.slug))
        }

    companion object {
        /**
         * Redraw every placed widget. Called whenever today's assignment
         * changes, from wherever it changed.
         */
        fun updateAll(context: Context) {
            val manager = AppWidgetManager.getInstance(context) ?: return
            val ids = manager.getAppWidgetIds(
                ComponentName(context, TodayWidgetProvider::class.java)
            )
            if (ids.isEmpty()) return

            context.sendBroadcast(
                Intent(context, TodayWidgetProvider::class.java)
                    .setAction(AppWidgetManager.ACTION_APPWIDGET_UPDATE)
                    .putExtra(AppWidgetManager.EXTRA_APPWIDGET_IDS, ids)
            )
        }
    }
}

/**
 * Tapping an empty widget opens the today-picker; a filled one opens that
 * watch's page — SPEC-ANDROID 5.9.
 *
 * The picker, not the app shell. The whole point of the widget is that logging
 * today never requires opening the app, and dropping the owner on the grid to
 * navigate to a calendar would give that back at the last step.
 */
private fun pickerPendingIntent(context: Context): PendingIntent = PendingIntent.getActivity(
    context,
    REQUEST_PICKER,
    Intent(context, TodayPickerActivity::class.java)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK),
    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
)

private fun detailPendingIntent(context: Context, slug: String): PendingIntent =
    PendingIntent.getActivity(
        context,
        // Keyed by slug so two widgets — or one widget across two days — do not
        // share a PendingIntent and open the wrong watch. Two intents that
        // differ only in their extras are otherwise "the same" to the system.
        REQUEST_DETAIL + slug.hashCode(),
        Intent(context, MainActivity::class.java)
            .setAction(Intent.ACTION_VIEW)
            .putExtra(MainActivity.EXTRA_WATCH_SLUG, slug)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
    )

private const val REQUEST_PICKER = 100
private const val REQUEST_DETAIL = 200

/**
 * The one scheduled tick that rolls the widget over at midnight — this
 * milestone's "one scheduled tick, not a heartbeat".
 *
 * AN INEXACT ALARM, AND THAT IS A HARD-RULE DECISION rather than a shortcut.
 * The precise alternatives all cost a permission: `setExact` and
 * `setExactAndAllowWhileIdle` need SCHEDULE_EXACT_ALARM or USE_EXACT_ALARM from
 * API 31, and hard rule 2 says the merged manifest declares NO permission at
 * all. A widget that says "Nothing recorded today" a few minutes into the new
 * day is a fair price; one that made the app ask for an alarm permission is not.
 *
 * WorkManager would have been the other way to do this and is now doubly out:
 * not on the approved list, forbidden by hard rule 4 for the SQLite it carries,
 * and unnecessary — there is exactly one tick a day and nothing to retry if it
 * is missed, because the next update recomputes today from the files anyway.
 */
object MidnightRefresh {

    fun schedule(context: Context, now: LocalDateTime = LocalDateTime.now()) {
        val alarms = context.getSystemService(AlarmManager::class.java) ?: return
        val at = nextMidnight(now).atZone(ZoneId.systemDefault()).toInstant().toEpochMilli()

        // set(), not setExact(): see above. FLAG_UPDATE_CURRENT so rescheduling
        // replaces the pending request rather than stacking one per update.
        alarms.set(AlarmManager.RTC, at, pendingIntent(context))
    }

    private fun pendingIntent(context: Context): PendingIntent = PendingIntent.getBroadcast(
        context,
        REQUEST_CODE,
        Intent(context, MidnightReceiver::class.java).setAction(ACTION_MIDNIGHT),
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
    )

    const val ACTION_MIDNIGHT = "io.github.sudomegas.saat.MIDNIGHT"

    private const val REQUEST_CODE = 1
}

/**
 * Redraws the widget when the day turns over, and re-arms the next tick.
 *
 * Also listens for the system's own date and time-zone changes, which covers a
 * phone that slept through midnight, one whose clock was set by hand and one
 * carried across a time zone — three cases a single alarm cannot see. All three
 * are exempt from the API 26 implicit-broadcast restrictions, so a manifest
 * receiver still gets them.
 */
class MidnightReceiver : android.content.BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        TodayWidgetProvider.updateAll(context)
        MidnightRefresh.schedule(context)
    }
}

/**
 * A Context whose resources speak the language the OWNER chose, not the one the
 * phone is set to.
 *
 * Hard rule 7 is enforced for the app's own screens by
 * `SaatApplication.applyLanguage`, and for API 33+ the framework then applies
 * that locale to the whole process. A widget is the exception, twice over: its
 * layout is inflated somewhere else entirely, and on API 26-32 the per-app
 * locale lives in an AppCompat static that only Activity contexts consult — a
 * broadcast receiver's context has never heard of it.
 *
 * `AppCompatDelegate.getApplicationLocales` answers correctly on both sides of
 * 33 (it reads the framework's LocaleManager above, its own record below), so
 * pinning it onto a configuration context gives one lookup that is right
 * everywhere. An empty list means nothing was ever asserted, and the platform
 * default is then the honest answer.
 */
private fun Context.inAppLanguage(): Context {
    val locales = AppCompatDelegate.getApplicationLocales()
    if (locales.isEmpty) return this

    val configuration = Configuration(resources.configuration)
    configuration.setLocales(LocaleList.forLanguageTags(locales.toLanguageTags()))
    return createConfigurationContext(configuration)
}
