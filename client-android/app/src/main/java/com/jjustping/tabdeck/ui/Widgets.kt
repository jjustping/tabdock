package com.jjustping.tabdeck.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.heightIn
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jjustping.tabdeck.data.Deck
import com.jjustping.tabdeck.data.Fmt
import com.jjustping.tabdeck.data.STATUS
import com.jjustping.tabdeck.data.a
import com.jjustping.tabdeck.data.b
import com.jjustping.tabdeck.data.d
import com.jjustping.tabdeck.data.i
import com.jjustping.tabdeck.data.nums
import com.jjustping.tabdeck.data.o
import com.jjustping.tabdeck.data.objs
import com.jjustping.tabdeck.data.s
import com.jjustping.tabdeck.data.strs
import com.jjustping.tabdeck.data.weatherIcon
import kotlinx.coroutines.delay
import org.json.JSONObject
import java.util.Calendar

data class WidgetDef(val name: String, val icon: String, val desc: String, val w: Int, val h: Int, val single: Boolean = false)

val WIDGETS = linkedMapOf(
    "reminders" to WidgetDef("Напоминания", "check", "Свой список задач со сроками", 4, 6, true),
    "shoots" to WidgetDef("Съёмки", "aperture", "Прогресс обработки съёмок", 4, 4, true),
    "calendar" to WidgetDef("Погода, сроки, календарь", "calendar", "Всё о ближайших днях", 4, 2, true),
    "player" to WidgetDef("Музыка", "note", "Apple Music / Spotify и громкость", 4, 3, true),
    "quick" to WidgetDef("Быстрые действия", "cup", "Приложения, сон, скриншот", 4, 3, true),
    "clock" to WidgetDef("Часы", "hourglass", "Крупное время и дата", 4, 2),
    "weather" to WidgetDef("Погода", "cloudsun", "Сейчас и на 4 дня", 4, 2),
    "deadlines" to WidgetDef("Ближайшие сроки", "hourglass", "Сдача съёмок, wfolio, напоминания", 4, 2),
    "events" to WidgetDef("Календарь", "calendar", "События на сегодня и завтра", 4, 3),
    "macstat" to WidgetDef("Компьютер", "computer", "Процессор, температура, память", 4, 3, true),
    "disks" to WidgetDef("Диски", "drive", "Свободное место", 4, 3, true),
    "note" to WidgetDef("Заметка", "book", "Заметка или чек-лист из справки", 4, 4),
    "focus" to WidgetDef("Фокус-таймер", "hourglass", "25 минут работы, 5 отдыха", 4, 2, true),
    "network" to WidgetDef("Сеть", "link", "Роутер, DNS, интернет", 4, 3, true),
    "shortcuts" to WidgetDef("Команды", "frame", "Кнопки Apple Shortcuts", 4, 2),
    "wfolio" to WidgetDef("Галереи wfolio", "link", "Сроки хранения галерей", 4, 3, true),
)

/** Everything a widget needs: the latest data and the actions. */
class Ctx(val deck: Deck, val all: JSONObject?, val state: JSONObject?, val openShoot: (JSONObject) -> Unit,
          val openNote: (JSONObject?) -> Unit, val goTab: (String) -> Unit, val editWidget: (JSONObject) -> Unit)

@Composable
fun Widget(type: String, w: JSONObject, c: Ctx, modifier: Modifier) {
    val def = WIDGETS[type] ?: return
    when (type) {
        "clock" -> ClockW(modifier)
        else -> DeckCard(cardTitle(type, def, c), modifier, action = headerAction(type, c, w)) {
            when (type) {
                "reminders" -> RemindersW(c); "shoots" -> ShootsW(c); "calendar" -> CalendarW(c)
                "player" -> PlayerW(c); "quick" -> QuickW(c); "weather" -> WeatherW(c); "deadlines" -> DeadlinesW(c)
                "events" -> EventsW(c); "macstat" -> MacW(c); "disks" -> DisksW(c); "note" -> NoteW(c, w)
                "focus" -> FocusW(c); "network" -> NetW(c); "shortcuts" -> ShortcutsW(c, w); "wfolio" -> WfolioW(c)
            }
        }
    }
}

