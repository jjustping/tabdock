package com.jjustping.tabdock.data

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.Inet4Address
import java.net.NetworkInterface
import java.net.URL
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Collections
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * The Wi-Fi network itself. A VPN on the phone (corporate, "unblock" apps…) often swallows LAN traffic too;
 * opening connections on the Wi-Fi network directly reaches the computer anyway when the VPN allows bypass.
 */
object Lan {
    @Volatile var wifi: android.net.Network? = null
    @Volatile var vpn = false
    /** "Honor HEY2-W09", "Google Pixel 8" … (ASCII only: it goes into an HTTP header) */
    val deviceName: String by lazy {
        val m = android.os.Build.MANUFACTURER.replaceFirstChar { it.uppercase() }; val model = android.os.Build.MODEL
        (if (model.startsWith(m, ignoreCase = true)) model else "$m $model").filter { it.code in 32..126 }.take(60)
    }
    fun init(ctx: Context) {
        val cm = ctx.getSystemService(Context.CONNECTIVITY_SERVICE) as android.net.ConnectivityManager
        val req = android.net.NetworkRequest.Builder().addTransportType(android.net.NetworkCapabilities.TRANSPORT_WIFI).build()
        runCatching { cm.registerNetworkCallback(req, object : android.net.ConnectivityManager.NetworkCallback() {
            override fun onAvailable(n: android.net.Network) { wifi = n }
            override fun onLost(n: android.net.Network) { if (wifi == n) wifi = null }
        }) }
        runCatching { cm.registerDefaultNetworkCallback(object : android.net.ConnectivityManager.NetworkCallback() {
            override fun onCapabilitiesChanged(n: android.net.Network, c: android.net.NetworkCapabilities) {
                vpn = c.hasTransport(android.net.NetworkCapabilities.TRANSPORT_VPN)
            }
        }) }
    }
    private val private = Regex("""^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.)""")
    fun open(u: URL): java.net.URLConnection {
        val w = wifi
        if (w != null && private.containsMatchIn(u.host)) runCatching { return w.openConnection(u) }
        return u.openConnection()
    }
    const val VPN_HINT = "На этом устройстве включён VPN, и он не пускает в домашнюю сеть. " +
        "В настройках VPN-клиента добавьте TabDock в исключения."
    fun explain(e: Throwable): String =
        if (vpn) "Не достучаться до компьютера. $VPN_HINT"
        else "Не удалось подключиться: компьютер не отвечает (${e.message?.substringBefore(" from ") ?: "нет ответа"})"
}

/** HTTP client for one TabDock server. The access key goes in the X-Dock-Key header. */
class Api(val base: String, @Volatile var key: String?) {

    class HttpError(val code: Int, msg: String) : Exception(msg)

    private fun open(path: String, timeoutMs: Int): HttpURLConnection {
        val c = Lan.open(URL(base.trimEnd('/') + path)) as HttpURLConnection
        c.connectTimeout = timeoutMs
        c.readTimeout = timeoutMs * 3
        key?.let { c.setRequestProperty("X-Dock-Key", it) }
        c.setRequestProperty("X-Dock-Device", Lan.deviceName)   // shown in the computer's menu-bar icon
        return c
    }

    suspend fun bytes(path: String, timeoutMs: Int = 4000): ByteArray = withContext(Dispatchers.IO) {
        val c = open(path, timeoutMs)
        try {
            if (c.responseCode != 200) throw HttpError(c.responseCode, "HTTP ${c.responseCode}")
            c.inputStream.use { it.readBytes() }
        } finally { c.disconnect() }
    }

    suspend fun text(path: String, timeoutMs: Int = 4000): String = String(bytes(path, timeoutMs), Charsets.UTF_8)
    suspend fun obj(path: String, timeoutMs: Int = 4000): JSONObject = JSONObject(text(path, timeoutMs))
    suspend fun arr(path: String, timeoutMs: Int = 4000): JSONArray = JSONArray(text(path, timeoutMs))

    suspend fun post(path: String, body: JSONObject, timeoutMs: Int = 6000): JSONObject = withContext(Dispatchers.IO) {
        val c = open(path, timeoutMs)
        try {
            c.requestMethod = "POST"
            c.doOutput = true
            c.setRequestProperty("Content-Type", "application/json")
            c.outputStream.use { it.write(body.toString().toByteArray()) }
            val stream = if (c.responseCode in 200..299) c.inputStream else c.errorStream
            val txt = stream?.use { String(it.readBytes()) } ?: "{}"
            if (c.responseCode !in 200..299) throw HttpError(c.responseCode, JSONObject(txt).optString("error", "HTTP ${c.responseCode}"))
            JSONObject(txt)
        } finally { c.disconnect() }
    }

    /** Computer → phone: stream a file into [out] (no size limit, no buffering in memory). */
    fun download(path: String, out: java.io.OutputStream) {   // call from Dispatchers.IO
        val c = open(path, 15000)
        try {
            c.readTimeout = 120000
            if (c.responseCode != 200) throw HttpError(c.responseCode, "HTTP ${c.responseCode}")
            c.inputStream.use { it.copyTo(out, 256 * 1024) }
        } finally { c.disconnect() }
    }

