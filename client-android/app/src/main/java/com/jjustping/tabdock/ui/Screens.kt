package com.jjustping.tabdock.ui

import android.annotation.SuppressLint
import android.webkit.CookieManager
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.staggeredgrid.LazyVerticalStaggeredGrid
import androidx.compose.foundation.lazy.staggeredgrid.StaggeredGridCells
import androidx.compose.foundation.lazy.staggeredgrid.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.jjustping.tabdock.data.Deck
import com.jjustping.tabdock.data.FoundServer
import com.jjustping.tabdock.data.Fmt
import com.jjustping.tabdock.data.STATUS
import com.jjustping.tabdock.data.a
import com.jjustping.tabdock.data.b
import com.jjustping.tabdock.data.d
import com.jjustping.tabdock.data.i
import com.jjustping.tabdock.data.o
import com.jjustping.tabdock.data.objs
import com.jjustping.tabdock.data.s
import com.jjustping.tabdock.data.strs
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

// ---------------- dialogs ----------------
class Dialogs(val deck: Deck) {
    var current by mutableStateOf<(@Composable () -> Unit)?>(null)
    var onCull: (JSONObject) -> Unit = {}
    fun close() { current = null }

    fun catalog(sp: JSONObject, add: (String, WidgetDef) -> Unit) { current = {
        Sheet("Добавить виджет") {
            val have = sp.a("widgets").objs().map { it.s("type") }.toSet()
            Grid(WIDGETS.entries.toList(), 3) { (k, d) ->
                val taken = d.single && k in have
                Inner(Modifier.fillMaxWidth().height(96.dp), onClick = if (taken) null else ({ add(k, d); close() })) {
                    Ic(d.icon, 24.dp, if (taken) LocalSkin.current.dim else LocalSkin.current.accent)
                    T(d.name, 15.sp, weight = FontWeight.SemiBold, maxLines = 1)
                    T(if (taken) "уже есть" else d.desc, 12.sp, LocalSkin.current.muted, maxLines = 2)
                }
            }
            Actions { Btn("Закрыть") { close() } }
        }
    } }

