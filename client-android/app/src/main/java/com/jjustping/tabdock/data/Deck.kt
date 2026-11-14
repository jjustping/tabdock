package com.jjustping.tabdock.data

import android.content.Context
import android.graphics.BitmapFactory
import android.util.LruCache
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONObject

enum class Conn { STARTING, NEED_PAIRING, CONNECTED, LOST }

/**
 * The whole client state: which server we talk to, the latest /api/all and /api/state,
 * polling, and every action the UI can trigger.
 */
class Deck(private val ctx: Context, private val scope: CoroutineScope) {
    val store = Store(ctx)
    val discovery = Discovery(ctx, store)
    init { Lan.init(ctx); Notify.init(ctx); com.jjustping.tabdock.ui.Themes.load(store) }
    val transfers = Transfers(store)
    private val receiver = Receiver(ctx, store, transfers)

    @Volatile var api: Api? = null
        private set
    val conn = MutableStateFlow(Conn.STARTING)
    val all = MutableStateFlow<JSONObject?>(null)
    val state = MutableStateFlow<JSONObject?>(null)
    val serverName = MutableStateFlow("")
    val toasts = MutableSharedFlow<String>(extraBufferCapacity = 8)
    val events = MutableSharedFlow<JSONObject>(extraBufferCapacity = 8)
    private val _skin = MutableStateFlow(store.skin)
    val skin: StateFlow<String?> = _skin
    private var poller: Job? = null
    private var lastEvent = (store.string("last_event") ?: "0").toInt()
    var visible = true
    /** When the data on screen was last received from the computer (ms); shown while offline. */
    val syncedAt = MutableStateFlow(0L)

    // ---------------- offline cache: the last data survives restarts and lost Wi-Fi ----------------
    private val cacheFile = java.io.File(ctx.filesDir, "last_all.json")
    private val imgDir = java.io.File(ctx.cacheDir, "img").apply { mkdirs() }
    init {
        runCatching {
            if (cacheFile.exists()) {
                val o = JSONObject(cacheFile.readText())
                all.value = o.optJSONObject("all"); state.value = o.optJSONObject("all")?.optJSONObject("state")
                syncedAt.value = o.optLong("at")
            }
        }
    }
    private fun saveCache(a: JSONObject) {
        syncedAt.value = System.currentTimeMillis()
        val text = JSONObject().put("at", syncedAt.value).put("all", a).toString()
        scope.launch(kotlinx.coroutines.Dispatchers.IO) { runCatching { cacheFile.writeText(text) } }
    }

    fun toast(s: String) { toasts.tryEmit(s) }
    fun setSkin(id: String) { store.skin = id; _skin.value = id }

    /** Start: reconnect to the last pinned server if it proves its identity, else show pairing. */
    fun start() = scope.launch {
        discovery.startNsd()
        // paired before and have cached data → show it and keep looking for the computer instead of the pairing screen
        if (!reconnect()) {
            conn.value = if (store.pins().length() > 0) Conn.LOST else Conn.NEED_PAIRING
            store.entry(store.current)?.let { serverName.value = it.optString("name") }
        }
        startPolling()
    }

    /** Bumped by every pairing: a slower reconnect that started earlier must not switch back to the old computer. */
    @Volatile private var pairGen = 0

    private suspend fun reconnect(): Boolean {
        val gen = pairGen
        val pins = store.pins()
        val order = listOfNotNull(store.current) + pins.keys().asSequence().filter { it != store.current }.toList()
        for (id in order) {
            val e = pins.optJSONObject(id) ?: continue
            val s = discovery.verify(e.optString("base")) ?: continue
            if (gen != pairGen) return true   // a QR code / link paired a computer meanwhile — it wins
            if (s.state == "pinned" && s.id == id) { useServer(e.optString("base"), e.optString("token"), e.optString("name"), e.optString("cert")); store.current = id; return true }
        }
        return false
    }

    private suspend fun useServer(base: String, token: String, name: String, cert: String) {
        api = Api(base, token, cert)
        serverName.value = name
        conn.value = Conn.CONNECTED
        loadAll()
    }

    /** Waiting for the computer to allow this device: the name shown on the waiting screen. */
    val approval = MutableStateFlow<String?>(null)
    private var approvalJob: Job? = null
    fun cancelApproval() { approvalJob?.cancel(); approval.value = null }

