package com.jjustping.tabdock.data

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import com.jjustping.tabdock.BuildConfigShim
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/** A newer release found by the computer (it checks GitHub; the phone does not need internet for that). */
data class AppUpdate(val version: String, val notes: String, val apk: String?, val page: String?)

object Updater {
    private fun parse(v: String): List<Int> {
        val m = Regex("""v?(\d+)\.(\d+)(?:\.(\d+))?(-[\w.]+)?""").find(v.trim()) ?: return listOf(0, 0, 0, 0)
        return listOf(m.groupValues[1].toInt(), m.groupValues[2].toInt(), m.groupValues[3].ifBlank { "0" }.toInt(),
            if (m.groupValues[4].isBlank()) 1 else 0)
    }
    fun newer(a: String, b: String): Boolean {
        val x = parse(a); val y = parse(b)
        for (i in x.indices) if (x[i] != y[i]) return x[i] > y[i]
        return false
    }

    /** From GET /api/update: the latest release if it is newer than this app. */
    fun fromServer(o: JSONObject?): AppUpdate? {
        val l = o?.optJSONObject("latest") ?: return null
        val v = l.optString("version")
        if (v.isBlank() || !newer(v, BuildConfigShim.VERSION)) return null
        return AppUpdate(v, l.optString("notes"), l.optString("apk").ifBlank { null }, l.optString("url").ifBlank { null })
    }

    /** Downloads the APK (from GitHub, following redirects) into cache/updates/; [progress] 0..1. */
    suspend fun download(ctx: Context, u: AppUpdate, progress: (Float) -> Unit): File = withContext(Dispatchers.IO) {
        val dir = File(ctx.cacheDir, "updates").apply { mkdirs(); listFiles()?.forEach { it.delete() } }
        val out = File(dir, "TabDock-${u.version}.apk")
        var url = URL(u.apk ?: error("no apk"))
        var c: HttpURLConnection
        var hops = 0
        while (true) {   // GitHub answers with a redirect to its file storage
            c = url.openConnection() as HttpURLConnection
            c.instanceFollowRedirects = false; c.connectTimeout = 15000; c.readTimeout = 30000
            c.setRequestProperty("User-Agent", "TabDock/${BuildConfigShim.VERSION}")
            if (c.responseCode in 300..399 && hops++ < 5) { url = URL(url, c.getHeaderField("Location")); c.disconnect(); continue }
            break
        }
        if (c.responseCode != 200) error("HTTP ${c.responseCode}")
        val total = c.contentLengthLong
        c.inputStream.use { inp ->
            out.outputStream().use { o ->
                val buf = ByteArray(64 * 1024); var n: Int; var got = 0L
                while (inp.read(buf).also { n = it } >= 0) { o.write(buf, 0, n); got += n; if (total > 0) progress(got.toFloat() / total) }
            }
        }
        c.disconnect()
        out
    }

    /** Android asks «allow installing from TabDock?» once; then the system installer takes over. */
    fun canInstall(ctx: Context) = Build.VERSION.SDK_INT < 26 || ctx.packageManager.canRequestPackageInstalls()

    fun askInstallPermission(ctx: Context) {
        ctx.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + ctx.packageName))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    fun install(ctx: Context, apk: File) {
        val uri = FileProvider.getUriForFile(ctx, ctx.packageName + ".files", apk)
        ctx.startActivity(Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    fun openPage(ctx: Context, url: String) {
        ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }
}
