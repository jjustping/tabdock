package com.jjustping.tabdeck.data

import org.json.JSONArray
import org.json.JSONObject
import java.util.Calendar

// Small, null-safe accessors over the server's JSON (the API is the same one the web UI uses).
fun JSONObject?.o(k: String): JSONObject? = this?.optJSONObject(k)
fun JSONObject?.a(k: String): JSONArray? = this?.optJSONArray(k)
fun JSONObject?.s(k: String, def: String = ""): String = this?.let { if (it.isNull(k)) def else it.optString(k, def) } ?: def
fun JSONObject?.d(k: String): Double? = this?.let { if (!it.has(k) || it.isNull(k)) null else it.optDouble(k).takeIf { v -> !v.isNaN() } }
fun JSONObject?.i(k: String, def: Int = 0): Int = this?.optInt(k, def) ?: def
fun JSONObject?.b(k: String): Boolean = this?.optBoolean(k) ?: false
fun JSONArray?.objs(): List<JSONObject> = if (this == null) emptyList() else (0 until length()).mapNotNull { optJSONObject(it) }
fun JSONArray?.strs(): List<String> = if (this == null) emptyList() else (0 until length()).map { optString(it) }
fun JSONArray?.nums(): List<Double> = if (this == null) emptyList() else (0 until length()).map { optDouble(it) }

object Fmt {
    val DAYS = listOf("воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота")
    val DS = listOf("вс", "пн", "вт", "ср", "чт", "пт", "сб")
    val MON = listOf("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря")
    fun pad(n: Int) = n.toString().padStart(2, '0')
    fun bytes(b: Double?): String {
        if (b == null) return "—"
        var v = b; val u = listOf("Б", "КБ", "МБ", "ГБ", "ТБ"); var i = 0
        while (v >= 1000 && i < 4) { v /= 1000; i++ }
        return (if (v >= 100 || i == 0) "%.0f" else "%.1f").format(v) + " " + u[i]
    }
    fun uptime(s: Double?): String {
        if (s == null) return "—"; val t = s.toLong()
        val d = t / 86400; val h = t % 86400 / 3600; val m = t % 3600 / 60
        return (if (d > 0) "$d д " else "") + "$h ч $m мин"
    }
    fun dur(s: Double?): String { if (s == null) return ""; val t = s.toInt().coerceAtLeast(0); return "${t / 60}:${pad(t % 60)}" }
    fun date(ts: Double?): String {
        if (ts == null) return ""; val c = Calendar.getInstance().apply { timeInMillis = (ts * 1000).toLong() }
        return "${c.get(Calendar.DAY_OF_MONTH)} ${MON[c.get(Calendar.MONTH)]}"
    }
    fun today(off: Int = 0): String {
        val c = Calendar.getInstance().apply { add(Calendar.DAY_OF_MONTH, off) }
        return "${c.get(Calendar.YEAR)}-${pad(c.get(Calendar.MONTH) + 1)}-${pad(c.get(Calendar.DAY_OF_MONTH))}"
    }
    /** "сегодня", "завтра", "просрочено · 06.11", "пн, 9 ноября" + severity 0..2 */
    fun due(d: String): Pair<String, Int> {
        val t = today(); val tm = today(1)
        if (d < t) return "просрочено · ${d.substring(8)}.${d.substring(5, 7)}" to 2
        if (d == t) return "сегодня" to 1
        if (d == tm) return "завтра" to 0
        val c = Calendar.getInstance().apply { set(d.substring(0, 4).toInt(), d.substring(5, 7).toInt() - 1, d.substring(8).toInt()) }
        return "${DS[c.get(Calendar.DAY_OF_WEEK) - 1]}, ${c.get(Calendar.DAY_OF_MONTH)} ${MON[c.get(Calendar.MONTH)]}" to 0
    }
}

fun weatherIcon(code: Int): String = when {
    code == 0 -> "sun"; code <= 2 -> "cloudsun"; code == 3 -> "cloud"; code == 45 || code == 48 -> "fog"
    code in 71..77 || code == 85 || code == 86 -> "snow"; code >= 95 -> "storm"; else -> "rain"
}

val STATUS = linkedMapOf("new" to "Не начато", "selecting" to "Отбор", "editing" to "В работе", "done" to "Готово", "delivered" to "Сдано")
