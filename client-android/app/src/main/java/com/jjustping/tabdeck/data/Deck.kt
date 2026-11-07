package com.jjustping.tabdeck.data

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

    fun toast(s: String) { toasts.tryEmit(s) }
    fun setSkin(id: String) { store.skin = id; _skin.value = id }

    /** Start: reconnect to the last pinned server if it proves its identity, else show pairing. */
    fun start() = scope.launch {
        discovery.startNsd()
        if (!reconnect()) conn.value = Conn.NEED_PAIRING
        startPolling()
    }

    private suspend fun reconnect(): Boolean {
        val pins = store.pins()
        val order = listOfNotNull(store.current) + pins.keys().asSequence().filter { it != store.current }.toList()
        for (id in order) {
            val e = pins.optJSONObject(id) ?: continue
            val s = discovery.verify(e.optString("base")) ?: continue
            if (s.state == "pinned" && s.id == id) { useServer(e.optString("base"), e.optString("token"), e.optString("name")); store.current = id; return true }
        }
        return false
    }

    private suspend fun useServer(base: String, token: String, name: String) {
        api = Api(base, token)
        serverName.value = name
        conn.value = Conn.CONNECTED
        loadAll()
    }

    /** Pair with a key (QR link or adb), then pin the server's identity. */
    fun pairWithKey(base: String, key: String) = scope.launch {
        val a = Api(base, key)
        val pin = runCatching { a.obj("/api/pin") }.getOrElse { toast("Не удалось подключиться: ${it.message}"); return@launch }
        store.pin(pin.getString("id"), base, pin.optString("name"), pin.getString("key"), key)
        useServer(base, key, pin.optString("name"))
        toast("Подключено: ${pin.optString("name")}")
    }

    fun login(server: FoundServer, password: String, done: (String) -> Unit) = scope.launch {
        val (token, msg) = runCatching { Api(server.base, null).login(password) }.getOrElse { null to (it.message ?: "Нет связи") }
        if (token == null) { done(msg); return@launch }
        pairWithKey(server.base, token).join(); done("ok")
    }

    fun refresh() = scope.launch { loadAll() }

    fun disconnect() { api = null; conn.value = Conn.NEED_PAIRING; all.value = null; state.value = null }

    suspend fun loadAll() {
        val a = api ?: return
        runCatching { a.obj("/api/all", 8000) }.onSuccess { all.value = it; it.optJSONObject("state")?.let { s -> state.value = s } }
    }

    private fun startPolling() {
        poller?.cancel()
        poller = scope.launch {
            var tick = 0; var fails = 0
            while (isActive) {
                val a = api
                if (a != null && visible) {
                    val r = runCatching { a.obj("/api/state", 3000) }
                    if (r.isSuccess) {
                        fails = 0
                        if (conn.value == Conn.LOST) { conn.value = Conn.CONNECTED; loadAll() }
                        val s = r.getOrThrow(); state.value = s; handleEvents(s)
                        if (++tick % 12 == 0) loadAll()
                    } else if (++fails >= 3 && conn.value == Conn.CONNECTED) {
                        conn.value = Conn.LOST
                    } else if (conn.value == Conn.LOST && fails % 4 == 0) {
                        reconnect()   // the Mac came back on a new address, or another pinned Mac is here
                    }
                }
                delay(2500)
            }
        }
    }

    private fun handleEvents(s: JSONObject) {
        val evs = s.optJSONArray("events") ?: return
        var max = lastEvent
        for (i in 0 until evs.length()) {
            val e = evs.getJSONObject(i); val id = e.optInt("id")
            if (id > lastEvent && System.currentTimeMillis() / 1000.0 - e.optDouble("at") < 600) events.tryEmit(e)
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
    private val images = LruCache<String, ImageBitmap>(80)
    suspend fun image(path: String): ImageBitmap? {
        images.get(path)?.let { return it }
        val a = api ?: return null
        val b = runCatching { a.bytes(path, 6000) }.getOrNull() ?: return null
        val bmp = BitmapFactory.decodeByteArray(b, 0, b.size)?.asImageBitmap() ?: return null
        images.put(path, bmp); return bmp
    }
}
