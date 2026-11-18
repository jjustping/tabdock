package com.jjustping.tabdock.data

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.os.IBinder
import android.provider.DocumentsContract
import android.provider.MediaStore
import android.webkit.MimeTypeMap
import androidx.core.content.FileProvider
import com.jjustping.tabdock.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.io.InputStream
import java.security.MessageDigest

/**
 * Every transfer between this device and the computer, both ways, one at a time, outside the screen's life:
 * big files go in parts of 16 MB and continue after a dropped connection; a folder goes as its files with their
 * paths and arrives as a folder. While something is moving, a foreground service (with a progress notification)
 * keeps Android from stopping the app.
 */
object TransferHub {
    const val PART = 16 * 1024 * 1024
    private const val CH_PROGRESS = "transfer"
    private const val CH_DONE = "files"
    const val NOTE_ID = 4100

    /** One file to send: where to read it, and (inside a folder) the folder's name and the path in it. */
    data class Item(val uri: Uri, val name: String, val size: Long, val folder: String = "", val rel: String = "", val batch: String = "")

    data class Progress(val out: Boolean, val title: String, val file: String, val index: Int, val count: Int,
                        val done: Long, val total: Long, val speed: Double, val waiting: Boolean = false, val queued: Int = 0)

    val progress = MutableStateFlow<Progress?>(null)
    private sealed class Job {
        class Send(val api: Api, val items: List<Item>, val title: String) : Job()
        class Fetch(val api: Api, val item: JSONObject) : Job()
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val queue = Channel<Job>(Channel.UNLIMITED)
    private val fetching = java.util.Collections.synchronizedSet(mutableSetOf<String>())
    @Volatile private var cancelled = false
    private val pending = java.util.concurrent.atomic.AtomicInteger(0)
    private lateinit var app: Context
    private lateinit var store: Store
    private lateinit var history: Transfers
    var toast: (String) -> Unit = {}

    fun init(ctx: Context, store: Store, history: Transfers) {
        if (::app.isInitialized) return
        app = ctx.applicationContext; this.store = store; this.history = history
        val nm = app.getSystemService(NotificationManager::class.java)
        nm?.createNotificationChannel(NotificationChannel(CH_PROGRESS, "Передача файлов", NotificationManager.IMPORTANCE_LOW)
            .apply { description = "Ход передачи файлов между устройством и компьютером" })
        nm?.createNotificationChannel(NotificationChannel(CH_DONE, "Файлы с компьютера", NotificationManager.IMPORTANCE_DEFAULT)
            .apply { description = "Файлы, отправленные с компьютера через «Передачу файлов»" })
        scope.launch {
            for (job in queue) {
                cancelled = false
                runCatching { if (job is Job.Send) send(job) else fetch((job as Job.Fetch).api, job.item) }
                    .onFailure { e -> if (e !is CancelledByUser) toast("Передача не удалась: ${e.message}") }
                if (pending.decrementAndGet() <= 0) { pending.set(0); progress.value = null; stopService() }
            }
        }
    }

    fun send(api: Api, items: List<Item>, title: String) {
        if (items.isEmpty()) return
        pending.incrementAndGet(); queue.trySend(Job.Send(api, items, title)); startService()
    }

    /** Files the computer has waiting for this device (from /api/state). */
    fun fetch(api: Api, items: List<JSONObject>) {
        for (it in items) {
            val id = it.optString("id")
            if (id.isBlank() || !fetching.add(id)) continue
            pending.incrementAndGet(); queue.trySend(Job.Fetch(api, it)); startService()
        }
    }

    fun cancel() {
        cancelled = true
        while (true) { val j = queue.tryReceive().getOrNull() ?: break; pending.decrementAndGet(); if (j is Job.Fetch) fetching.remove(j.item.optString("id")) }
        toast("Передача отменена")
    }

    private class CancelledByUser : IOException("отменено")
    private fun check() { if (cancelled) throw CancelledByUser() }