private fun cardTitle(type: String, def: WidgetDef, c: Ctx): String = when (type) {
    "macstat" -> c.state.o("sys").s("hostname").ifBlank { "Компьютер" }
    "reminders" -> "Напоминания"
    else -> def.name
}

private fun headerAction(type: String, c: Ctx, w: JSONObject): (@Composable androidx.compose.foundation.layout.RowScope.() -> Unit)? = when (type) {
    "shoots" -> { { Link("Все") { c.goTab("shoots") } } }
    "macstat", "disks" -> { { Link("Подробно") { c.goTab("mac") } } }
    "wfolio" -> { { Link("Все") { c.goTab("shoots") } } }
    "note", "shortcuts" -> { { Box(Modifier.clickable { c.editWidget(w) }.padding(4.dp)) { Ic("gear", 18.dp, LocalSkin.current.accent) } } }
    else -> null
}

@Composable fun Link(text: String, onClick: () -> Unit) {
    val s = LocalSkin.current
    Row(Modifier.clickable(onClick = onClick).padding(4.dp), verticalAlignment = Alignment.CenterVertically) {
        T(text, 14.sp, s.accent, FontWeight.Medium); Ic("chevron", 16.dp, s.accent)
    }
}

@Composable fun RemoteImage(deck: Deck, path: String?, modifier: Modifier, crop: Boolean = true, transparentBg: Boolean = false) {
    val s = LocalSkin.current
    val img by produceState<ImageBitmap?>(deck.cached(path), path) {
        if (value != null || path == null) return@produceState
        for (attempt in 0 until 3) { value = deck.image(path); if (value != null) break; delay(1500L * (attempt + 1)) }
    }
    Box(if (transparentBg) modifier else modifier.background(s.inner)) {
        img?.let { Image(it, null, Modifier.fillMaxSize(), contentScale = if (crop) ContentScale.Crop else ContentScale.Fit) }
    }
}

// ---------------- reminders ----------------
@Composable fun RemindersW(c: Ctx) {
    val s = LocalSkin.current
    var text by remember { mutableStateOf("") }
    val items = c.all.a("reminders").objs()
    val open = items.filter { !it.b("done") }.sortedWith(compareBy({ !it.b("important") }, { it.s("due").ifBlank { "9999" } }))
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.weight(1f).clip(RoundedCornerShape(12.dp)).background(s.inner).padding(horizontal = 14.dp, vertical = 13.dp)) {
            if (text.isEmpty()) T("Новое напоминание…", 16.sp, s.dim)
            BasicTextField(text, { text = it }, singleLine = true, textStyle = TextStyle(color = s.text, fontSize = 16.sp),
                cursorBrush = SolidColor(s.accent), keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { addReminder(c, text); text = "" }), modifier = Modifier.fillMaxWidth())
        }
        Spacer(Modifier.width(8.dp))
        Btn(icon = "plus", primary = true) { addReminder(c, text); text = "" }
    }
    Spacer(Modifier.height(8.dp))
    LazyColumn(Modifier.fillMaxWidth()) {
        items(open, key = { it.s("id") }) { r -> ReminderRow(c, r) }
        if (open.isEmpty()) item { Empty("Всё сделано") }
    }
}

private fun addReminder(c: Ctx, text: String) {
    if (text.isBlank()) return
    c.deck.post("/api/reminders", JSONObject().put("op", "add").put("text", text.trim()))
}

@Composable fun ReminderRow(c: Ctx, r: JSONObject) {
    val s = LocalSkin.current
    var done by remember(r.s("id")) { mutableStateOf(r.b("done")) }
    Row(Modifier.fillMaxWidth().padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(32.dp).clip(CircleShape).background(if (done) s.accent else Color.Transparent)
            .border(2.dp, if (done) s.accent else s.dim, CircleShape)
            .clickable { done = !done; c.deck.post("/api/reminders", JSONObject().put("op", "toggle").put("id", r.s("id"))) },
            contentAlignment = Alignment.Center) { if (done) Ic("check", 18.dp, s.onAccent) }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text2(r.s("text"), done)
            val due = r.s("due"); val list = r.s("list")
            if (due.isNotBlank() || list.isNotBlank()) Row(Modifier.padding(top = 3.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                if (due.isNotBlank()) { val (t, sev) = Fmt.due(due); Tag(t, when (sev) { 2 -> s.red; 1 -> s.amber; else -> null }) }
                if (list.isNotBlank()) Tag(list)
            }
        }
        if (r.b("important")) Ic("star", 18.dp, s.amber)
    }
}