    fun space(sp: JSONObject, all: List<JSONObject>, templates: Map<String, String>, onSave: (String, String) -> Unit,
              onAdd: (String?) -> Unit, onDelete: () -> Unit, onMove: (Int) -> Unit) { current = {
        var name by remember { mutableStateOf(sp.s("name")) }
        var icon by remember { mutableStateOf(sp.s("icon", "home")) }
        Sheet("Пространство") {
            TextInput(name, { name = it }, "Название", Modifier.fillMaxWidth())
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                for (n in listOf("home", "aperture", "check", "note", "computer", "book", "calendar", "cup", "star", "link", "drive", "moon"))
                    Box(Modifier.size(44.dp).clip(RoundedCornerShape(12.dp)).background(if (n == icon) LocalSkin.current.accent.copy(.2f) else LocalSkin.current.inner)
                        .clickable { icon = n }, contentAlignment = Alignment.Center) { Ic(n, 22.dp) }
            }
            Spacer(Modifier.height(12.dp))
            T("Добавить пространство из шаблона", 13.sp, LocalSkin.current.muted)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 6.dp)) {
                for ((k, n) in templates) Btn(n) { onAdd(k); close() }
                Btn("Пустое", "plus") { onAdd(null); close() }
            }
            Actions {
                if (all.size > 1) Btn("Удалить", danger = true) { onDelete(); close() }
                Btn(icon = "prev") { onMove(-1) }; Btn(icon = "next") { onMove(1) }
                Btn("Сохранить", primary = true) { onSave(name.ifBlank { sp.s("name") }, icon); close() }
            }
        }
    } }

    fun shoot(sh: JSONObject) { current = {
        val s = LocalSkin.current
        var st by remember { mutableStateOf(if (sh.b("status_manual")) sh.s("status") else "") }
        var target by remember { mutableStateOf(if (sh.b("target_manual")) sh.i("target").toString() else "") }
        var deadline by remember { mutableStateOf(sh.s("deadline")) }
        var note by remember { mutableStateOf(sh.s("note")) }
        Sheet(sh.s("name")) {
            T("Статус ${if (sh.b("status_manual")) "(вручную)" else "(авто: ${STATUS[sh.s("status_auto")]})"}", 13.sp, s.muted)
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.horizontalScroll(rememberScrollState()).padding(vertical = 6.dp)) {
                (listOf("" to "Авто") + STATUS.toList()).forEach { (k, n) -> Seg(n, st == k) { st = k } }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                TextInput(target, { target = it.filter(Char::isDigit) }, "Цель, кадров (авто: ${sh.i("picked").takeIf { it > 0 } ?: sh.i("total")})", Modifier.weight(1f))
                TextInput(deadline, { deadline = it }, "Срок: ГГГГ-ММ-ДД", Modifier.weight(1f))
            }
            Spacer(Modifier.height(10.dp))
            TextInput(note, { note = it }, "Заметка: что осталось, пожелания клиента…", Modifier.fillMaxWidth())
            Spacer(Modifier.height(8.dp))
            T("${sh.i("total")} кадров · ${sh.i("picked")} отобрано · ${sh.i("done")} ${sh.s("done_label")} · ${sh.s("catalog_name")}", 13.sp, s.muted)
            Actions {
                if (sh.s("source") != "folder") Btn("Отбор и метки", "star", primary = false) { close(); onCull(sh) }
                Btn(if (sh.s("source") == "folder") "Открыть папку" else "Открыть в Capture One") {
                    if (sh.s("source") == "folder") deck.post("/api/action", JSONObject().put("action", "open_folder").put("key", sh.s("key")), false)
                    else deck.post("/api/action", JSONObject().put("action", "open_shoot").put("catalog", sh.s("catalog")), false)
                }
                Btn("Отмена") { close() }
                Btn("Сохранить", primary = true) {
                    deck.post("/api/shoots", JSONObject().put("op", "set").put("key", sh.s("key")).put("status", st.ifBlank { JSONObject.NULL })
                        .put("target", target.toIntOrNull() ?: JSONObject.NULL).put("deadline", deadline.ifBlank { JSONObject.NULL }).put("note", note))
                    close()
                }
            }
        }
    } }

    fun note(n: JSONObject?) { current = {
        var title by remember { mutableStateOf(n.s("title")) }
        var body by remember { mutableStateOf(n.s("body")) }
        var tag by remember { mutableStateOf(n.s("tag")) }
        val s = LocalSkin.current
        Sheet(if (n == null) "Новая заметка" else "Заметка") {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                TextInput(title, { title = it }, "Заголовок", Modifier.weight(2f)); TextInput(tag, { tag = it }, "Раздел", Modifier.weight(1f))
            }
            Spacer(Modifier.height(10.dp))
            T("Текст: «- » список, «- [ ] » чек-лист", 13.sp, s.muted)
            Box(Modifier.fillMaxWidth().height(220.dp).clip(RoundedCornerShape(12.dp)).background(s.inner).padding(12.dp)) {
                BasicTextField(body, { body = it }, textStyle = TextStyle(color = s.text, fontSize = 16.sp), cursorBrush = SolidColor(s.accent), modifier = Modifier.fillMaxSize())
            }
            Actions {
                if (n != null) Btn("Удалить", danger = true) { deck.post("/api/notes", JSONObject().put("op", "delete").put("id", n.s("id"))); close() }
                Btn("Отмена") { close() }
                Btn("Сохранить", primary = true) {
                    val b = JSONObject().put("title", title.ifBlank { "Без названия" }).put("body", body).put("tag", tag)
                    deck.post("/api/notes", if (n == null) b.put("op", "add") else b.put("op", "edit").put("id", n.s("id"))); close()
                }
            }
        }
    } }

    fun widgetOpts(w: JSONObject, all: JSONObject?, save: (JSONObject) -> Unit) { current = {
        if (w.s("type") == "buttons") ButtonsEditor(Ctx(deck, all, null, {}, {}, {}, {})) { close() }
        else if (w.s("type") in setOf("hosts", "backups", "git", "ci")) AdminEditor(Ctx(deck, all, null, {}, {}, {}, {}), w.s("type")) { close() }
        else if (w.s("type") == "note") Sheet("Какую заметку показывать") {
            Grid(all.a("notes").objs(), 3) { n -> Inner(Modifier.fillMaxWidth(), onClick = { save(JSONObject().put("noteId", n.s("id"))); close() }) { T(n.s("title"), 15.sp, maxLines = 2) } }
            Actions { Btn("Закрыть") { close() } }
        } else {
            val list by androidx.compose.runtime.produceState(emptyList<String>()) { value = runCatching { deck.api!!.arr("/api/shortcuts").strs() }.getOrDefault(emptyList()) }
            var chosen by remember { mutableStateOf(w.o("opts").a("names").strs().toSet()) }
            Sheet("Кнопки команд (Apple Shortcuts)") {
                if (list.isEmpty()) Empty("На компьютере нет команд — создайте их в приложении «Команды»")
                Grid(list, 3) { n -> Seg(n, n in chosen) { chosen = if (n in chosen) chosen - n else if (chosen.size < 8) chosen + n else chosen } }
                Actions { Btn("Сохранить", primary = true) { save(JSONObject().put("names", JSONArray(chosen.toList()))); close() } }
            }
        }
    } }

    fun custom(content: @Composable () -> Unit) { current = content }

    @Composable fun Host() {
        val d = current ?: return
        Box(Modifier.fillMaxSize().background(Color.Black.copy(.55f)).clickable(interactionSource = noRipple(), indication = null) { close() },
            contentAlignment = Alignment.Center) {
            Box(Modifier.widthIn(max = 760.dp).fillMaxWidth(.9f).clickable(interactionSource = noRipple(), indication = null) {}) { d() }
        }
    }
}

