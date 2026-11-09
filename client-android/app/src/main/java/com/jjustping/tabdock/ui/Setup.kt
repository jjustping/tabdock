package com.jjustping.tabdock.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jjustping.tabdock.data.Deck
import com.jjustping.tabdock.data.a
import com.jjustping.tabdock.data.b
import com.jjustping.tabdock.data.i
import com.jjustping.tabdock.data.o
import com.jjustping.tabdock.data.objs
import com.jjustping.tabdock.data.s
import com.jjustping.tabdock.data.strs
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import java.net.URLEncoder

private fun cfgPost(c: Ctx, body: JSONObject) = c.deck.post("/api/config", body)

// ===================== native settings =====================
@Composable
fun SettingsScreen(c: Ctx, openWeb: (String) -> Unit, onConnect: () -> Unit, onWizard: () -> Unit, onScan: () -> Unit = {}) {
    val s = LocalSkin.current
    val cfg = c.all.o("config")
    val skin by c.deck.skin.collectAsState()
    val cur = skinById(skin ?: cfg.s("skin").ifBlank { null })
    val scope = rememberCoroutineScope()
    val ctx = androidx.compose.ui.platform.LocalContext.current
    var editing by remember { mutableStateOf<String?>(null) }   // "new" or a custom skin id
    editing?.let { e -> ThemeEditor(c.deck, c.all, if (e == "new") null else e) { editing = null }; return }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        DeckCard("Пространства и сценарии") {
            Column {
                T("Пространства: " + spacesOf(c.all).joinToString(", ") { it.s("name") } + ". Раскладку меняет карандаш на главной.", 14.sp, s.muted)
                Btn("Первая настройка", "star", modifier = Modifier.padding(top = 10.dp)) { onWizard() }
            }
        }
        DeckCard("Оформление") {
            Grid(SKINS + Themes.custom, if (LocalCompact.current) 2 else 4) { k ->
                Column(Modifier.clip(RoundedCornerShape(14.dp)).border(2.dp, if (k.id == cur.id) s.accent else Color.Transparent, RoundedCornerShape(14.dp))
                    .background(s.inner).clickable { c.deck.setSkin(k.id) }) {
                    Box(Modifier.fillMaxWidth().height(64.dp).background(k.bg)) {
                        if (k.bgImage != null) RemoteImage(c.deck, k.bgImage, Modifier.fillMaxSize())
                        Box(Modifier.padding(10.dp).size(70.dp, 40.dp).clip(RoundedCornerShape(8.dp)).background(k.card))
                        Box(Modifier.align(Alignment.BottomEnd).padding(10.dp).size(40.dp, 14.dp).clip(RoundedCornerShape(7.dp)).background(k.primary))
                    }
                    Column(Modifier.padding(10.dp)) { T(k.name, 15.sp, weight = FontWeight.SemiBold); T(k.desc, 12.sp, s.muted) }
                }
            }
            Row(Modifier.horizontalScroll(rememberScrollState()).padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Btn("Свой скин", "plus", primary = true) { editing = "new" }
                if (cur.id.startsWith("custom-")) Btn("Изменить «${cur.name}»", "pencil") { editing = cur.id }
                Btn("Вставить скин") {
                    val t = pasteText(ctx)?.let { Themes.import(it) }
                    if (t == null) c.deck.toast("В буфере обмена нет скина TabDock")
                    else { Themes.save(t); c.deck.setSkin(t.s("id")); c.deck.toast("Скин «${t.s("name")}» добавлен") }
                }
            }
            Column(Modifier.padding(top = 10.dp)) {
                T("Скин запоминается на этом устройстве. Свой скин можно передать на другое устройство кнопкой «Скопировать» в редакторе.", 13.sp, s.dim, modifier = Modifier.padding(bottom = 8.dp))
                if (!cur.id.startsWith("custom-")) Btn("Сделать скином для всех") { cfgPost(c, JSONObject().put("skin", cur.id)); c.deck.toast("Новые устройства откроются в «${cur.name}»") }
            }
        }
        Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
            WeatherSettings(c, Modifier.fillMaxWidth())
            DeckCard("Календарь компьютера", Modifier.fillMaxWidth()) {
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Seg("Показывать события", (cfg?.optBoolean("calendar", true) ?: true)) { cfgPost(c, JSONObject().put("calendar", true)) }
                    Seg("Выключить", !(cfg?.optBoolean("calendar", true) ?: true)) { cfgPost(c, JSONObject().put("calendar", false)) }
                }
                T(if (c.all.o("calendar").b("ok")) "Доступ к календарю есть." else "Доступа пока нет — на компьютере появится запрос разрешения.", 13.sp, s.dim, modifier = Modifier.padding(top = 8.dp))
            }
        }
        BottomBarSettings(c)
        DeckCard("Это устройство") {
            var notify by remember { mutableStateOf(c.deck.store.string("notify") != "0") }
            var standAuto by remember { mutableStateOf(c.deck.store.string("stand_auto") != "0") }
            T("Уведомления: экспорт закончился, срок сдачи сегодня или завтра", 14.sp, s.muted)
            Row(Modifier.horizontalScroll(rememberScrollState()).padding(top = 6.dp, bottom = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Seg("Включены", notify) { notify = true; c.deck.store.put("notify", "1") }
                Seg("Выключены", !notify) { notify = false; c.deck.store.put("notify", "0") }
            }
            T("Подставка: сама включается, когда телефон лежит боком на зарядке", 14.sp, s.muted)
            Row(Modifier.horizontalScroll(rememberScrollState()).padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Seg("Автоматически", standAuto) { standAuto = true; c.deck.store.put("stand_auto", "1") }
                Seg("Только кнопкой", !standAuto) { standAuto = false; c.deck.store.put("stand_auto", "0") }
            }
            T("Уведомления приходят, пока приложение открыто или свёрнуто; если его закрыть совсем — не проверяется ничего.", 12.sp, s.dim, modifier = Modifier.padding(top = 10.dp))
        }
        // Capture One exists only on the Mac: a Linux computer shows folder-based shoots only
        val mac = c.all.s("platform", "darwin") == "darwin"
        if (mac) DeliveredRule(c)
        AppsSettings(c)
        if (mac) CatalogSettings(c)
        FolderSettings(c)
        DeckCard("Компьютер") {
            val name by c.deck.serverName.collectAsState()
            T("$name · ${c.deck.api?.base ?: ""}", 16.sp)
            T("Сервер ${c.state.s("version")} · TabDock ${com.jjustping.tabdock.BuildConfigShim.VERSION}", 13.sp, s.muted)
            Row(Modifier.horizontalScroll(rememberScrollState()).padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Btn("Сменить компьютер", "computer") { onConnect() }
                Btn("Сканировать QR-код", "qr") { onScan() }
                Btn("Проверить обновления", "reset") { c.deck.checkUpdate(force = true) }
                Btn("Веб-версия", "link") { openWeb("/?tab=settings") }
            }
            T("Пароль для входа и новый ключ доступа задаются на самом компьютере (панель TabDock в браузере на компьютере или меню значка TabDock) — так их нельзя сменить с чужого устройства.", 13.sp, s.dim, modifier = Modifier.padding(top = 10.dp))
        }
        Spacer(Modifier.height(10.dp))
    }
}