@Composable private fun Text2(t: String, done: Boolean) {
    val s = LocalSkin.current
    androidx.compose.material3.Text(t, color = if (done) s.dim else s.text, fontSize = 17.sp,
        textDecoration = if (done) TextDecoration.LineThrough else null)
}

// ---------------- shoots ----------------
fun statusColor(st: String, s: Skin): Color = when (st) {
    "done" -> s.green; "delivered" -> Color(0xFFB794F4); "selecting" -> s.blue; "editing" -> s.accent; else -> s.muted
}

@Composable fun ShootsW(c: Ctx) {
    val s = LocalSkin.current
    val items = c.all.o("shoots").a("items").objs().filter { !it.b("hidden") }
    val todo = items.filter { it.s("status") !in setOf("done", "delivered") }
    val left = todo.sumOf { (it.i("target") - it.i("done")).coerceAtLeast(0) }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        for ((n, l) in listOf(todo.size to "в работе", left to "кадров ждут", (items.size - todo.size) to "готово"))
            Inner(Modifier.weight(1f)) { T("$n", 22.sp, weight = FontWeight.Bold); T(l, 13.sp, s.muted, maxLines = 2) }
    }
    Spacer(Modifier.height(6.dp))
    LazyColumn {
        items(items.take(12), key = { it.s("key") }) { sh -> ShootRow(c, sh) }
        if (items.isEmpty()) item { Empty("Съёмок нет — проверьте каталог в настройках") }
    }
}

@Composable fun ShootRow(c: Ctx, sh: JSONObject) {
    val s = LocalSkin.current
    val p = (sh.d("progress") ?: 0.0).toFloat()
    Row(Modifier.fillMaxWidth().clickable { c.openShoot(sh) }.padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        RemoteImage(c.deck, sh.s("cover").ifBlank { null }, Modifier.width(84.dp).height(56.dp).clip(RoundedCornerShape(10.dp)))
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            T(sh.s("name"), 16.sp, weight = FontWeight.SemiBold, maxLines = 1)
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 3.dp)) {
                Tag(STATUS[sh.s("status")] ?: sh.s("status"), statusColor(sh.s("status"), s)); Spacer(Modifier.width(6.dp))
                T("${sh.i("done")} из ${sh.i("target")} ${sh.s("done_label", "готово")}", 12.sp, s.muted, maxLines = 1)
            }
            Bar(p, statusColor(sh.s("status"), s))
        }
        Spacer(Modifier.width(10.dp))
        T("${(p * 100).toInt()}%", 20.sp, weight = FontWeight.Bold)
    }
}

// ---------------- calendar / weather / deadlines / events ----------------
fun deadlines(all: JSONObject?): List<Triple<String, String, String>> {
    val lim = Fmt.today(14); val out = mutableListOf<Triple<String, String, String>>()
    for (sh in all.o("shoots").a("items").objs()) { val d = sh.s("deadline"); if (d.isNotBlank() && d <= lim && !sh.b("hidden") && sh.s("status") != "delivered") out += Triple(d, "aperture", "Сдать «${sh.s("name")}»") }
    for (g in all.a("wfolio").objs()) { val d = g.s("expires"); if (d.isNotBlank() && d <= lim && g.o("check").s("status") != "expired") out += Triple(d, "hourglass", "wfolio: «${g.s("title").ifBlank { g.s("url") }}» истекает") }
    for (r in all.a("reminders").objs()) { val d = r.s("due"); if (d.isNotBlank() && d <= lim && !r.b("done")) out += Triple(d, "check", r.s("text")) }
    return out.sortedBy { it.first }
}