@Composable fun Sheet(title: String, content: @Composable () -> Unit) {
    DeckCard(title, Modifier.fillMaxWidth(), pad = 20.dp) { Column(Modifier.verticalScroll(rememberScrollState())) { content() } }
}
@OptIn(ExperimentalLayoutApi::class)
@Composable fun Actions(content: @Composable () -> Unit) {
    // wraps onto a second line on narrow screens instead of pushing buttons off the edge
    FlowRow(Modifier.fillMaxWidth().padding(top = 16.dp), horizontalArrangement = Arrangement.spacedBy(10.dp, Alignment.End),
        verticalArrangement = Arrangement.spacedBy(10.dp)) { content() }
}
@Composable fun Seg(text: String, on: Boolean, onClick: () -> Unit) {
    val s = LocalSkin.current
    Box(Modifier.clip(RoundedCornerShape(12.dp)).background(s.inner).border(1.dp, if (on) s.accent else s.innerBorder, RoundedCornerShape(12.dp))
        .clickable(onClick = onClick).padding(horizontal = 14.dp, vertical = 10.dp)) { T(text, 14.sp, if (on) s.accent else s.text, maxLines = 1) }
}

// ---------------- shoots ----------------
@Composable fun ShootsScreen(c: Ctx) {
    val s = LocalSkin.current
    val items = c.all.o("shoots").a("items").objs()
    Column(Modifier.fillMaxSize()) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(bottom = 12.dp)) {
            T("Съёмки", 24.sp, weight = FontWeight.Bold, modifier = Modifier.weight(1f))
            T("${c.all.o("shoots").a("catalogs").strs().size} каталог(а) · ${items.size} съёмок", 14.sp, s.muted)
        }
        for (e in c.all.o("shoots").a("errors").objs()) T("⚠ ${e.s("error")}", 14.sp, s.red, modifier = Modifier.padding(bottom = 8.dp))
        LazyVerticalGrid(GridCells.Adaptive(300.dp), horizontalArrangement = Arrangement.spacedBy(14.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            items(items, key = { it.s("key") }) { sh ->
                val p = (sh.d("progress") ?: 0.0).toFloat()
                DeckCard(null, Modifier.fillMaxWidth().clickable { c.openShoot(sh) }, pad = 0.dp) {
                    Box { RemoteImage(c.deck, sh.s("cover").ifBlank { null }, Modifier.fillMaxWidth().height(160.dp))
                        Box(Modifier.padding(10.dp).clip(RoundedCornerShape(999.dp)).background(Color.Black.copy(.6f)).padding(horizontal = 10.dp, vertical = 3.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) { Box(Modifier.size(8.dp).clip(CircleShape).background(statusColor(sh.s("status"), s))); Spacer(Modifier.width(6.dp))
                                T(STATUS[sh.s("status")] ?: "", 12.sp, Color.White, FontWeight.SemiBold) } } }
                    Column(Modifier.padding(14.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) { T(sh.s("name"), 18.sp, weight = FontWeight.SemiBold, maxLines = 1); T(listOf(sh.s("catalog_name"), sh.s("camera")).filter { it.isNotBlank() }.joinToString(" · "), 13.sp, s.muted, maxLines = 1) }
                            T("${(p * 100).toInt()}%", 24.sp, weight = FontWeight.Bold)
                        }
                        Spacer(Modifier.height(8.dp)); Bar(p, statusColor(sh.s("status"), s)); Spacer(Modifier.height(8.dp))
                        T("${sh.i("total")} кадров · ${sh.i("picked")} отобрано · ${sh.i("done")} ${sh.s("done_label")}" + (sh.s("deadline").takeIf { it.isNotBlank() }?.let { " · срок ${it.substring(8)}.${it.substring(5, 7)}" } ?: ""), 13.sp, s.muted)
                    }
                }
            }
        }
    }
}