@Composable private fun WeatherSettings(c: Ctx, modifier: Modifier) {
    val s = LocalSkin.current
    var q by remember { mutableStateOf("") }
    var res by remember { mutableStateOf(listOf<JSONObject>()) }
    var msg by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    DeckCard("Погода", modifier) {
        T("Город: " + (c.all.o("config").o("place").s("name").ifBlank { "не выбран" }), 14.sp, s.muted)
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 8.dp)) {
            TextInput(q, { q = it }, "Название города", Modifier.weight(1f)); Spacer(Modifier.width(8.dp))
            Btn("Найти", primary = true) { scope.launch {
                runCatching { c.deck.api!!.arr("/api/geocode?q=" + URLEncoder.encode(q, "UTF-8"), 8000).objs() }
                    .onSuccess { res = it; msg = if (it.isEmpty()) "Ничего не найдено" else "" }.onFailure { msg = "Нет интернета на компьютере" } } }
        }
        if (msg.isNotBlank()) T(msg, 13.sp, s.muted)
        for (r in res.take(5)) Inner(Modifier.fillMaxWidth().padding(top = 6.dp), onClick = { cfgPost(c, JSONObject().put("place", r)); res = emptyList() }) {
            T("${r.s("name")}, ${listOf(r.s("admin"), r.s("country")).filter { it.isNotBlank() }.joinToString(", ")}", 15.sp)
        }
    }
}

