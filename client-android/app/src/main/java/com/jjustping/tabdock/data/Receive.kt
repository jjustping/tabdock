package com.jjustping.tabdock.data

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.webkit.MimeTypeMap
import androidx.core.content.FileProvider
import com.jjustping.tabdock.R
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.io.OutputStream

/**
 * Computer → phone: files from the «Передача файлов» window. The app takes them while it is open or in the
 * background, saves them to Downloads/TabDock and shows a notification that opens the file.
 */
class Receiver(private val ctx: Context, private val store: Store, private val history: Transfers) {
    private val busy = java.util.Collections.synchronizedSet(mutableSetOf<String>())

    init {
        ctx.getSystemService(NotificationManager::class.java)?.createNotificationChannel(
            NotificationChannel(CH, "Файлы с компьютера", NotificationManager.IMPORTANCE_DEFAULT)
                .apply { description = "Файлы, отправленные с компьютера через «Передачу файлов»" })
    }

    /** Called with the "outbox" list from /api/state; returns names of files saved now. */
    suspend fun take(api: Api, items: List<JSONObject>, toast: (String) -> Unit) {
        for (it in items) {
            val id = it.optString("id"); val name = it.optString("name").ifBlank { "файл" }
            if (id.isBlank() || !busy.add(id)) continue
            try {
                val saved = withContext(Dispatchers.IO) { save(name) { out -> api.download("/api/outbox/file?id=$id", out) } }
                runCatching { api.post("/api/outbox", JSONObject().put("op", "done").put("id", id)) }
                history.add("in", name, it.optLong("size", -1), saved.toString())
                toast("Файл с компьютера: $name — в «Загрузках → TabDock»")
                notify(name, saved)
            } catch (e: Exception) {
                toast("Не получилось принять «$name»: ${e.message}")
            } finally { busy.remove(id) }
        }
    }

    /** Writes to Downloads/TabDock (MediaStore on Android 10+, the app's own folder before that). */
    private fun save(name: String, write: (OutputStream) -> Unit): Uri {
        val mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(name.substringAfterLast('.', "").lowercase()) ?: "application/octet-stream"
        if (Build.VERSION.SDK_INT >= 29) {
            val cr = ctx.contentResolver
            val v = ContentValues().apply {
                put(MediaStore.Downloads.DISPLAY_NAME, name)
                put(MediaStore.Downloads.MIME_TYPE, mime)
                put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/TabDock")
                put(MediaStore.Downloads.IS_PENDING, 1)
            }
            val uri = cr.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v) ?: error("нет доступа к «Загрузкам»")
            try {
                cr.openOutputStream(uri)!!.use(write)
            } catch (e: Exception) { cr.delete(uri, null, null); throw e }
            cr.update(uri, ContentValues().apply { put(MediaStore.Downloads.IS_PENDING, 0) }, null, null)
            return uri
        }
        val dir = File(ctx.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "TabDock").apply { mkdirs() }
        var f = File(dir, name); var i = 2
        while (f.exists()) { f = File(dir, name.substringBeforeLast('.') + " ($i)." + name.substringAfterLast('.', "bin")); i++ }
        f.outputStream().use(write)
        return FileProvider.getUriForFile(ctx, ctx.packageName + ".files", f)
    }

    private fun notify(name: String, uri: Uri) {
        if (Build.VERSION.SDK_INT >= 33 && ctx.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        val mime = ctx.contentResolver.getType(uri) ?: "*/*"
        val open = PendingIntent.getActivity(ctx, name.hashCode(), Intent(Intent.ACTION_VIEW).setDataAndType(uri, mime)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE)
        val n = android.app.Notification.Builder(ctx, CH).setSmallIcon(R.drawable.ic_stat_tabdock)
            .setContentTitle("Файл с компьютера").setContentText(name).setContentIntent(open).setAutoCancel(true).build()
        runCatching { ctx.getSystemService(NotificationManager::class.java)?.notify(3000 + (name.hashCode() and 0xfff), n) }
    }

    companion object { const val CH = "files" }
}

/** This device's history of transfers in both directions (newest first, at most 200 lines). */
class Transfers(private val store: Store) {
    val list = kotlinx.coroutines.flow.MutableStateFlow(
        runCatching { org.json.JSONArray(store.string("transfers") ?: "[]").objs() }.getOrDefault(emptyList()))

    @Synchronized fun add(dir: String, name: String, size: Long, uri: String?) {
        val o = JSONObject().put("dir", dir).put("name", name).put("size", size).put("at", System.currentTimeMillis()).put("uri", uri ?: "")
        save(listOf(o) + list.value)
    }
    @Synchronized fun remove(o: JSONObject) = save(list.value.filter { it !== o })
    @Synchronized fun clear() = save(emptyList())
    private fun save(next: List<JSONObject>) {
        list.value = next.take(200); store.put("transfers", org.json.JSONArray(list.value).toString())
    }
}

/** Opening files and the Downloads/TabDock folder in the phone's own apps. */
object Files {
    fun open(ctx: Context, uri: Uri, name: String): Boolean {
        val mime = runCatching { ctx.contentResolver.getType(uri) }.getOrNull()
            ?: MimeTypeMap.getSingleton().getMimeTypeFromExtension(name.substringAfterLast('.', "").lowercase()) ?: "*/*"
        // a file that was deleted or moved: say so instead of opening an empty viewer
        if (runCatching { ctx.contentResolver.openInputStream(uri)?.close() }.isFailure) return false
        return runCatching {
            ctx.startActivity(Intent.createChooser(Intent(Intent.ACTION_VIEW).setDataAndType(uri, mime)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION), name).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }.isSuccess
    }

    /** Downloads/TabDock in the system «Файлы» app (the Downloads list where that is not possible). */
    fun openFolder(ctx: Context) {
        if (Build.VERSION.SDK_INT >= 29) {
            val dir = android.provider.DocumentsContract.buildDocumentUri("com.android.externalstorage.documents", "primary:Download/TabDock")
            // the system «Файлы» (DocumentsUI) opens right in the folder; without a package some phones show a long chooser
            for (pkg in listOf("com.google.android.documentsui", "com.android.documentsui", null)) {
                val ok = runCatching {
                    ctx.startActivity(Intent(Intent.ACTION_VIEW).setDataAndType(dir, android.provider.DocumentsContract.Document.MIME_TYPE_DIR)
                        .apply { if (pkg != null) setPackage(pkg) }
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))     // no grant flag: the app does not own this URI
                }.isSuccess
                if (ok) return
            }
        }
        runCatching { ctx.startActivity(Intent(android.app.DownloadManager.ACTION_VIEW_DOWNLOADS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
    }
}