@Composable fun DeadlineRows(all: JSONObject?, max: Int = 6) {
    val s = LocalSkin.current
    val list = deadlines(all)
    if (list.isEmpty()) { Empty("На две недели сроков нет"); return }
    for ((d, ic, text) in list.take(max)) Row(Modifier.padding(vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
        val (t, sev) = Fmt.due(d); Tag(t, when (sev) { 2 -> s.red; 1 -> s.amber; else -> null })
        Spacer(Modifier.width(10.dp)); Ic(ic, 18.dp, s.muted); Spacer(Modifier.width(6.dp)); T(text, 15.sp, maxLines = 1)
    }
}

@Composable fun Forecast(all: JSONObject?) {
    val s = LocalSkin.current
    val days = all.o("weather").a("days").objs().take(4)
    if (days.isEmpty()) return
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(bottom = 8.dp)) {
        days.forEachIndexed { i, d ->
            Inner(Modifier.weight(1f)) {
                val cal = Calendar.getInstance().apply { set(d.s("date").take(4).toInt(), d.s("date").substring(5, 7).toInt() - 1, d.s("date").substring(8).toInt()) }
                T(if (i == 0) "сегодня" else Fmt.DS[cal.get(Calendar.DAY_OF_WEEK) - 1], 13.sp, s.muted, modifier = Modifier.align(Alignment.CenterHorizontally))
                Ic(weatherIcon(d.i("code")), 28.dp, s.text, Modifier.align(Alignment.CenterHorizontally).padding(vertical = 4.dp))
                T("${d.d("max")?.toInt()}° / ${d.d("min")?.toInt()}°", 13.sp, modifier = Modifier.align(Alignment.CenterHorizontally))
            }
        }
    }
}

@Composable fun EventRows(all: JSONObject?) {
    val s = LocalSkin.current
    val cal = all.o("calendar")
    if (!cal.b("ok")) { Empty("Нет доступа к календарю компьютера"); return }
    val evs = cal.a("events").objs()
    if (evs.isEmpty()) { Empty("Сегодня и завтра событий нет"); return }
    for (e in evs.take(8)) Row(Modifier.padding(vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
        T(if (e.b("allDay")) "весь день" else e.s("start").substring(11, 16), 15.sp, weight = FontWeight.SemiBold, modifier = Modifier.width(76.dp))
        Box(Modifier.width(4.dp).height(30.dp).clip(RoundedCornerShape(2.dp)).background(runCatching { Color(android.graphics.Color.parseColor(e.s("color"))) }.getOrDefault(s.muted)))
        Spacer(Modifier.width(10.dp))
        Column { T(e.s("title"), 15.sp, maxLines = 1); T(if (e.s("start").take(10) == Fmt.today()) "сегодня" else "завтра", 12.sp, s.muted) }
    }
}

@Composable fun CalendarW(c: Ctx) {
    Forecast(c.all)
    Column(Modifier.fillMaxWidth()) {
        if (deadlines(c.all).isNotEmpty()) { T("БЛИЖАЙШИЕ СРОКИ", 12.sp, LocalSkin.current.dim); DeadlineRows(c.all, 3) }
        EventRows(c.all)
    }
}

@Composable fun WeatherW(c: Ctx) {
    val s = LocalSkin.current
    val w = c.all.o("weather")
    if (w.d("temp") == null) { Empty(if (w?.has("configured") == true && !w.b("configured")) "Выберите город в настройках" else "Нет данных о погоде"); return }
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(bottom = 8.dp)) {
        Ic(weatherIcon(w.i("code")), 44.dp)
        Spacer(Modifier.width(12.dp))
        T("${w.d("temp")?.toInt()}°", 40.sp, weight = FontWeight.SemiBold)
        Spacer(Modifier.width(12.dp))
        Column { T(w.s("text"), 15.sp); T("ощущается ${w.d("feels")?.toInt()}° · ${w.s("place")}", 13.sp, s.muted) }
    }
    Forecast(c.all)
}

@Composable fun DeadlinesW(c: Ctx) = DeadlineRows(c.all)
@Composable fun EventsW(c: Ctx) = EventRows(c.all)