@Composable fun RulePicker(rule: JSONObject, onChange: (JSONObject) -> Unit) {
    val s = LocalSkin.current
    val type = rule.s("type", "export")
    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        for ((k, n) in listOf("export" to "Экспортированные", "color" to "С цветной меткой", "color_or_export" to "Метка или экспорт", "rating" to "По рейтингу"))
            Seg(n, type == k) { onChange(JSONObject(rule.toString()).put("type", k)) }
    }
    if (type == "color" || type == "color_or_export") Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically, modifier = Modifier.horizontalScroll(rememberScrollState()).padding(top = 10.dp)) {
        for (ci in 1..7) Box(Modifier.size(38.dp).clip(CircleShape).background(TAG_COLORS[ci]).border(3.dp, if (rule.i("color", 4) == ci) s.text else Color.Transparent, CircleShape)
            .clickable { onChange(JSONObject(rule.toString()).put("color", ci)) })
        T("метка «${TAG_NAMES[rule.i("color", 4)]}»", 14.sp, s.muted)
    }
    if (type == "rating") Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 10.dp)) {
        for (n in 1..5) Seg("★".repeat(n) + "+", rule.i("rating", 5) == n) { onChange(JSONObject(rule.toString()).put("rating", n)) }
    }
}

@Composable private fun DeliveredRule(c: Ctx) {
    val rule = c.all.o("config").o("done_rule") ?: JSONObject().put("type", "export").put("color", 4).put("rating", 5)
    DeckCard("Что считать отданными кадрами (Capture One)") {
        RulePicker(rule) { cfgPost(c, JSONObject().put("done_rule", it)) }
        T("Прогресс съёмки = отданные / отобранные (или все кадры).", 13.sp, LocalSkin.current.dim, modifier = Modifier.padding(top = 8.dp))
    }
}

@Composable private fun AppsSettings(c: Ctx) {
    val s = LocalSkin.current
    val apps = c.all.o("config").a("apps").strs()
    var q by remember { mutableStateOf("") }
    val installed by androidx.compose.runtime.produceState(emptyList<String>()) { value = runCatching { c.deck.api!!.arr("/api/apps_installed", 8000).strs() }.getOrDefault(emptyList()) }
    DeckCard("Приложения в быстрых действиях") {
        FlowChips(apps) { a -> cfgPost(c, JSONObject().put("apps", JSONArray(apps - a))) }
        Spacer(Modifier.height(10.dp))
        TextInput(q, { q = it }, "Добавить: начните вводить название", Modifier.fillMaxWidth())
        val sug = if (q.length < 2) emptyList() else installed.filter { it.contains(q, true) && it !in apps }.take(8)
        if (sug.isNotEmpty()) Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.horizontalScroll(rememberScrollState()).padding(top = 8.dp)) {
            for (a in sug) Seg(a, false) { cfgPost(c, JSONObject().put("apps", JSONArray(apps + a))); q = "" }
        }
        T("На главной показываются первые 8 установленных.", 13.sp, s.dim, modifier = Modifier.padding(top = 8.dp))
    }
}

@Composable fun FlowChips(items: List<String>, onRemove: (String) -> Unit) {
    val s = LocalSkin.current
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        for (row in items.chunked(if (LocalCompact.current) 2 else 5)) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for (a in row) Row(Modifier.clip(RoundedCornerShape(10.dp)).border(1.dp, s.accent, RoundedCornerShape(10.dp)).clickable { onRemove(a) }
                .padding(horizontal = 12.dp, vertical = 8.dp)) { T("$a  ✕", 14.sp, s.accent, maxLines = 1) }
        }
    }
}