// ---------------- notes ----------------
@Composable fun NotesScreen(c: Ctx) {
    val notes = c.all.a("notes").objs().sortedWith(compareBy({ !it.b("pinned") }, { -(it.d("updated") ?: 0.0) }))
    Column(Modifier.fillMaxSize()) {
        var showSets by remember { mutableStateOf(false) }
        var sets by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
        LaunchedEffect(showSets, notes.size) { if (showSets) sets = runCatching { c.deck.api!!.arr("/api/notesets", 6000).objs() }.getOrDefault(emptyList()) }
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(bottom = 12.dp)) {
            T("Справка", 24.sp, weight = FontWeight.Bold, modifier = Modifier.weight(1f))
            Btn(if (LocalCompact.current) null else "Шпаргалки", "book") { showSets = !showSets }; Spacer(Modifier.width(10.dp))
            Btn(if (LocalCompact.current) null else "Заметка", "plus", primary = true) { c.openNote(null) }
        }
        if (showSets) DeckCard("Готовые шпаргалки", Modifier.fillMaxWidth().padding(bottom = 14.dp)) {
            T("Горячие клавиши и команды для разных программ и задач. Добавляются в «Справку», их можно менять и удалять.", 13.sp, LocalSkin.current.muted)
            if (sets.isEmpty()) T("Загружаю…", 14.sp, LocalSkin.current.dim, modifier = Modifier.padding(top = 8.dp))
            for (st in sets) Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    T(st.s("name"), 16.sp, weight = FontWeight.SemiBold, maxLines = 1)
                    T(st.a("titles").strs().joinToString(" · "), 12.sp, LocalSkin.current.muted, maxLines = 1)
                }
                if (st.b("added")) T("✓ добавлено", 13.sp, LocalSkin.current.green)
                else Btn("Добавить") { c.deck.post("/api/notes", JSONObject().put("op", "add_sets").put("sets", org.json.JSONArray().put(st.s("id")))) }
            }
        }
        LazyVerticalStaggeredGrid(StaggeredGridCells.Adaptive(320.dp), horizontalArrangement = Arrangement.spacedBy(14.dp), verticalItemSpacing = 14.dp) {
            items(notes, key = { it.s("id") }) { n ->
                DeckCard(n.s("title"), Modifier.fillMaxWidth(), action = { Box(Modifier.clickable { c.openNote(n) }.padding(4.dp)) { Ic("pencil", 18.dp, LocalSkin.current.muted) } }) {
                    if (n.s("tag").isNotBlank()) Box(Modifier.padding(bottom = 6.dp)) { Tag(n.s("tag")) }
                    Markdown(n, c)
                    for (l in n.a("links").objs()) T("↗ ${l.s("title").ifBlank { l.s("url") }}", 15.sp, LocalSkin.current.accent, modifier = Modifier.padding(top = 6.dp))
                }
            }
        }
    }
}