    /** Phone → computer: stream a file to ~/Downloads/TabDock on the computer. */
    suspend fun putFile(name: String, length: Long, input: java.io.InputStream): JSONObject = withContext(Dispatchers.IO) {
        val c = open("/api/send/file?name=" + java.net.URLEncoder.encode(name, "UTF-8"), 15000)
        try {
            c.requestMethod = "PUT"; c.doOutput = true; c.readTimeout = 120000
            c.setRequestProperty("Content-Type", "application/octet-stream")
            if (length >= 0) c.setFixedLengthStreamingMode(length) else c.setChunkedStreamingMode(256 * 1024)
            c.outputStream.use { out -> input.use { it.copyTo(out, 256 * 1024) } }
            val stream = if (c.responseCode in 200..299) c.inputStream else c.errorStream
            JSONObject(stream?.use { String(it.readBytes()) } ?: "{}")
        } finally { c.disconnect() }
    }

    /** Password sign-in: the server answers with a cookie that carries the access key. */
    suspend fun login(password: String): Pair<String?, String> = withContext(Dispatchers.IO) {
        val c = open("/api/login", 5000)
        try {
            c.requestMethod = "POST"; c.doOutput = true
            c.setRequestProperty("Content-Type", "application/json")
            c.outputStream.use { it.write(JSONObject().put("password", password).toString().toByteArray()) }
            val stream = if (c.responseCode in 200..299) c.inputStream else c.errorStream
            val r = JSONObject(stream?.use { String(it.readBytes()) } ?: "{}")
            val cookie = c.headerFields.entries.filter { it.key.equals("Set-Cookie", true) }.flatMap { it.value }
                .firstOrNull { it.startsWith("dock_k=") }
            val token = cookie?.substringAfter("dock_k=")?.substringBefore(";")
            if (r.optBoolean("ok") && !token.isNullOrBlank()) token to "ok" else null to r.optString("message", "Не получилось")
        } finally { c.disconnect() }
    }
}

/** A server seen on the network (Bonjour or subnet probe), verified against the pinned identity. */
data class FoundServer(val base: String, val name: String, val model: String, val id: String,
                       val state: String /* pinned | unknown | mismatch */, val hasPassword: Boolean)

object Crypto {
    fun nonce(): String = ByteArray(16).also { SecureRandom().nextBytes(it) }.joinToString("") { "%02x".format(it) }
    fun hmac(key: String, msg: String): String {
        val m = Mac.getInstance("HmacSHA256")
        m.init(SecretKeySpec(key.toByteArray(), "HmacSHA256"))
        return m.doFinal(msg.toByteArray()).joinToString("") { "%02x".format(it) }
    }
    fun same(a: String, b: String) = MessageDigest.isEqual(a.toByteArray(), b.toByteArray())
    fun sha1(s: String): String = MessageDigest.getInstance("SHA-1").digest(s.toByteArray()).joinToString("") { "%02x".format(it) }
}

/** Locally stored servers: identity pins (TOFU) and access keys. */
class Store(ctx: Context) {
    private val p = ctx.getSharedPreferences("tabdock", Context.MODE_PRIVATE).also { now ->
        // one-time move from the pre-0.9 name, so paired computers and settings survive the update
        val old = ctx.getSharedPreferences("tabdeck", Context.MODE_PRIVATE)
        // (the old WebView app also used "tabdock" with another format — the 0.8 data wins and replaces it)
        if (old.all.isNotEmpty()) {
            val e = now.edit().clear()
            for ((k, v) in old.all) when (v) { is String -> e.putString(k, v); is Boolean -> e.putBoolean(k, v); is Int -> e.putInt(k, v); is Long -> e.putLong(k, v); is Float -> e.putFloat(k, v) }
            e.apply(); old.edit().clear().apply()
        }
    }
    fun pins(): JSONObject = runCatching { JSONObject(p.getString("pins", "{}")!!) }.getOrDefault(JSONObject())
    fun savePins(o: JSONObject) = p.edit().putString("pins", o.toString()).apply()
    var current: String?
        get() = p.getString("current", null)
        set(v) = p.edit().putString("current", v).apply()
    var skin: String?
        get() = p.getString("skin", null)
        set(v) = p.edit().putString("skin", v).apply()
    var space: String?
        get() = p.getString("space", null)
        set(v) = p.edit().putString("space", v).apply()
    fun string(k: String): String? = p.getString(k, null)
    fun put(k: String, v: String?) = p.edit().putString(k, v).apply()

    fun pin(id: String, base: String, name: String, proofKey: String, token: String) {
        val o = pins()
        o.put(id, JSONObject().put("base", base).put("name", name).put("key", proofKey).put("token", token))
        savePins(o); current = id
    }
    fun forget(id: String) { val o = pins(); o.remove(id); savePins(o); if (current == id) current = null }
    fun entry(id: String?): JSONObject? = id?.let { pins().optJSONObject(it) }
}