    // ---------------- phone → computer ----------------
    private suspend fun send(job: Job.Send) {
        val total = job.items.sumOf { it.size.coerceAtLeast(0) }
        val t0 = System.currentTimeMillis()
        var before = 0L; var ok = 0; var last = ""
        for ((i, it) in job.items.withIndex()) {
            check()
            val label = (if (it.folder.isNotBlank()) it.folder + "/" + (if (it.rel.isNotBlank()) it.rel + "/" else "") else "") + it.name
            fun show(sent: Long, waiting: Boolean = false) {
                val secs = (System.currentTimeMillis() - t0) / 1000.0
                progress.value = Progress(true, job.title, label, i + 1, job.items.size, before + sent, total,
                    if (secs > 1) (before + sent) / secs else 0.0, waiting, (pending.get() - 1).coerceAtLeast(0))
            }
            show(0)
            val r = runCatching { sendOne(job.api, it) { b, w -> show(b, w) } }
            r.exceptionOrNull()?.let { if (it is CancelledByUser) throw it }
            if (r.isSuccess) { ok++; if (it.folder.isBlank()) history.add("out", it.name, it.size, it.uri.toString()) }
            else last = r.exceptionOrNull()?.message.orEmpty()
            before += it.size.coerceAtLeast(0)
        }
        job.items.firstOrNull()?.takeIf { it.folder.isNotBlank() }?.let { history.add("out", "📁 " + it.folder, total, "") }
        toast(when {
            ok == job.items.size && job.items.size == 1 -> "Готово: «Загрузки → TabDock» на компьютере"
            ok == job.items.size -> "Готово: ${job.title} — в «Загрузки → TabDock» на компьютере"
            else -> "Отправлено $ok из ${job.items.size}. $last"
        })
    }

    private fun sha256(b: ByteArray, n: Int) = MessageDigest.getInstance("SHA-256").apply { update(b, 0, n) }.digest()
        .joinToString("") { "%02x".format(it) }

    private fun skipFully(inp: InputStream, n: Long) {
        var left = n
        while (left > 0) {
            val s = inp.skip(left)
            if (s <= 0) { if (inp.read() < 0) throw IOException("файл короче, чем ожидалось"); left-- } else left -= s
        }
    }

    private fun readFully(inp: InputStream, b: ByteArray, want: Int): Int {
        var got = 0
        while (got < want) { val n = inp.read(b, got, want - got); if (n < 0) break; got += n }
        return got
    }

    /** One file in parts; after a network error it waits and asks the computer where to continue. */
    /** Size from the file itself when the app or folder that gave it did not say (some file pickers leave it out). */
    private fun realSize(uri: Uri): Long =
        runCatching { app.contentResolver.openFileDescriptor(uri, "r")!!.use { fd -> fd.statSize } }.getOrDefault(-1L)
            .takeIf { it >= 0 } ?: runCatching { app.contentResolver.openAssetFileDescriptor(uri, "r")!!.use { fd -> fd.length } }.getOrDefault(-1L)

