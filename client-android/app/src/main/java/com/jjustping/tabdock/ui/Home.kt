package com.jjustping.tabdock.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jjustping.tabdock.data.a
import com.jjustping.tabdock.data.i
import com.jjustping.tabdock.data.o
import com.jjustping.tabdock.data.objs
import com.jjustping.tabdock.data.s
import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.abs
import kotlin.random.Random


/** A long press opens these widgets' own settings; on the others it turns on the edit mode of the space. */
private val WIDGETS_WITH_SETTINGS = setOf("buttons", "note", "shortcuts")
private val TEMPLATES = linkedMapOf(
    "photo" to Triple("Фото", "aperture", listOf(Triple("reminders", 4, 6), Triple("shoots", 4, 4), Triple("player", 4, 3), Triple("quick", 4, 3), Triple("calendar", 4, 2))),
    "work" to Triple("Работа", "check", listOf(Triple("reminders", 4, 6), Triple("note", 4, 4), Triple("clock", 4, 2), Triple("deadlines", 4, 2), Triple("events", 4, 2), Triple("focus", 4, 2))),
    "fun" to Triple("Отдых", "note", listOf(Triple("clock", 6, 2), Triple("weather", 6, 2), Triple("player", 6, 4), Triple("quick", 6, 4))),
    "admin" to Triple("Система", "computer", listOf(Triple("macstat", 6, 3), Triple("network", 6, 3), Triple("disks", 6, 3), Triple("shortcuts", 6, 3))),
)

private fun rid() = (1..8).map { "abcdefghijklmnopqrstuvwxyz0123456789"[Random.nextInt(36)] }.joinToString("")
fun fromTemplate(k: String): JSONObject {
    val (n, ic, ws) = TEMPLATES.getValue(k)
    return JSONObject().put("id", k + rid().take(4)).put("name", n).put("icon", ic)
        .put("widgets", JSONArray(ws.map { (t, w, h) -> JSONObject().put("id", rid()).put("type", t).put("w", w).put("h", h).put("opts", JSONObject()) }))
}

fun spacesOf(all: JSONObject?): List<JSONObject> = all.o("config").a("spaces").objs().ifEmpty { listOf(fromTemplate("photo")) }

/** CSS-grid-like "dense" placement so the layout matches the web UI. */
private fun place(ws: List<JSONObject>, cols: Int): List<IntArray> {
    val occ = mutableListOf<BooleanArray>()
    fun free(r: Int, c: Int, w: Int, h: Int): Boolean {
        for (y in r until r + h) { while (occ.size <= y) occ += BooleanArray(cols); for (x in c until c + w) if (occ[y][x]) return false }
        return true
    }
    return ws.map { wj ->
        val w = if (cols == 12) wj.i("w", 4).coerceIn(2, 12) else (wj.i("w", 4) * cols / 12.0).toInt().coerceIn(2, cols)
        val h = if (cols < 12) wj.i("h", 2).coerceIn(2, 4) else wj.i("h", 2).coerceIn(1, 8)   // phone / narrow: no giant cards
        var r = 0
        while (true) {
            var placed = -1
            for (c in 0..cols - w) if (free(r, c, w, h)) { placed = c; break }
            if (placed >= 0) { for (y in r until r + h) for (x in placed until placed + w) occ[y][x] = true; return@map intArrayOf(r, placed, w, h) }
            r++
        }
        @Suppress("UNREACHABLE_CODE") intArrayOf(0, 0, w, h)
    }
}