class Discovery(private val ctx: Context, private val store: Store) {
    private val _servers = MutableStateFlow<List<FoundServer>>(emptyList())
    val servers: StateFlow<List<FoundServer>> = _servers
    private val _scanning = MutableStateFlow(0f)
    val scanning: StateFlow<Float> = _scanning
    private var nsd: NsdManager? = null
    private var listener: NsdManager.DiscoveryListener? = null
    private var lock: WifiManager.MulticastLock? = null
    private val nsdBases = Collections.synchronizedSet(mutableSetOf<String>())

    /** Ask the server to prove it knows our pinned key (HMAC over nonce|id). */
    suspend fun verify(base: String): FoundServer? {
        val n = Crypto.nonce()
        val h = runCatching { Api(base, null).obj("/api/hello?nonce=$n", 1500) }.getOrNull() ?: return null
        if (h.optString("app") != "tabdock") return null
        val id = h.optString("id")
        val pins = store.pins()
        val state = when {
            pins.has(id) -> {
                val want = Crypto.hmac(pins.getJSONObject(id).getString("key"), "$n|$id")
                if (Crypto.same(want, h.optString("proof"))) {
                    pins.getJSONObject(id).put("base", base); store.savePins(pins); "pinned"
                } else "mismatch"
            }
            pins.keys().asSequence().any { pins.getJSONObject(it).optString("base") == base } -> "mismatch"
            else -> "unknown"
        }
        return FoundServer(base, h.optString("name", base), h.optString("model"), id, state, h.optBoolean("password"))
    }

    private fun add(s: FoundServer) {
        _servers.value = (_servers.value.filter { it.base != s.base } + s)
            .sortedWith(compareBy({ it.state != "pinned" }, { it.name }))
    }

    suspend fun refreshKnown() {
        val pins = store.pins()
        for (id in pins.keys()) verify(pins.getJSONObject(id).getString("base"))?.let { add(it) }
    }

    fun startNsd() {
        if (listener != null) return
        runCatching {
            val wm = ctx.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            lock = wm.createMulticastLock("tabdock").apply { setReferenceCounted(false); acquire() }
            val m = ctx.getSystemService(Context.NSD_SERVICE) as NsdManager
            nsd = m
            val l = object : NsdManager.DiscoveryListener {
                override fun onStartDiscoveryFailed(t: String?, e: Int) {}
                override fun onStopDiscoveryFailed(t: String?, e: Int) {}
                override fun onDiscoveryStarted(t: String?) {}
                override fun onDiscoveryStopped(t: String?) {}
                override fun onServiceLost(i: NsdServiceInfo?) {}
                override fun onServiceFound(i: NsdServiceInfo) {
                    @Suppress("DEPRECATION")
                    m.resolveService(i, object : NsdManager.ResolveListener {
                        override fun onResolveFailed(si: NsdServiceInfo?, e: Int) {}
                        override fun onServiceResolved(si: NsdServiceInfo) {
                            @Suppress("DEPRECATION") val a = si.host
                            if (a is Inet4Address) nsdBases.add("http://${a.hostAddress}:${si.port}")
                        }
                    })
                }
            }
            listener = l
            m.discoverServices("_tabdock._tcp", NsdManager.PROTOCOL_DNS_SD, l)
        }
    }

    fun stopNsd() {
        runCatching { listener?.let { nsd?.stopServiceDiscovery(it) } }
        listener = null
        lock?.takeIf { it.isHeld }?.release()
    }

    /** Bonjour results + every address of the local /24 on port 8787. */
    suspend fun scan() = coroutineScope {
        refreshKnown()
        for (b in nsdBases.toList()) verify(b)?.let { add(it) }
        val prefixes = mutableSetOf<String>()
        deviceIp()?.substringBeforeLast('.')?.let { prefixes += it }
        store.pins().let { p -> p.keys().forEach { k -> p.getJSONObject(k).optString("base").removePrefix("http://").substringBefore(':').substringBeforeLast('.').takeIf { it.isNotBlank() }?.let { prefixes += it } } }
        val targets = prefixes.flatMap { pre -> (1..254).map { "http://$pre.$it:8787" } }
        val sem = Semaphore(48)
        var done = 0
        targets.map { b ->
            async(Dispatchers.IO) {
                sem.withPermit { verify(b)?.let { add(it) } }
                done++; _scanning.value = done.toFloat() / targets.size
            }
        }.awaitAll()
        for (b in nsdBases.toList()) verify(b)?.let { add(it) }
        _scanning.value = 0f
    }

    companion object {
        fun deviceIp(): String? = runCatching {
            NetworkInterface.getNetworkInterfaces().toList().filter { it.isUp && !it.isLoopback }
                .flatMap { it.inetAddresses.toList() }.firstOrNull { it is Inet4Address && it.isSiteLocalAddress }?.hostAddress
        }.getOrNull()
    }
}

fun ByteArray.toImageBytes() = ByteArrayOutputStream().also { it.write(this) }.toByteArray()