    /** Ask the computer for this device's own key, with the QR code's pairing code or the password. Null = sent, else the error. */
    private suspend fun requestAccess(base: String, proof: JSONObject, pin: String?, name: String): String? {
        pairGen++
        val a = Api(base, null, pin)
        val r = runCatching { a.post("/api/devices/request", proof.put("name", Lan.deviceName)) }
            .getOrElse { return if (it is javax.net.ssl.SSLException) "Это не тот компьютер: его сертификат не совпал с QR-кодом" else if (it is Api.HttpError) it.message else Lan.explain(it) }
        if (!r.optBoolean("ok")) return r.optString("message", "Не получилось")
        waitForApproval(base, r.getString("key"), a.certSeen.orEmpty(), name)
        return null
    }

    private fun waitForApproval(base: String, key: String, cert: String, name: String) {
        approvalJob?.cancel()
        approval.value = name
        approvalJob = scope.launch {
            val a = Api(base, key, cert)
            while (isActive) {
                delay(2000)
                val r = runCatching { a.obj("/api/devices/me") }
                if ((r.exceptionOrNull() as? Api.HttpError)?.code == 401) { approval.value = null; toast("Компьютер не разрешил это устройство"); return@launch }
                if (r.getOrNull()?.optString("status") == "ok") {
                    val pin = runCatching { a.obj("/api/pin") }.getOrNull() ?: continue
                    store.pin(pin.getString("id"), base, pin.optString("name"), pin.getString("key"), key, cert)
                    approval.value = null
                    useServer(base, key, pin.optString("name"), cert)
                    toast("Подключено: ${pin.optString("name")}")
                    return@launch
                }
            }
        }
    }

    /** A computer this device already has a key for. */
    fun connectKnown(id: String, onDone: () -> Unit) = scope.launch {
        val e = store.entry(id) ?: return@launch
        pairGen++
        store.current = id
        useServer(e.optString("base"), e.optString("token"), e.optString("name"), e.optString("cert"))
        onDone()
    }

    /** QR code / link "https://<ip>:<port>/?k=<code>&fp=<certificate>" → ask for access. False if the text is not a TabDock link. */
    fun pairFromLink(text: String): Boolean {
        val u = runCatching { android.net.Uri.parse(text.trim()) }.getOrNull() ?: return false
        val k = u.getQueryParameter("k") ?: return false
        val fp = u.getQueryParameter("fp")?.lowercase()
        if (u.scheme != "https" || u.host.isNullOrBlank() || k.length < 8 || fp?.length != 64) return false
        scope.launch { requestAccess("https://${u.host}:${if (u.port > 0) u.port else 8787}", JSONObject().put("k", k), fp, u.host!!)?.let { toast(it) } }
        return true
    }

    // ---------------- updates: the computer checks GitHub, the app asks the computer ----------------
    val update = MutableStateFlow<AppUpdate?>(null)
    private var updateAt = 0L
    fun checkUpdate(force: Boolean = false) = scope.launch {
        val a = api ?: return@launch
        if (!force && System.currentTimeMillis() - updateAt < 6 * 3600_000L) return@launch
        updateAt = System.currentTimeMillis()
        val u = Updater.fromServer(runCatching { a.obj("/api/update", 6000) }.getOrNull())
        if (u == null) { if (force) toast("У вас последняя версия"); return@launch }
        if (force || store.string("update_skip") != u.version) update.value = u
    }