@Composable
fun HomeScreen(c: Ctx, dialogs: Dialogs) {
    val s = LocalSkin.current
    val spaces = spacesOf(c.all)
    var cur by remember { mutableStateOf(c.deck.store.space) }
    val sp = spaces.firstOrNull { it.s("id") == cur } ?: spaces.first()
    var edit by remember { mutableStateOf(false) }
    fun select(id: String) { cur = id; c.deck.store.space = id }
    fun save(newSpaces: List<JSONObject>) {
        val cfg = c.all.o("config"); cfg?.put("spaces", JSONArray(newSpaces))
        c.deck.post("/api/config", JSONObject().put("spaces", JSONArray(newSpaces)), refresh = true)
    }
    fun mutate(fn: (JSONObject, MutableList<JSONObject>) -> Unit) {
        val copy = spaces.map { JSONObject(it.toString()) }.toMutableList()
        val target = copy.firstOrNull { it.s("id") == sp.s("id") } ?: copy.first()
        fn(target, copy); save(copy)
    }

    Column(Modifier.fillMaxSize()) {
        // space switcher
        Row(Modifier.fillMaxWidth().height(48.dp), verticalAlignment = Alignment.CenterVertically) {
            Row(Modifier.weight(1f).horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for (x in spaces) {
                    val on = x.s("id") == sp.s("id")
                    Row(Modifier.clip(RoundedCornerShape(999.dp)).background(if (on) s.inner else Color.Transparent)
                        .border(1.dp, if (on) s.accent else s.border, RoundedCornerShape(999.dp)).clickable { select(x.s("id")) }
                        .padding(horizontal = 16.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Ic(x.s("icon", "home"), 18.dp, if (on) s.accent else s.muted); Spacer(Modifier.width(8.dp))
                        T(x.s("name"), 15.sp, if (on) s.text else s.muted, maxLines = 1)
                    }
                }
            }
            if (edit) {
                Btn(if (LocalCompact.current) null else "Виджет", "plus") { dialogs.catalog(sp) { type, def -> mutate { t, _ -> t.getJSONArray("widgets").put(JSONObject().put("id", rid()).put("type", type).put("w", def.w).put("h", def.h).put("opts", JSONObject())) } } }
                Spacer(Modifier.width(8.dp))
                Btn(if (LocalCompact.current) null else "Пространство", "gear") { dialogs.space(sp, spaces, TEMPLATES.mapValues { it.value.first },
                    onSave = { name, icon -> mutate { t, _ -> t.put("name", name).put("icon", icon) } },
                    onAdd = { key -> val n = if (key == null) JSONObject().put("id", rid()).put("name", "Новое").put("icon", "home").put("widgets", JSONArray()) else fromTemplate(key)
                        save(spaces + n); select(n.s("id")) },
                    onDelete = { val left = spaces.filter { it.s("id") != sp.s("id") }; save(left); select(left.first().s("id")) },
                    onMove = { d -> val l = spaces.toMutableList(); val i = l.indexOfFirst { it.s("id") == sp.s("id") }; val j = i + d
                        if (j in l.indices) { val t = l[i]; l[i] = l[j]; l[j] = t; save(l) } }) }
                Spacer(Modifier.width(8.dp))
                Btn("Готово", primary = true) { edit = false }
            } else Box(Modifier.size(44.dp).clip(CircleShape).border(1.dp, s.border, CircleShape).clickable { edit = true }, contentAlignment = Alignment.Center) {
                Ic("pencil", 20.dp, s.muted)
            }
        }
        Spacer(Modifier.height(8.dp))
        val widgets = sp.a("widgets").objs()
        BoxWithConstraints(Modifier.fillMaxSize().pointerInput(spaces.map { it.s("id") }, sp.s("id"), edit) {
            if (edit) return@pointerInput
            var dx = 0f
            detectHorizontalDragGestures(onDragStart = { dx = 0f }, onDragEnd = {
                if (abs(dx) > 160) { val i = spaces.indexOfFirst { it.s("id") == sp.s("id") }; select(spaces[(i + (if (dx < 0) 1 else -1) + spaces.size) % spaces.size].s("id")) }
            }) { _, d -> dx += d }
        }) {
            val phone = LocalCompact.current
            // phone: one column upright, two columns lying sideways; small tablets: 4; tablets: the 12×6 grid
            val cols = when { maxWidth < 600.dp -> 2; phone || maxWidth < 700.dp -> 4; else -> 12 }
            val gap = 12.dp
            val cellW = (maxWidth - gap * (cols - 1)) / cols
            val cellH = when { cols == 12 -> (maxHeight - gap * 5) / 6; cols == 2 || phone -> 96.dp; else -> 130.dp }
            val slots = place(widgets, cols)
            val rows = (slots.maxOfOrNull { it[0] + it[3] } ?: 0).coerceAtLeast(1)
            if (widgets.isEmpty()) Empty("Пространство пустое — нажмите карандаш и добавьте виджеты")
            Box(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).height(cellH * rows + gap * (rows - 1))) {
                widgets.forEachIndexed { idx, wj ->
                    val (r, col, w, h) = slots[idx].let { listOf(it[0], it[1], it[2], it[3]) }
                    val mod = Modifier.offset(x = (cellW + gap) * col, y = (cellH + gap) * r).size(cellW * w + gap * (w - 1), cellH * h + gap * (h - 1))
                    val settings = wj.s("type") in WIDGETS_WITH_SETTINGS
                    Box(mod.onLongHold(!edit, except = { p -> wj.s("type") == "reminders" && p.y < 240f }) { if (settings) c.editWidget(wj) else edit = true }) {
                        Widget(wj.s("type"), wj, c, Modifier.fillMaxSize())
                        if (edit) EditOverlay(wj, idx, widgets.size, onAct = { act ->
                            mutate { t, _ ->
                                val arr = t.getJSONArray("widgets"); val list = arr.objs().toMutableList()
                                val me = list[idx]
                                when (act) {
                                    "left" -> if (idx > 0) { list[idx] = list[idx - 1]; list[idx - 1] = me }
                                    "right" -> if (idx < list.size - 1) { list[idx] = list[idx + 1]; list[idx + 1] = me }
                                    "w-" -> me.put("w", (me.i("w") - 1).coerceAtLeast(2)); "w+" -> me.put("w", (me.i("w") + 1).coerceAtMost(12))
                                    "h-" -> me.put("h", (me.i("h") - 1).coerceAtLeast(1)); "h+" -> me.put("h", (me.i("h") + 1).coerceAtMost(8))
                                    "del" -> list.removeAt(idx)
                                }
                                t.put("widgets", JSONArray(list))
                            }
                        }, onOpts = { c.editWidget(wj) })
                    }
                }
            }
        }
    }
}