    private suspend fun sendOne(api: Api, item: Item, onBytes: (Long, Boolean) -> Unit) {
        val it = if (item.size >= 0) item else item.copy(size = realSize(item.uri))
        if (it.size < 0) {          // the app that shared it does not say how big it is: one request, no resuming
            app.contentResolver.openInputStream(it.uri)!!.use { inp -> api.putFile(it.name, -1, inp) }
                .let { r -> if (!r.optBoolean("ok")) throw IOException(r.optString("message", "ошибка")) }
            return
        }
        val body = JSONObject().put("name", it.name).put("size", it.size).put("folder", it.folder).put("rel", it.rel).put("batch", it.batch)
        val start = try { api.post("/api/upload/start", body, 15000) } catch (e: Api.HttpError) {
            if (e.code == 404) {     // a computer with TabDock older than 0.16: one request, no resuming
                app.contentResolver.openInputStream(it.uri)!!.use { inp -> api.putFile(it.name, it.size, inp) }
                    .let { r -> if (!r.optBoolean("ok")) throw IOException(r.optString("message", "ошибка")) }
                return
            }
            throw e
        }
        if (!start.optBoolean("ok")) throw IOException(start.optString("message", "Компьютер не принял файл"))
        if (start.optBoolean("done")) return
        val id = start.getString("id")
        var offset = start.optLong("offset")
        var fails = 0
        val buf = ByteArray(PART)
        while (offset < it.size) {
            check()
            try {
                app.contentResolver.openInputStream(it.uri)!!.use { inp ->
                    skipFully(inp, offset)
                    while (offset < it.size) {
                        check()
                        val n = readFully(inp, buf, minOf(PART.toLong(), it.size - offset).toInt())
                        if (n <= 0) throw IOException("файл короче, чем ожидалось")
                        val (code, r) = api.putChunk(id, offset, buf, n, sha256(buf, n))
                        when (code) {
                            200 -> { offset = r.optLong("offset", offset + n); fails = 0; onBytes(offset, false); if (r.optBoolean("done")) return }
                            409, 422 -> { offset = r.optLong("offset", offset); return@use }        // reopen the file at the right place
                            404 -> throw IOException(r.optString("message", "передача не найдена"))
                            else -> throw IOException(r.optString("message", "HTTP $code"))
                        }
                    }
                }
            } catch (e: IOException) {
                if (e is CancelledByUser || e.message?.contains("не найдена") == true || ++fails > 60) throw e
                onBytes(offset, true)
                delay(minOf(30_000L, 1000L shl minOf(fails, 5)))
                runCatching { api.obj("/api/upload/status?id=$id", 8000) }.getOrNull()?.let { st ->
                    if (st.optBoolean("ok")) offset = st.optLong("offset", offset)
                }
            }
        }
    }

    // ---------------- computer → phone ----------------
    private suspend fun fetch(api: Api, it: JSONObject) {
        val id = it.optString("id"); val name = it.optString("name").ifBlank { "файл" }
        val size = it.optLong("size", -1); val folder = it.optString("folder"); val rel = it.optString("rel")
        val label = (if (folder.isNotBlank()) "$folder/" + (if (rel.isNotBlank()) "$rel/" else "") else "") + name
        try {
            val t0 = System.currentTimeMillis()
            val (uri, file) = target(id, name, folder, rel)
            var fails = 0
            while (true) {
                check()
                val have = written(uri, file)
                if (size >= 0 && have >= size) break
                try {
                    api.downloadFrom("/api/outbox/file?id=$id", have) { code, inp ->
                        val append = code == 206
                        open(uri, file, append).use { out ->
                            val b = ByteArray(256 * 1024); var done = if (append) have else 0L
                            while (true) {
                                check()
                                val n = inp.read(b); if (n < 0) break
                                out.write(b, 0, n); done += n
                                val secs = (System.currentTimeMillis() - t0) / 1000.0
                                progress.value = Progress(false, "С компьютера", label, 1, 1, done, size, if (secs > 1) (done - have) / secs else 0.0,
                                    queued = (pending.get() - 1).coerceAtLeast(0))
                            }
                        }
                    }
                    if (size < 0) break
                    fails = 0
                } catch (e: Api.HttpError) {
                    if (e.code == 416) break                 // everything is already here
                    throw e
                } catch (e: IOException) {
                    if (e is CancelledByUser || ++fails > 60) throw e
                    progress.value = progress.value?.copy(waiting = true)
                    delay(minOf(30_000L, 1000L shl minOf(fails, 5)))
                }
            }
            finish(uri)
            store.put("dl:$id", null)
            runCatching { api.post("/api/outbox", JSONObject().put("op", "done").put("id", id)) }
            history.add("in", label, size, uri.toString())
            toast("С компьютера: $label — в «Загрузках → TabDock»")
            notifyDone(label, uri)
        } finally { fetching.remove(id) }
    }