// ---------------- computer ----------------
@Composable fun ComputerScreen(c: Ctx) {
    val s = LocalSkin.current
    val sys = c.state.o("sys"); val t = sys.o("temp"); val m = sys.o("mem")
    var armed by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(armed) { if (armed != null) { delay(3000); armed = null } }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        DeckCard("${sys.s("hostname")} · ${sys.s("chip")} · ${sys.i("cores")} ядер") {
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                Column(Modifier.weight(1f)) { T("Процессор", 13.sp, s.muted); T("${sys.d("cpu")?.toInt() ?: "—"}%", 34.sp, weight = FontWeight.Bold); Spark(sys.a("cpu_history").let { a -> (0 until (a?.length() ?: 0)).map { a!!.optDouble(it) } }) }
                Column(Modifier.weight(1f)) { T("Температура", 13.sp, s.muted); T("${t.d("cpu")?.toInt() ?: "—"}°", 34.sp, weight = FontWeight.Bold); T("SSD ${t.d("ssd")?.toInt() ?: "—"}° · ${if (sys.s("thermal") == "throttled") "троттлинг!" else "охлаждение в норме"}", 13.sp, s.muted) }
                Column(Modifier.weight(1f)) { T("Память", 13.sp, s.muted); T("${m.d("pct")?.toInt() ?: "—"}%", 34.sp, weight = FontWeight.Bold); T("${Fmt.bytes(m.d("used"))} из ${Fmt.bytes(m.d("total"))}", 13.sp, s.muted); Spacer(Modifier.height(6.dp)); Bar(((m.d("pct") ?: 0.0) / 100).toFloat()) }
                Column(Modifier.weight(1f)) { T("Работает", 13.sp, s.muted); T(Fmt.uptime(sys.d("uptime")), 22.sp, weight = FontWeight.Bold); T("IP ${sys.s("ip")}", 13.sp, s.muted) }
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            DeckCard("Диски", Modifier.weight(1f)) {
                for (d in sys.a("disks").objs()) Row(Modifier.padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Ic(if (d.s("bus") == "Disk Image") "disc" else if (d.b("external")) "drive" else "computer", 22.dp, s.muted); Spacer(Modifier.width(10.dp))
                    Column(Modifier.weight(1f)) {
                        T(d.s("name"), 16.sp, weight = FontWeight.SemiBold)
                        T(if (d.b("external")) listOf(d.s("model"), d.s("bus"), d.s("fs")).filter { it.isNotBlank() }.joinToString(" · ") else "системный", 12.sp, s.muted, maxLines = 1)
                        Spacer(Modifier.height(4.dp)); Bar(((d.d("pct") ?: 0.0) / 100).toFloat(), if ((d.d("pct") ?: 0.0) > 90) s.red else s.green)
                    }
                    Spacer(Modifier.width(10.dp)); T("${Fmt.bytes(d.d("free"))}\nсвободно", 13.sp, s.muted)
                    if (d.b("external")) { Spacer(Modifier.width(8.dp)); Btn(if (armed == d.s("mount")) "Ещё раз" else null, if (armed == d.s("mount")) null else "eject", danger = armed == d.s("mount")) {
                        if (armed == d.s("mount")) { armed = null; c.deck.action("eject", d.s("mount")) } else armed = d.s("mount") } }
                }
            }
            DeckCard("Система", Modifier.weight(1f)) {
                SysTiles(c); Spacer(Modifier.height(12.dp))
                T("Приложения", 13.sp, s.muted); Spacer(Modifier.height(6.dp)); AppTiles(c, 16)
            }
        }
    }
}