@Composable
private fun EditOverlay(w: JSONObject, idx: Int, count: Int, onAct: (String) -> Unit, onOpts: () -> Unit) {
    val s = LocalSkin.current
    Box(Modifier.fillMaxSize().clip(RoundedCornerShape(s.radius)).background(Color(0xCC0A0C0F))
        .border(2.dp, s.accent, RoundedCornerShape(s.radius)), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp)) {
            T(WIDGETS[w.s("type")]?.name ?: w.s("type"), 15.sp, Color.White, FontWeight.SemiBold)
            T("${w.i("w")}×${w.i("h")}", 12.sp, Color.White.copy(.6f))
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Mini("prev", enabled = idx > 0) { onAct("left") }; Mini("next", enabled = idx < count - 1) { onAct("right") }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) { Mini(label = "↔ −") { onAct("w-") }; Mini(label = "↔ +") { onAct("w+") } }
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) { Mini(label = "↕ −") { onAct("h-") }; Mini(label = "↕ +") { onAct("h+") } }
            if (w.s("type") == "note" || w.s("type") == "shortcuts") Mini(label = "Настроить") { onOpts() }
        }
        Box(Modifier.align(Alignment.TopEnd).padding(8.dp).size(34.dp).clip(CircleShape).background(s.red).clickable { onAct("del") },
            contentAlignment = Alignment.Center) { T("✕", 16.sp, Color.White, FontWeight.Bold) }
    }
}

@Composable private fun Mini(icon: String? = null, label: String? = null, enabled: Boolean = true, onClick: () -> Unit) {
    Row(Modifier.clip(RoundedCornerShape(10.dp)).background(Color.White.copy(if (enabled) .16f else .05f))
        .clickable(enabled = enabled, onClick = onClick).padding(horizontal = 12.dp, vertical = 8.dp)) {
        if (icon != null) Ic(icon, 18.dp, Color.White.copy(if (enabled) 1f else .3f))
        if (label != null) T(label, 13.sp, Color.White)
    }
}

@Composable fun TextInput(value: String, onChange: (String) -> Unit, hint: String, modifier: Modifier = Modifier, password: Boolean = false) {
    val s = LocalSkin.current
    Box(modifier.clip(RoundedCornerShape(12.dp)).background(s.inner).border(1.dp, s.innerBorder, RoundedCornerShape(12.dp)).padding(horizontal = 14.dp, vertical = 13.dp)) {
        if (value.isEmpty()) T(hint, 16.sp, s.dim)
        BasicTextField(value, onChange, singleLine = true, textStyle = TextStyle(color = s.text, fontSize = 16.sp), cursorBrush = SolidColor(s.accent),
            visualTransformation = if (password) androidx.compose.ui.text.input.PasswordVisualTransformation() else androidx.compose.ui.text.input.VisualTransformation.None,
            modifier = Modifier.fillMaxWidth())
    }
}
