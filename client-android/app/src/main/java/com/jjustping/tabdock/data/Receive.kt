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