@Composable fun ClockW(modifier: Modifier) {
    val now by produceState(System.currentTimeMillis()) { while (true) { value = System.currentTimeMillis(); delay(5000) } }
    DeckCard(null, modifier) {
        val cal = Calendar.getInstance().apply { timeInMillis = now }
        Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
            T("${Fmt.pad(cal.get(Calendar.HOUR_OF_DAY))}:${Fmt.pad(cal.get(Calendar.MINUTE))}", 72.sp, weight = FontWeight.SemiBold)
            T("${Fmt.DAYS[cal.get(Calendar.DAY_OF_WEEK) - 1]}, ${cal.get(Calendar.DAY_OF_MONTH)} ${Fmt.MON[cal.get(Calendar.MONTH)]}", 16.sp, LocalSkin.current.muted)
        }
    }
}

// ---------------- player ----------------
@Composable fun PlayerW(c: Ctx) {
    val s = LocalSkin.current
    val m = c.state.o("media"); val p = m.o("player")
    Row(verticalAlignment = Alignment.CenterVertically) {
        val art = p.s("art").ifBlank { null }
        Box(Modifier.size(72.dp).clip(RoundedCornerShape(12.dp)).background(s.inner), contentAlignment = Alignment.Center) {
            if (art != null && art.startsWith("/")) RemoteImage(c.deck, art, Modifier.fillMaxSize()) else Ic("note", 34.dp, s.dim)
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            T(if (p != null) p.s("title") else "Ничего не играет", 17.sp, weight = FontWeight.SemiBold, maxLines = 1)
            T(if (p != null) listOf(p.s("artist"), p.s("album")).filter { it.isNotBlank() }.joinToString(" — ") else "Apple Music / Spotify", 14.sp, s.muted, maxLines = 1)
        }
    }
    Spacer(Modifier.height(10.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Btn(icon = "prev", modifier = Modifier.weight(1f)) { c.deck.media("previous") }
        Btn(icon = if (p.s("state") == "playing") "pause" else "play", primary = true, modifier = Modifier.weight(1.4f)) { c.deck.media("playpause") }
        Btn(icon = "next", modifier = Modifier.weight(1f)) { c.deck.media("next") }
        Btn(icon = if (m.b("muted")) "mute" else "volume", modifier = Modifier.weight(1f)) { c.deck.media("mute") }
    }
    val vol = m?.takeIf { it.has("volume") && !it.isNull("volume") }?.optInt("volume")
    if (vol != null) {
        var local by remember { mutableFloatStateOf(vol.toFloat()) }
        var dragging by remember { mutableStateOf(false) }
        LaunchedEffect(vol) { if (!dragging) local = vol.toFloat() }
        Row(verticalAlignment = Alignment.CenterVertically) {
            VolumeBar(local / 100f, Modifier.weight(1f), onDrag = { local = it * 100f; dragging = true },
                onDone = { dragging = false; c.deck.media("volume", local.toInt()) })
            T("${local.toInt()}", 14.sp, s.muted, modifier = Modifier.width(36.dp))
        }
    }
}

// ---------------- quick actions ----------------
val SYS_TILES = listOf(Triple("awake", "cup", "Не спать"), Triple("screenshot", "frame", "Скриншот"),
    Triple("display_sleep", "display", "Экран выкл."), Triple("sleep", "moon", "Сон"))

/** Volume bar drawn in the skin's colours (the stock Material slider looks foreign here). */
@Composable fun VolumeBar(value: Float, modifier: Modifier, onDrag: (Float) -> Unit, onDone: () -> Unit) {
    val s = LocalSkin.current
    var w by remember { mutableStateOf(1f) }
    fun at(x: Float) = (x / w).coerceIn(0f, 1f)
    Box(modifier.height(40.dp).onSizeChanged { w = it.width.toFloat().coerceAtLeast(1f) }
        .pointerInput(Unit) { detectTapGestures { onDrag(at(it.x)); onDone() } }
        .pointerInput(Unit) { detectHorizontalDragGestures(onDragEnd = onDone, onDragCancel = onDone) { ch, _ -> onDrag(at(ch.position.x)) } },
        contentAlignment = Alignment.CenterStart) {
        Box(Modifier.fillMaxWidth().height(10.dp).clip(RoundedCornerShape(5.dp)).background(s.inner).border(1.dp, s.innerBorder.copy(.6f), RoundedCornerShape(5.dp)))
        Box(Modifier.fillMaxWidth(value.coerceIn(0.02f, 1f)).height(10.dp).clip(RoundedCornerShape(5.dp)).background(s.accent))
        Box(Modifier.fillMaxWidth(value.coerceIn(0f, 1f)), contentAlignment = Alignment.CenterEnd) {
            Box(Modifier.size(26.dp).clip(CircleShape).background(Color.White).border(2.dp, s.accent, CircleShape)) }
    }
}

@Composable fun Tile(icon: String?, label: String, modifier: Modifier = Modifier, on: Boolean = false, armed: Boolean = false,
                     image: @Composable (() -> Unit)? = null, onClick: () -> Unit) {
    val s = LocalSkin.current
    Column(modifier.clip(RoundedCornerShape(14.dp)).background(when { armed -> s.red.copy(.25f); on -> s.amber.copy(.2f); else -> s.inner })
        .border(1.dp, if (armed) s.red else s.innerBorder.copy(.5f), RoundedCornerShape(14.dp)).clickable(onClick = onClick).padding(horizontal = 4.dp, vertical = 8.dp),
        horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        if (image != null) image() else if (icon != null) Ic(icon, 28.dp, if (on) s.amber else s.text)
        Spacer(Modifier.height(4.dp))
        T(label, 12.sp, if (armed) s.red else s.muted, maxLines = 2, align = androidx.compose.ui.text.style.TextAlign.Center)
    }
}

@Composable fun SysTiles(c: Ctx, cols: Int = 4) {
    var armed by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(armed) { if (armed != null) { delay(3000); armed = null } }
    val awake = c.state.b("awake")
    Grid(SYS_TILES, cols) { (a, ic, t) ->
        Tile(ic, if (armed == a) "Ещё раз" else t, Modifier.fillMaxWidth().heightIn(min = 80.dp), on = a == "awake" && awake, armed = armed == a) {
            if (a == "sleep" && armed != a) { armed = a; c.deck.toast("Нажмите ещё раз для подтверждения") }
            else { armed = null; c.deck.action(a) }
        }
    }
}

@Composable fun AppTiles(c: Ctx, max: Int = 8, cols: Int = 4) {
    val apps = c.all.a("apps").objs().filter { it.b("installed") }.take(max)
    Grid(apps, cols) { app ->
        val name = app.s("name")
        Tile(null, name, Modifier.fillMaxWidth().heightIn(min = 80.dp), image = {
            RemoteImage(c.deck, "/api/app_icon?name=" + java.net.URLEncoder.encode(name, "UTF-8").replace("+", "%20"),
                Modifier.size(32.dp).clip(RoundedCornerShape(8.dp)), crop = false)
        }) { c.deck.action("open_app", name) }
    }
}

@Composable fun <T> Grid(items: List<T>, cols: Int, gap: Int = 8, cell: @Composable (T) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(gap.dp)) {
        for (row in items.chunked(cols)) Row(horizontalArrangement = Arrangement.spacedBy(gap.dp)) {
            for (it in row) Box(Modifier.weight(1f)) { cell(it) }
            repeat(cols - row.size) { Spacer(Modifier.weight(1f)) }
        }
    }
}