@Composable private fun CatalogSettings(c: Ctx) {
    val s = LocalSkin.current
    var data by remember { mutableStateOf<JSONObject?>(null) }
    var path by remember { mutableStateOf("") }
    val manual = c.all.o("config").a("c1_catalogs").strs()
    LaunchedEffect(manual.joinToString()) { data = runCatching { c.deck.api!!.obj("/api/catalogs", 10000) }.getOrNull() }
    DeckCard("Каталоги Capture One") {
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Seg("Автоматически (открытый в Capture One)", manual.isEmpty()) { cfgPost(c, JSONObject().put("c1_catalogs", JSONArray())) }
            Seg("Выбрать вручную", manual.isNotEmpty()) { c.deck.toast("Отметьте нужные каталоги ниже") }
        }
        val active = data.a("active").strs().toSet()
        val found = data.a("found").objs()
        for (e in found) {
            val p = e.s("path"); val on = p in active
            Row(Modifier.fillMaxWidth().padding(top = 8.dp).clip(RoundedCornerShape(12.dp)).background(s.inner).clickable {
                val base = if (manual.isNotEmpty()) manual else active.toList()
                cfgPost(c, JSONObject().put("c1_catalogs", JSONArray(if (p in base) base - p else base + p)))
            }.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(26.dp).clip(CircleShape).background(if (on) s.accent else Color.Transparent).border(2.dp, if (on) s.accent else s.dim, CircleShape), contentAlignment = Alignment.Center) { if (on) Ic("check", 16.dp, s.onAccent) }
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    T(p.substringAfterLast('/') + if (e.b("current")) "  · открыт в Capture One" else "", 15.sp, weight = FontWeight.SemiBold, maxLines = 1)
                    T(p + (" · " + e.a("sources").strs().joinToString(", ")), 12.sp, s.muted, maxLines = 1)
                }
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 10.dp)) {
            TextInput(path, { path = it }, "/Volumes/Диск/Каталог.cocatalog", Modifier.weight(1f)); Spacer(Modifier.width(8.dp))
            Btn("Добавить путь", primary = true) { if (path.isNotBlank()) { cfgPost(c, JSONObject().put("c1_catalogs", JSONArray((manual + path.trim()).distinct()))); path = "" } }
        }
        T("Каталоги ищутся в настройках Capture One, Spotlight, «Изображениях» и на внешних дисках. Читаются только для чтения.", 13.sp, s.dim, modifier = Modifier.padding(top = 8.dp))
    }
}

@Composable private fun FolderSettings(c: Ctx) {
    val s = LocalSkin.current
    val cfg = c.all.o("config")
    val roots = cfg.a("folder_roots").objs()
    var path by remember { mutableStateOf("") }
    var app by remember { mutableStateOf("Photon Studio") }
    var dirs by remember(cfg.toString()) { mutableStateOf((cfg.a("export_dirs").strs().ifEmpty { c.all.a("export_dirs_default").strs() }).joinToString(", ")) }
    DeckCard("Папки со съёмками · Photon Studio, Photoshop и др.") {
        for ((i, r) in roots.withIndex()) Row(Modifier.fillMaxWidth().padding(bottom = 8.dp).clip(RoundedCornerShape(12.dp)).background(s.inner).padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) { T(r.s("app"), 15.sp, weight = FontWeight.SemiBold); T(r.s("path"), 12.sp, s.muted, mono = true) }
            Btn(icon = "plus", danger = true) { cfgPost(c, JSONObject().put("folder_roots", JSONArray(roots.filterIndexed { j, _ -> j != i }))) }
        }
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            TextInput(path, { path = it }, if (c.all.s("platform", "darwin") == "darwin") "/Volumes/SSD/Съёмки" else "/home/имя/Изображения/Съёмки", Modifier.fillMaxWidth())
            TextInput(app, { app = it }, "Программа", Modifier.fillMaxWidth())
            Btn("Добавить", primary = true) { if (path.isNotBlank()) { cfgPost(c, JSONObject().put("folder_roots", JSONArray(roots + JSONObject().put("path", path.trim()).put("app", app.ifBlank { "Папки" })))); path = "" } }
        }
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 10.dp)) {
            TextInput(dirs, { dirs = it }, "Подпапки с готовыми файлами через запятую", Modifier.weight(1f)); Spacer(Modifier.width(8.dp))
            Btn("Сохранить") { cfgPost(c, JSONObject().put("export_dirs", JSONArray(dirs.split(",").map { it.trim() }.filter { it.isNotBlank() }))) }
        }
        T("Каждая подпапка = съёмка. Прогресс = готовые файлы в подпапке экспорта / исходники (RAW).", 13.sp, s.dim, modifier = Modifier.padding(top = 8.dp))
    }
}

// ===================== native first-run setup =====================
private val USAGE = listOf(Triple("photo", "aperture", "Фото и съёмки" to "Capture One, Photon Studio, Photoshop: прогресс, отбор, сроки, wfolio"),
    Triple("work", "check", "Работа и задачи" to "Задачи, заметки, календарь, фокус-таймер"),
    Triple("fun", "note", "Отдых и музыка" to "Плеер, погода, часы, быстрые действия"),
    Triple("admin", "computer", "Система и сеть" to "Нагрузка, диски, сеть, команды"))