    /** The file being written, kept across restarts of the app so a download continues where it stopped. */
    private fun target(id: String, name: String, folder: String, rel: String): Pair<Uri, File?> {
        store.string("dl:$id")?.let { saved ->
            val u = Uri.parse(saved)
            if (u.scheme == "file") return u to File(u.path!!)
            if (runCatching { app.contentResolver.openFileDescriptor(u, "r")?.close() }.isSuccess) return u to null
        }
        val sub = listOf("TabDock", folder, rel).filter { it.isNotBlank() }.joinToString("/")
        val mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(name.substringAfterLast('.', "").lowercase()) ?: "application/octet-stream"
        val result: Pair<Uri, File?> = if (Build.VERSION.SDK_INT >= 29) {
            val v = ContentValues().apply {
                put(MediaStore.Downloads.DISPLAY_NAME, name)
                put(MediaStore.Downloads.MIME_TYPE, mime)
                put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/" + sub)
                put(MediaStore.Downloads.IS_PENDING, 1)
            }
            (app.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v) ?: throw IOException("нет доступа к «Загрузкам»")) to null
        } else {
            val dir = File(app.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), sub).apply { mkdirs() }
            var f = File(dir, name); var i = 2
            while (f.exists()) { f = File(dir, name.substringBeforeLast('.') + " ($i)." + name.substringAfterLast('.', "bin")); i++ }
            Uri.fromFile(f) to f
        }
        store.put("dl:$id", result.first.toString())
        return result
    }

    private fun written(uri: Uri, file: File?): Long =
        file?.length() ?: runCatching { app.contentResolver.openFileDescriptor(uri, "r")!!.use { it.statSize } }.getOrDefault(0L)

    private fun open(uri: Uri, file: File?, append: Boolean): java.io.OutputStream =
        if (file != null) java.io.FileOutputStream(file, append)
        else app.contentResolver.openOutputStream(uri, if (append) "wa" else "wt") ?: throw IOException("не открыть файл")

    private fun finish(uri: Uri) {
        if (Build.VERSION.SDK_INT >= 29 && uri.scheme == "content")
            app.contentResolver.update(uri, ContentValues().apply { put(MediaStore.Downloads.IS_PENDING, 0) }, null, null)
    }

    private fun shareable(uri: Uri): Uri = if (uri.scheme == "file") FileProvider.getUriForFile(app, app.packageName + ".files", File(uri.path!!)) else uri

    private fun notifyDone(name: String, saved: Uri) {
        if (Build.VERSION.SDK_INT >= 33 && app.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        val uri = shareable(saved)
        val mime = app.contentResolver.getType(uri) ?: "*/*"
        val open = PendingIntent.getActivity(app, name.hashCode(), Intent(Intent.ACTION_VIEW).setDataAndType(uri, mime)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE)
        val n = Notification.Builder(app, CH_DONE).setSmallIcon(R.drawable.ic_stat_tabdock)
            .setContentTitle("Файл с компьютера").setContentText(name).setContentIntent(open).setAutoCancel(true).build()
        runCatching { app.getSystemService(NotificationManager::class.java)?.notify(3000 + (name.hashCode() and 0xfff), n) }
    }

    // ---------------- folders on this device ----------------
    /** All files of a folder picked in the system dialog, with their paths inside it. */
    fun folderItems(ctx: Context, tree: Uri): Pair<String, List<Item>> {
        val cr = ctx.contentResolver
        val rootId = DocumentsContract.getTreeDocumentId(tree)
        var rootName = "Папка"
        cr.query(DocumentsContract.buildDocumentUriUsingTree(tree, rootId), arrayOf(DocumentsContract.Document.COLUMN_DISPLAY_NAME), null, null, null)
            ?.use { if (it.moveToFirst()) rootName = it.getString(0) ?: rootName }
        val batch = java.lang.Long.toString(System.currentTimeMillis(), 36)
        val out = mutableListOf<Item>()
        fun walk(docId: String, rel: String, depth: Int) {
            if (depth > 20 || out.size > 50_000) return
            cr.query(DocumentsContract.buildChildDocumentsUriUsingTree(tree, docId), arrayOf(
                DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                DocumentsContract.Document.COLUMN_MIME_TYPE, DocumentsContract.Document.COLUMN_SIZE), null, null, null)?.use { c ->
                while (c.moveToNext()) {
                    val id = c.getString(0) ?: continue; val name = c.getString(1) ?: continue
                    if (c.getString(2) == DocumentsContract.Document.MIME_TYPE_DIR) walk(id, if (rel.isEmpty()) name else "$rel/$name", depth + 1)
                    else {
                        val doc = DocumentsContract.buildDocumentUriUsingTree(tree, id)
                        // some phones' folder pickers leave the size out: ask the file itself (needed for parts and progress)
                        val size = if (c.isNull(3)) runCatching { cr.openFileDescriptor(doc, "r")!!.use { fd -> fd.statSize } }.getOrDefault(-1L) else c.getLong(3)
                        out += Item(doc, name, size, rootName, rel, batch)
                    }
                }
            }
        }
        walk(rootId, "", 0)
        return rootName to out
    }

    // ---------------- the service that keeps the app alive while files move ----------------
    private fun startService() {
        runCatching {
            if (Build.VERSION.SDK_INT >= 26) app.startForegroundService(Intent(app, TransferService::class.java))
        }   // not allowed while the app is in the background on newer Android: the transfer still runs, just without it
    }

    private fun stopService() { runCatching { app.stopService(Intent(app, TransferService::class.java)) } }

    fun notification(ctx: Context, p: Progress?): Notification {
        val open = PendingIntent.getActivity(ctx, 0, ctx.packageManager.getLaunchIntentForPackage(ctx.packageName), PendingIntent.FLAG_IMMUTABLE)
        val b = Notification.Builder(ctx, CH_PROGRESS).setSmallIcon(R.drawable.ic_stat_tabdock).setOngoing(true).setOnlyAlertOnce(true)
            .setContentIntent(open)
        if (p == null) return b.setContentTitle("Передача файлов").setContentText("Подготовка…").build()
        val pct = if (p.total > 0) (100 * p.done / p.total).toInt() else 0
        val speed = if (p.speed > 0) " · ${Fmt.bytes(p.speed)}/с" else ""
        return b.setContentTitle((if (p.out) "На компьютер" else "С компьютера") + (if (p.count > 1) " · ${p.index} из ${p.count}" else ""))
            .setContentText(if (p.waiting) "Нет связи — продолжу сам · ${p.file}" else "${Fmt.bytes(p.done.toDouble())} из ${Fmt.bytes(p.total.toDouble())}$speed · ${p.file}" +
                (if (p.queued > 0) " · ещё в очереди: ${p.queued}" else ""))
            .setProgress(100, pct, p.total <= 0).build()
    }
}

class TransferService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val n = TransferHub.notification(this, TransferHub.progress.value)
        if (Build.VERSION.SDK_INT >= 29) startForeground(TransferHub.NOTE_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        else startForeground(TransferHub.NOTE_ID, n)
        scope.launch {
            var last = 0L
            TransferHub.progress.collect { p ->
                val now = System.currentTimeMillis()
                if (now - last > 1000 || p == null) {
                    last = now
                    runCatching { getSystemService(NotificationManager::class.java)?.notify(TransferHub.NOTE_ID, TransferHub.notification(this@TransferService, p)) }
                }
            }
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() { scope.coroutineContext[kotlinx.coroutines.Job]?.cancel(); super.onDestroy() }
}