    /** «Поделиться → TabDock»: files go to the computer's Downloads/TabDock, a link opens there, text goes to its clipboard. */
    fun share(intent: android.content.Intent) = scope.launch {
        val a = api ?: run { toast("Сначала подключитесь к компьютеру"); return@launch }
        val uris = buildList {
            if (intent.action == android.content.Intent.ACTION_SEND_MULTIPLE)
                androidx.core.content.IntentCompat.getParcelableArrayListExtra(intent, android.content.Intent.EXTRA_STREAM, android.net.Uri::class.java)?.let { addAll(it) }
            else androidx.core.content.IntentCompat.getParcelableExtra(intent, android.content.Intent.EXTRA_STREAM, android.net.Uri::class.java)?.let { add(it) }
        }
        if (uris.isNotEmpty()) { upload(a, uris); return@launch }
        val text = intent.getStringExtra(android.content.Intent.EXTRA_TEXT).orEmpty()
        if (text.isBlank()) { toast("Нечего отправлять"); return@launch }
        val kind = if (Regex("""^\s*https?://\S+\s*$""").matches(text) || intent.getStringExtra(android.content.Intent.EXTRA_SUBJECT) != null && text.contains("http")) "link" else "text"
        val r = runCatching { a.post("/api/send", JSONObject().put("kind", kind).put("value", text)) }.getOrElse { JSONObject().put("message", Lan.explain(it)) }
        toast(r.optString("message", "Готово"))
    }

    /** Files picked on the «Файлы» screen. */
    fun sendFiles(uris: List<android.net.Uri>) = scope.launch {
        val a = api ?: run { toast("Сначала подключитесь к компьютеру"); return@launch }
        upload(a, uris)
    }

    /** True while files are going to the computer (the «Файлы» screen shows it). */
    val sending = MutableStateFlow<String?>(null)

    private suspend fun upload(a: Api, uris: List<android.net.Uri>) {
        toast(if (uris.size == 1) "Отправляю на компьютер…" else "Отправляю ${uris.size} файла(ов)…")
        var ok = 0; var last = ""
        for ((i, u) in uris.withIndex()) {
            val (name, size) = queryName(u)
            sending.value = if (uris.size == 1) name else "${i + 1} из ${uris.size}: $name"
            val r = runCatching { ctx.contentResolver.openInputStream(u)!!.let { a.putFile(name, size, it) } }
                .getOrElse { JSONObject().put("ok", false).put("message", Lan.explain(it)) }
            if (r.optBoolean("ok")) { ok++; transfers.add("out", name, size, u.toString()) } else last = r.optString("message")
        }
        sending.value = null
        toast(if (ok == uris.size) (if (ok == 1) "Готово: «Загрузки → TabDock» на компьютере" else "Готово: $ok файла(ов) в «Загрузки → TabDock»")
              else "Отправлено $ok из ${uris.size}. $last")
    }

    private fun queryName(u: android.net.Uri): Pair<String, Long> {
        var name = u.lastPathSegment?.substringAfterLast('/') ?: "файл"; var size = -1L
        runCatching {
            ctx.contentResolver.query(u, arrayOf(android.provider.OpenableColumns.DISPLAY_NAME, android.provider.OpenableColumns.SIZE), null, null, null)?.use { cur ->
                if (cur.moveToFirst()) {
                    cur.getString(0)?.let { name = it }
                    if (!cur.isNull(1)) size = cur.getLong(1)
                }
            }
        }
        return name to size
    }

    fun login(server: FoundServer, password: String, done: (String) -> Unit) = scope.launch {
        done(requestAccess(server.base, JSONObject().put("password", password), server.cert.ifBlank { null }, server.name) ?: "ok")
    }

    fun refresh() = scope.launch { loadAll() }

    fun disconnect() { api = null; conn.value = Conn.NEED_PAIRING; all.value = null; state.value = null }

    suspend fun loadAll() {
        val a = api ?: return
        runCatching { a.obj("/api/all", 15000) }.onSuccess {
            all.value = it; it.optJSONObject("state")?.let { s -> state.value = s }
            saveCache(it); Notify.deadlines(ctx, store, it); checkUpdate()
        }
    }