// ---------------- settings & connection ----------------
@Composable fun ConnectScreen(deck: Deck, onScan: () -> Unit = {}, onDone: () -> Unit) {
    val s = LocalSkin.current
    val servers by deck.discovery.servers.collectAsState()
    val progress by deck.discovery.scanning.collectAsState()
    val scope = rememberCoroutineScope()
    var manual by remember { mutableStateOf("") }
    var pwFor by remember { mutableStateOf<FoundServer?>(null) }
    var pw by remember { mutableStateOf("") }
    var msg by remember { mutableStateOf("") }
    LaunchedEffect(Unit) { deck.discovery.scan() }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 40.dp, vertical = 30.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Ic("computer", 48.dp, s.accent); Spacer(Modifier.width(14.dp))
            Column { T("TabDock", 30.sp, weight = FontWeight.Bold); T("Подключитесь к компьютеру с TabDock", 16.sp, s.muted) }
        }
        DeckCard("Быстрее всего — QR-код") {
            T("Откройте TabDock на компьютере: панель в браузере, меню значка TabDock («Показать QR-код») или конец установки — и отсканируйте код отсюда. Камера телефона для этого не подойдёт.",
                14.sp, s.muted)
            Btn("Сканировать QR-код", "qr", primary = true, modifier = Modifier.padding(top = 12.dp)) { onScan() }
        }
        DeckCard("Компьютеры в этой сети", action = { if (progress > 0f) T("${(progress * 100).toInt()}%", 13.sp, s.muted) else Link("Искать") { scope.launch { deck.discovery.scan() } } }) {
            if (servers.isEmpty()) Empty(if (progress > 0f) "Ищу…" else "Никого не нашли — проверьте, что компьютер включён и в той же сети")
            for (sv in servers) Row(Modifier.fillMaxWidth().padding(vertical = 6.dp).clip(RoundedCornerShape(12.dp)).background(s.inner).padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(12.dp).clip(CircleShape).background(when (sv.state) { "pinned" -> s.green; "mismatch" -> s.red; else -> s.dim }))
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    T(sv.name, 17.sp, weight = FontWeight.SemiBold)
                    T("${sv.base.substringAfter("://")} · ${sv.model} · " + when (sv.state) { "pinned" -> "ваш компьютер"; "mismatch" -> "⚠ не подтверждён"; else -> "новый" }, 13.sp, if (sv.state == "mismatch") s.red else s.muted)
                }
                Btn("Подключить", primary = sv.state == "pinned") {
                    if (sv.state == "pinned" && deck.store.entry(sv.id) != null) deck.connectKnown(sv.id, onDone) else { pwFor = sv; msg = "" }
                }
            }
        }
        pwFor?.let { sv ->
            DeckCard("Вход: ${sv.name}") {
                if (sv.state == "mismatch") T("Этот сервер выдаёт себя за ваш компьютер, но не подтвердил ключ. Подключайтесь, только если уверены (например, на компьютере сменили ключ).", 14.sp, s.red)
                if (!sv.hasPassword) T("На этом компьютере пароль не задан. Откройте TabDock на компьютере → «Подключение» → «Пароль для входа», или отсканируйте QR-код с экрана компьютера камерой и откройте ссылку в TabDock.", 14.sp, s.muted)
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 10.dp)) {
                    TextInput(pw, { pw = it }, "Пароль TabDock", Modifier.weight(1f), password = true); Spacer(Modifier.width(10.dp))
                    Btn("Войти", primary = true) { deck.login(sv, pw) { r -> if (r == "ok") onDone() else msg = r } }
                }
                if (msg.isNotBlank()) T(msg, 14.sp, s.red, modifier = Modifier.padding(top = 8.dp))
            }
        }
        DeckCard("Вручную") {
            Row(verticalAlignment = Alignment.CenterVertically) {
                TextInput(manual, { manual = it }, "IP компьютера, например 192.168.1.20", Modifier.weight(1f)); Spacer(Modifier.width(10.dp))
                Btn("Найти", primary = true) {
                    scope.launch {
                        var a = manual.trim().substringAfter("://").substringBefore('/'); if (a.isBlank()) return@launch
                        if (!a.contains(':')) a += ":8787"
                        val f = deck.discovery.verify("https://$a")
                        if (f == null) msg = "По адресу $a TabDock не отвечает" else { pwFor = f; msg = "" }
                    }
                }
            }
            T("Приложение само подключается только к компьютеру, который уже подтвердил свой ключ. В чужой сети ничего не откроется само.", 13.sp, s.dim, modifier = Modifier.padding(top = 10.dp))
        }
    }
}

/** Screens not yet ported to native open the server's web UI inside the app (same key, as a cookie). */
@SuppressLint("SetJavaScriptEnabled")
@Composable fun WebScreen(deck: Deck, path: String, onClose: () -> Unit) {
    val s = LocalSkin.current
    Column(Modifier.fillMaxSize().background(s.bg)) {
        Row(Modifier.fillMaxWidth().padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
            Btn("Назад", "prev") { deck.refresh(); onClose() }
            Spacer(Modifier.width(12.dp)); T("Веб-экран сервера", 15.sp, s.muted)
        }
        AndroidView({ ctx ->
            val api = deck.api
            if (api != null) { CookieManager.getInstance().setCookie(api.base, "dock_k=${api.key}; Path=/; Secure"); CookieManager.getInstance().flush() }
            WebView(ctx).apply { settings.javaScriptEnabled = true; settings.domStorageEnabled = true; settings.textZoom = 100
                webViewClient = object : WebViewClient() {
                    // the same rule as the app's own connections: only the certificate remembered at pairing
                    override fun onReceivedSslError(view: WebView, handler: android.webkit.SslErrorHandler, error: android.net.http.SslError) {
                        val der = android.net.http.SslCertificate.saveState(error.certificate).getByteArray("x509-certificate")
                        if (der != null && api?.pin != null && com.jjustping.tabdock.data.Crypto.same(api.pin, com.jjustping.tabdock.data.Crypto.sha256(der))) handler.proceed() else handler.cancel()
                    }
                }
                loadUrl((api?.base ?: "") + path) }
        }, Modifier.fillMaxSize())
    }
}