@Composable fun QuickW(c: Ctx) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) { AppTiles(c); SysTiles(c) }
}

// ---------------- computer / disks / network ----------------
@Composable fun MacW(c: Ctx) {
    val s = LocalSkin.current
    val sys = c.state.o("sys")
    Grid(listOf("CPU" to "${sys.d("cpu")?.toInt() ?: "—"}%", "Температура" to "${sys.o("temp").d("cpu")?.toInt() ?: "—"}°",
        "Память" to "${sys.o("mem").d("pct")?.toInt() ?: "—"}%", "Работает" to Fmt.uptime(sys.d("uptime"))), 2) { (k, v) ->
        Row { T(k, 15.sp, s.muted, modifier = Modifier.weight(1f)); T(v, 15.sp, weight = FontWeight.SemiBold) }
    }
    Spacer(Modifier.height(8.dp))
    Spark(sys.a("cpu_history").nums())
}

@Composable fun DisksW(c: Ctx) {
    val s = LocalSkin.current
    for (d in c.state.o("sys").a("disks").objs().filter { it.s("bus") != "Disk Image" }) Column(Modifier.padding(vertical = 5.dp)) {
        val ro = d.b("readonly")
        Row { T(d.s("name"), 15.sp, weight = FontWeight.SemiBold, modifier = Modifier.weight(1f), maxLines = 1)
            T(if (ro) "только чтение" else "${Fmt.bytes(d.d("free"))} свободно", 14.sp, s.muted) }
        Spacer(Modifier.height(5.dp))
        Bar(((d.d("pct") ?: 0.0) / 100).toFloat(), when { ro -> s.dim; (d.d("pct") ?: 0.0) > 90 -> s.red; else -> s.green })
    }
}