@Composable
fun SetupWizard(deck: Deck, all: JSONObject?, onDone: () -> Unit) {
    val s = LocalSkin.current
    var step by remember { mutableStateOf(0) }
    var usage by remember { mutableStateOf(all.o("config").a("usage").strs().toSet().ifEmpty { setOf("photo") }) }
    var editor by remember { mutableStateOf("c1") }
    var rule by remember { mutableStateOf(all.o("config").o("done_rule") ?: JSONObject().put("type", "color_or_export").put("color", 4).put("rating", 5)) }
    var folder by remember { mutableStateOf("") }
    var place by remember { mutableStateOf<JSONObject?>(null) }
    var q by remember { mutableStateOf("") }
    var res by remember { mutableStateOf(listOf<JSONObject>()) }
    val scope = rememberCoroutineScope()
    val steps = listOf("hello", "usage") + (if ("photo" in usage) listOf("photo") else emptyList()) + listOf("weather", "look", "done")
    val name = steps[step.coerceIn(0, steps.size - 1)]
    fun finish() {
        val order = listOf("photo", "work", "fun", "admin").filter { it in usage }
        val spaces = order.map { fromTemplate(it) }
        val body = JSONObject().put("setup_done", true).put("usage", JSONArray(order)).put("spaces", JSONArray(spaces))
            .put("tabs", JSONArray(listOf("notes", "mac", "connect", "settings") + if ("photo" in usage && editor != "none") listOf("shoots") else emptyList()))
            .put("skin", deck.skin.value ?: "classic")
        if ("photo" in usage && editor == "c1") body.put("done_rule", rule)
        if ("photo" in usage && editor == "folders" && folder.isNotBlank())
            body.put("folder_roots", JSONArray(all.o("config").a("folder_roots").objs() + JSONObject().put("path", folder.trim()).put("app", "Photon Studio")))
        place?.let { body.put("place", it) }
        deck.post("/api/config", body)
        deck.store.space = spaces.firstOrNull()?.s("id")
        onDone()
    }
    Box(Modifier.fillMaxSize().background(s.bg).statusBarsPadding().navigationBarsPadding(), contentAlignment = Alignment.Center) {
        val compact = LocalCompact.current
        DeckCard(null, Modifier.widthIn(max = 900.dp).fillMaxWidth(if (compact) .96f else .92f).let { if (compact) it.fillMaxHeight(.94f) else it }, pad = if (compact) 18.dp else 26.dp) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Row(Modifier.weight(1f), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    steps.indices.forEach { i -> Box(Modifier.size(28.dp, 6.dp).clip(RoundedCornerShape(3.dp)).background(if (i == step) s.accent else if (i < step) s.muted else s.border)) }
                }
                Btn("Пропустить") { deck.post("/api/config", JSONObject().put("setup_done", true)); onDone() }
            }
            Spacer(Modifier.height(18.dp))
            Column(Modifier.weight(1f, fill = compact).verticalScroll(rememberScrollState())) {
                when (name) {
                    "hello" -> Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
                        Ic("computer", 64.dp, s.accent); Spacer(Modifier.height(10.dp))
                        T("Привет! Это TabDock", 32.sp, weight = FontWeight.Bold)
                        T("Планшет или телефон, который лежит без дела, становится доком для работы: задачи, съёмки, музыка, состояние компьютера. Настроим всё под вас — займёт минуту.", 17.sp, s.muted, align = androidx.compose.ui.text.style.TextAlign.Center, modifier = Modifier.padding(top = 8.dp))
                    }
                    "usage" -> {
                        T("Для чего вам док?", 26.sp, weight = FontWeight.Bold); T("Можно выбрать несколько — для каждого будет своё пространство.", 15.sp, s.muted)
                        Spacer(Modifier.height(12.dp))
                        Grid(USAGE, if (compact) 1 else 2, 12) { (id, ic, t) ->
                            val on = id in usage
                            Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(if (on) s.accent.copy(.1f) else s.inner)
                                .border(2.dp, if (on) s.accent else s.border, RoundedCornerShape(18.dp)).clickable { usage = if (on) usage - id else usage + id }.padding(18.dp)) {
                                Ic(ic, 30.dp, s.accent); T(t.first, 18.sp, weight = FontWeight.SemiBold, modifier = Modifier.padding(top = 6.dp)); T(t.second, 14.sp, s.muted)
                            }
                        }
                    }
                    "photo" -> {
                        T("Съёмки", 26.sp, weight = FontWeight.Bold); T("Где вы обрабатываете фото?", 14.sp, s.muted, modifier = Modifier.padding(top = 6.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.horizontalScroll(rememberScrollState()).padding(vertical = 8.dp)) {
                            Seg("Capture One", editor == "c1") { editor = "c1" }; Seg("Photon Studio, Photoshop… (папки)", editor == "folders") { editor = "folders" }; Seg("Пока не нужно", editor == "none") { editor = "none" }
                        }
                        if (editor == "folders") TextInput(folder, { folder = it }, "/Volumes/SSD/Съёмки — папка, где каждая подпапка = съёмка", Modifier.fillMaxWidth())
                        if (editor == "c1") { T("Что считать отданными кадрами?", 14.sp, s.muted, modifier = Modifier.padding(top = 10.dp, bottom = 6.dp)); RulePicker(rule) { rule = it }
                            T("«Метка или экспорт» удобно, если раньше готовые кадры не отмечались.", 13.sp, s.dim, modifier = Modifier.padding(top = 8.dp)) }
                    }
                    "weather" -> {
                        T("Погода", 26.sp, weight = FontWeight.Bold); T("Город для погоды на главной. Можно пропустить.", 15.sp, s.muted)
                        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 10.dp)) {
                            TextInput(q, { q = it }, "Название города", Modifier.weight(1f)); Spacer(Modifier.width(8.dp))
                            Btn("Найти", primary = true) { scope.launch { res = runCatching { deck.api!!.arr("/api/geocode?q=" + URLEncoder.encode(q, "UTF-8"), 8000).objs() }.getOrDefault(emptyList()) } }
                        }
                        for (r in res.take(5)) Seg("${r.s("name")}, ${r.s("country")}", place?.s("name") == r.s("name") && place?.s("country") == r.s("country")) { place = r }
                    }
                    "look" -> {
                        T("Оформление", 26.sp, weight = FontWeight.Bold); Spacer(Modifier.height(10.dp))
                        Grid(SKINS, if (compact) 2 else 4) { k -> Column(Modifier.clip(RoundedCornerShape(14.dp)).border(2.dp, if (k.id == (deck.skin.value ?: "classic")) s.accent else Color.Transparent, RoundedCornerShape(14.dp))
                            .background(s.inner).clickable { deck.setSkin(k.id) }) {
                            Box(Modifier.fillMaxWidth().height(56.dp).background(k.bg)) { Box(Modifier.padding(8.dp).size(60.dp, 34.dp).clip(RoundedCornerShape(8.dp)).background(k.card)) }
                            T(k.name, 14.sp, weight = FontWeight.SemiBold, modifier = Modifier.padding(8.dp)) } }
                    }
                    "done" -> Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
                        Ic("check", 64.dp, s.green); T("Готово!", 32.sp, weight = FontWeight.Bold)
                        T("Пространства: " + listOf("photo", "work", "fun", "admin").filter { it in usage }.joinToString(", ") { USAGE.first { u -> u.first == it }.third.first },
                            17.sp, s.muted, align = androidx.compose.ui.text.style.TextAlign.Center)
                    }
                }
            }
            Row(Modifier.fillMaxWidth().padding(top = 20.dp), horizontalArrangement = Arrangement.spacedBy(10.dp, Alignment.End)) {
                if (step > 0) Btn("Назад", "prev") { step-- }
                Btn(when (name) { "hello" -> "Начать"; "done" -> "Открыть TabDock"; else -> "Дальше" }, primary = true) {
                    if (name == "usage" && usage.isEmpty()) deck.toast("Выберите хотя бы один вариант")
                    else if (name == "done") finish() else step++
                }
            }
        }
    }
}


/** Which tabs the bottom bar shows (for all devices of this computer). «Главная» and «Настройки» always stay. */
@Composable fun BottomBarSettings(c: Ctx) {
    val s = LocalSkin.current
    val all = listOf("shoots" to "Съёмки", "notes" to "Справка", "files" to "Файлы", "mac" to "Компьютер")
    val cur = c.all.o("config").a("tabs")?.strs() ?: listOf("shoots", "notes", "files", "mac", "connect", "settings")
    DeckCard("Нижняя панель") {
        T("Какие кнопки показывать внизу. «Главная» и «Настройки» есть всегда.", 14.sp, s.muted)
        Row(Modifier.horizontalScroll(rememberScrollState()).padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for ((id, name) in all) {
                val on = id in cur
                Seg((if (on) "✓ " else "") + name, on) {
                    val next = if (on) cur - id else cur + id
                    cfgPost(c, JSONObject().put("tabs", JSONArray(next.distinct())))
                }
            }
        }
        T("Например, если вы не фотограф, уберите «Съёмки». Действует на всех планшетах и телефонах этого компьютера.", 12.sp, s.dim,
            modifier = Modifier.padding(top = 8.dp))
    }
}
