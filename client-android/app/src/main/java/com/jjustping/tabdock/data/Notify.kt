package com.jjustping.tabdock.data

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import com.jjustping.tabdock.R
import org.json.JSONObject

/**
 * Android notifications: "export finished" (while the app is in the background) and shoot deadlines
 * (today / tomorrow, once a day per shoot). Polling keeps running slowly while the app is in the background;
 * when the app is closed completely nothing is checked — that needs a background service (later).
 */
object Notify {
    private const val CH_EVENTS = "events"
    private const val CH_DEADLINES = "deadlines"
    private const val CH_HOSTS = "hosts"

    fun init(ctx: Context) {
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return
        nm.createNotificationChannel(NotificationChannel(CH_EVENTS, "Экспорт закончился", NotificationManager.IMPORTANCE_DEFAULT)
            .apply { description = "Capture One или папка закончили выгрузку съёмки" })
        nm.createNotificationChannel(NotificationChannel(CH_DEADLINES, "Сроки сдачи", NotificationManager.IMPORTANCE_DEFAULT)
            .apply { description = "Съёмки, которые нужно сдать сегодня или завтра" })
        nm.createNotificationChannel(NotificationChannel(CH_HOSTS, "Хосты в сети", NotificationManager.IMPORTANCE_HIGH)
            .apply { description = "Роутер, NAS или сервер перестал отвечать или снова работает" })
    }

    private fun allowed(ctx: Context, store: Store) =
        store.string("notify") != "0" &&
            (Build.VERSION.SDK_INT < 33 || ctx.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED)

    private fun post(ctx: Context, channel: String, id: Int, title: String, text: String) {
        val open = PendingIntent.getActivity(ctx, 0, ctx.packageManager.getLaunchIntentForPackage(ctx.packageName)?.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val n = android.app.Notification.Builder(ctx, channel).setSmallIcon(R.drawable.ic_stat_tabdock)
            .setContentTitle(title).setContentText(text).setStyle(android.app.Notification.BigTextStyle().bigText(text))
            .setContentIntent(open).setAutoCancel(true).build()
        runCatching { ctx.getSystemService(NotificationManager::class.java)?.notify(id, n) }
    }

    fun exportDone(ctx: Context, store: Store, e: JSONObject) {
        if (!allowed(ctx, store)) return
        val target = e.optInt("target")
        post(ctx, CH_EVENTS, 1000 + e.optInt("id") % 1000, "Экспорт закончился",
            "«${e.optString("name")}»: +${e.optInt("added")} кадров" + if (target > 0) " · ${e.optInt("done")} из $target" else "")
    }

    fun host(ctx: Context, store: Store, e: JSONObject) {
        if (!allowed(ctx, store)) return
        val down = e.optString("type") == "host_down"
        post(ctx, CH_HOSTS, 3000 + (e.optString("name").hashCode() and 0x3ff),
            if (down) "Не отвечает: ${e.optString("name")}" else "Снова работает: ${e.optString("name")}",
            if (down) "TabDock на компьютере больше не получает ответа" else "Хост снова отвечает")
    }

    /** Shoots due today / tomorrow and not delivered yet: one notification per shoot per day. */
    fun deadlines(ctx: Context, store: Store, all: JSONObject) {
        if (!allowed(ctx, store)) return
        val today = Fmt.today(); val tomorrow = Fmt.today(1)
        for (sh in all.optJSONObject("shoots").a("items").objs()) {
            val d = sh.s("deadline")
            if (d != today && d != tomorrow || sh.s("status") in setOf("done", "delivered") || sh.b("hidden")) continue
            val key = "dl:${sh.s("key")}:$d:$today"
            if (store.string(key) != null) continue
            store.put(key, "1")
            val left = (sh.i("target").takeIf { it > 0 } ?: sh.i("total")) - sh.i("done")
            post(ctx, CH_DEADLINES, 2000 + (sh.s("key").hashCode() and 0x3ff),
                if (d == today) "Сегодня сдать: ${sh.s("name")}" else "Завтра сдать: ${sh.s("name")}",
                "Готово ${sh.i("done")} ${sh.s("done_label")}" + if (left > 0) ", осталось $left" else "")
        }
    }
}