@Composable fun NetW(c: Ctx) {
    val s = LocalSkin.current
    val n = c.state.o("net")
    if (n == null || n.d("at") == null || n.d("at") == 0.0) { Empty("Проверяю сеть…"); return }
    @Composable fun row(ok: Boolean, name: String, v: String) = Row(Modifier.padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(10.dp).clip(CircleShape).background(if (ok) s.green else s.red)); Spacer(Modifier.width(10.dp))
        T(name, 15.sp, weight = FontWeight.SemiBold, modifier = Modifier.width(90.dp)); T(v, 14.sp, s.muted, maxLines = 1)
    }
    val gw = n.d("gw_ms")
    row(gw != null, "Роутер", n.s("gateway").ifBlank { "не найден" } + (gw?.let { " · ${it.toInt()} мс" } ?: " · не отвечает"))
    row(n.b("dns_ok"), "DNS", if (n.b("dns_ok")) "${n.i("dns_ms")} мс" else n.s("dns_err", "ошибка"))
    row(n.b("inet_ok"), "Интернет", if (n.b("inet_ok")) "${n.i("inet_ms")} мс" else n.s("inet_err", "нет"))
    val verdict = when { gw == null -> "Нет связи с роутером"; !n.b("dns_ok") -> "DNS не отвечает — сайты не открываются"; !n.b("inet_ok") -> "Нет выхода в интернет"; else -> "Сеть в порядке" }
    val ok = verdict == "Сеть в порядке"
    Box(Modifier.padding(top = 8.dp).fillMaxWidth().clip(RoundedCornerShape(12.dp)).background((if (ok) s.green else s.red).copy(.14f)).padding(10.dp)) {
        T(verdict, 14.sp, if (ok) s.green else s.red)
    }
}

// ---------------- note / focus / shortcuts / wfolio ----------------
@Composable fun NoteW(c: Ctx, w: JSONObject) {
    val notes = c.all.a("notes").objs()
    val id = w.o("opts").s("noteId")
    val n = notes.firstOrNull { it.s("id") == id } ?: notes.firstOrNull { it.b("pinned") } ?: notes.firstOrNull()
    if (n == null) { Empty("Заметок нет — добавьте в «Справке»"); return }
    T(n.s("title"), 17.sp, weight = FontWeight.SemiBold, modifier = Modifier.clickable { c.openNote(n) }.padding(bottom = 6.dp))
    Markdown(n, c)
}

/** Light markdown: "- " lists, "- [ ]" checklists (tap to toggle), **bold** is shown as plain text. */
@Composable fun Markdown(n: JSONObject, c: Ctx) {
    val s = LocalSkin.current
    val lines = n.s("body").split("\n")
    Column {
        lines.forEachIndexed { idx, raw ->
            val l = raw.replace("**", "").replace("`", "")
            val cb = Regex("^\\s*[-•]\\s+\\[( |x|х)\\]\\s+(.*)$", RegexOption.IGNORE_CASE).find(l)
            when {
                cb != null -> {
                    val on = cb.groupValues[1].isNotBlank()
                    Row(Modifier.fillMaxWidth().clickable {
                        val ls = n.s("body").split("\n").toMutableList()
                        ls[idx] = ls[idx].replaceFirst(Regex("\\[( |x|х)\\]", RegexOption.IGNORE_CASE), if (on) "[ ]" else "[x]")
                        c.deck.post("/api/notes", JSONObject().put("op", "edit").put("id", n.s("id")).put("body", ls.joinToString("\n")))
                    }.padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(24.dp).clip(RoundedCornerShape(7.dp)).background(if (on) s.accent else Color.Transparent)
                            .border(2.dp, if (on) s.accent else s.dim, RoundedCornerShape(7.dp)), contentAlignment = Alignment.Center) {
                            if (on) Ic("check", 16.dp, s.onAccent)
                        }
                        Spacer(Modifier.width(10.dp))
                        Text2(cb.groupValues[2], on)
                    }
                }
                Regex("^\\s*[-•]\\s+").containsMatchIn(l) -> Row(Modifier.padding(vertical = 2.dp)) { T("•  ", 15.sp, s.muted); T(l.replaceFirst(Regex("^\\s*[-•]\\s+"), ""), 15.sp, s.text.copy(.9f)) }
                l.isNotBlank() -> T(l, 15.sp, s.text.copy(.9f), modifier = Modifier.padding(vertical = 2.dp))
            }
        }
    }
}