    private fun startPolling() {
        poller?.cancel()
        poller = scope.launch {
            var tick = 0; var fails = 0
            while (isActive) {
                val a = api
                if (a == null && conn.value == Conn.LOST && ++tick % 4 == 0) reconnect()
                if (a != null) {
                    val r = runCatching { a.obj("/api/state", 3000) }
                    if (r.isSuccess) {
                        fails = 0
                        if (conn.value == Conn.LOST) { conn.value = Conn.CONNECTED; loadAll() }
                        val s = r.getOrThrow(); state.value = s; handleEvents(s)
                        s.optJSONArray("outbox")?.objs()?.takeIf { it.isNotEmpty() }?.let { files -> scope.launch { receiver.take(a, files) { toast(it) } } }
                        if (++tick % (if (visible) 12 else 2) == 0) loadAll()
                    } else if ((r.exceptionOrNull() as? Api.HttpError)?.code == 401) {
                        // switched off on the computer: this key will never work again
                        store.current?.let { store.forget(it) }
                        api = null; conn.value = Conn.NEED_PAIRING
                        toast("Это устройство отключено на компьютере. Подключите его заново")
                    } else if (++fails >= 3 && conn.value == Conn.CONNECTED) {
                        conn.value = Conn.LOST
                    } else if (conn.value == Conn.LOST && fails % 4 == 0) {
                        reconnect()   // the Mac came back on a new address, or another pinned Mac is here
                    }
                }
                delay(if (visible) 2500 else 30000)   // in the background: every 30 s, for notifications
            }
        }
    }

    private fun handleEvents(s: JSONObject) {
        val evs = s.optJSONArray("events") ?: return
        var max = lastEvent
        for (i in 0 until evs.length()) {
            val e = evs.getJSONObject(i); val id = e.optInt("id")
            if (id > lastEvent && System.currentTimeMillis() / 1000.0 - e.optDouble("at") < 600) {
                // only «export finished» shows the banner / notification; other events (a file sent from a phone…) are quiet
                if (e.optString("type") == "host_down" || e.optString("type") == "host_up") {
                    Notify.host(ctx, store, e)
                    if (visible) toast((if (e.optString("type") == "host_down") "Не отвечает: " else "Снова работает: ") + e.optString("name"))
                } else if (e.optString("type", "export_done") == "export_done") {
                    events.tryEmit(e)
                    if (!visible) Notify.exportDone(ctx, store, e)
                }
            }
            if (id > max) max = id
        }
        if (max < lastEvent) max = 0
        lastEvent = max; store.put("last_event", max.toString())
    }

    /** POST helper: shows the server message, refreshes data afterwards. */
    fun post(path: String, body: JSONObject, refresh: Boolean = true, onOk: (JSONObject) -> Unit = {}) = scope.launch {
        val a = api ?: return@launch
        runCatching { a.post(path, body) }
            .onSuccess { r -> r.optString("message").takeIf { it.isNotBlank() }?.let { toast(it) }; onOk(r); if (refresh) loadAll() }
            .onFailure { toast(it.message ?: "Ошибка") }
    }

    fun action(name: String, arg: String? = null) =
        post("/api/action", JSONObject().put("action", name).apply { arg?.let { put("arg", it) } }, refresh = false) { r ->
            if (r.has("awake")) state.value = state.value?.let { JSONObject(it.toString()).put("awake", r.optBoolean("awake")) }
        }

    fun media(cmd: String, value: Int? = null) =
        post("/api/media", JSONObject().put("cmd", cmd).apply { value?.let { put("value", it) } }, refresh = false) { r ->
            r.optJSONObject("media")?.let { m -> state.value = state.value?.let { JSONObject(it.toString()).put("media", m) } }
        }

    // ---------------- images (covers, app icons) ----------------
    private val images = object : LruCache<String, ImageBitmap>(96 * 1024 * 1024) {
        override fun sizeOf(key: String, value: ImageBitmap) = value.width * value.height * 4
    }
    fun cached(path: String?): ImageBitmap? = path?.let { images.get(it) }
    suspend fun image(path: String): ImageBitmap? {
        images.get(path)?.let { return it }
        // small pictures (covers, thumbnails, app icons) are also kept on disk for offline use; big previews are not
        val disk = if (path.startsWith("/api/cull/preview")) null else java.io.File(imgDir, Crypto.sha1(path))
        val a = api
        val b = (if (a != null) runCatching { a.bytes(path, 6000) }.getOrNull() else null)
            ?.also { bytes -> disk?.let { f -> scope.launch(kotlinx.coroutines.Dispatchers.IO) { runCatching { f.writeBytes(bytes) } } } }
            ?: disk?.takeIf { it.exists() }?.let { f -> runCatching { f.readBytes() }.getOrNull() }
            ?: return null
        val bmp = BitmapFactory.decodeByteArray(b, 0, b.size)?.asImageBitmap() ?: return null
        images.put(path, bmp); return bmp
    }
}