private const val WORK = 25 * 60L
private const val REST = 5 * 60L

@Composable fun FocusW(c: Ctx) {
    val st = c.deck.store
    var mode by remember { mutableStateOf(st.string("focus_mode") ?: "work") }
    var end by remember { mutableLongStateOf(st.string("focus_end")?.toLong() ?: 0L) }
    var left by remember { mutableLongStateOf(st.string("focus_left")?.toLong() ?: WORK) }
    val now by produceState(System.currentTimeMillis(), end) { while (true) { value = System.currentTimeMillis(); delay(1000) } }
    val running = end > now
    val remain = if (running) (end - now) / 1000 else left
    LaunchedEffect(running, end) {
        if (end != 0L && !running) {
            mode = if (mode == "work") "rest" else "work"; left = if (mode == "work") WORK else REST; end = 0
            c.deck.toast(if (mode == "rest") "Время перерыва — 5 минут" else "Перерыв окончен")
        }
    }
    fun save() { st.put("focus_mode", mode); st.put("focus_end", end.toString()); st.put("focus_left", left.toString()) }
    Row(Modifier.fillMaxSize(), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            T(if (mode == "work") "Фокус" else "Перерыв", 14.sp, LocalSkin.current.muted)
            T("${remain / 60}:${Fmt.pad((remain % 60).toInt())}", 44.sp, weight = FontWeight.SemiBold)
        }
        Btn(icon = if (running) "pause" else "play", primary = true) {
            if (running) { left = remain; end = 0 } else end = System.currentTimeMillis() + remain * 1000; save()
        }
        Spacer(Modifier.width(8.dp))
        Btn(icon = "reset") { end = 0; left = if (mode == "work") WORK else REST; save() }
    }
}

@Composable fun ShortcutsW(c: Ctx, w: JSONObject) {
    val names = w.o("opts").a("names").strs()
    if (names.isEmpty()) { Empty("Выберите команды Apple Shortcuts — значок ⚙ выше"); return }
    Grid(names, 3) { n -> Tile("frame", n, Modifier.fillMaxWidth().heightIn(min = 80.dp)) { c.deck.action("shortcut", n) } }
}

@Composable fun WfolioW(c: Ctx) {
    val s = LocalSkin.current
    val list = c.all.a("wfolio").objs()
    if (list.isEmpty()) { Empty("Галерей пока нет"); return }
    for (g in list.take(6)) Row(Modifier.padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        val st = g.o("check").s("status")
        Box(Modifier.size(10.dp).clip(CircleShape).background(when (st) { "active" -> s.green; "expired" -> s.red; "error" -> s.amber; else -> s.dim }))
        Spacer(Modifier.width(10.dp))
        T(g.s("title").ifBlank { g.s("url") }, 15.sp, weight = FontWeight.SemiBold, modifier = Modifier.weight(1f), maxLines = 1)
        val dl = g.d("days_left")
        Tag(when { st == "expired" -> "истекла"; dl == null -> "бессрочно"; else -> "ещё ${dl.toInt()} дн." },
            when { st == "expired" || (dl != null && dl <= 3) -> s.red; dl != null && dl <= 14 -> s.amber; else -> null })
    }
}
