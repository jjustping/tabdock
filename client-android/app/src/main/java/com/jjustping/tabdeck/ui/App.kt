package com.jjustping.tabdeck.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
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
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jjustping.tabdeck.data.Conn
import com.jjustping.tabdeck.data.Deck
import com.jjustping.tabdeck.data.Fmt
import com.jjustping.tabdeck.data.a
import com.jjustping.tabdeck.data.b
import com.jjustping.tabdeck.data.d
import com.jjustping.tabdeck.data.i
import com.jjustping.tabdeck.data.o
import com.jjustping.tabdeck.data.objs
import com.jjustping.tabdeck.data.s
import com.jjustping.tabdeck.data.weatherIcon
import kotlinx.coroutines.delay
import org.json.JSONArray
import org.json.JSONObject
import java.util.Calendar

private val TABS = listOf(Triple("home", "home", "Главная"), Triple("shoots", "aperture", "Съёмки"), Triple("notes", "book", "Справка"),
    Triple("mac", "computer", "Компьютер"), Triple("settings", "gear", "Настройки"))

@Composable
fun TabDeckApp(deck: Deck) {
    val skinId by deck.skin.collectAsState()
    val conn by deck.conn.collectAsState()
    val all by deck.all.collectAsState()
    val state by deck.state.collectAsState()
    val s = skinById(skinId ?: all.o("config").s("skin").ifBlank { null })
    var tab by remember { mutableStateOf(deck.store.string("tab") ?: "home") }
    var web by remember { mutableStateOf<String?>(null) }
    var forceConnect by remember { mutableStateOf(false) }
    var cull by remember { mutableStateOf<JSONObject?>(null) }
    var wizard by remember { mutableStateOf(false) }
    var setupSeen by remember { mutableStateOf(false) }
    val dialogs = remember { Dialogs(deck) }
    dialogs.onCull = { cull = it }
    var toast by remember { mutableStateOf<String?>(null) }
    var banner by remember { mutableStateOf<JSONObject?>(null) }
    LaunchedEffect(Unit) { deck.toasts.collect { toast = it; delay(2400); if (toast == it) toast = null } }
    LaunchedEffect(Unit) { deck.events.collect { banner = it; delay(12000); if (banner === it) banner = null } }

    ProvideSkin(s) {
        Box(Modifier.fillMaxSize().background(s.bg)) {
            when {
                conn == Conn.STARTING -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { T("TabDeck · ищу компьютер…", 18.sp, s.muted) }
                conn == Conn.NEED_PAIRING || forceConnect -> ConnectScreen(deck) { forceConnect = false }
                web != null -> WebScreen(deck, web!!) { web = null }
                all != null && (wizard || (!setupSeen && !all.o("config").b("setup_done"))) -> SetupWizard(deck, all) { wizard = false; setupSeen = true; tab = "home" }
                cull != null -> Box(Modifier.fillMaxSize().padding(20.dp)) { CullScreen(deck, cull!!) { cull = null } }
                else -> {
                    val tabsShown = all.o("config").a("tabs")?.let { arr -> (0 until arr.length()).map { arr.getString(it) } }
                    val c = Ctx(deck, all, state, openShoot = { dialogs.shoot(it) }, openNote = { dialogs.note(it) },
                        goTab = { tab = it; deck.store.put("tab", it) },
                        editWidget = { w -> dialogs.widgetOpts(w, all) { opts -> saveWidgetOpts(deck, all, w, opts) } })
                    Column(Modifier.fillMaxSize().imePadding()) {
                        TopBar(c)
                        Box(Modifier.weight(1f).padding(horizontal = 20.dp, vertical = 6.dp)) {
                            when (tab) {
                                "shoots" -> ShootsScreen(c)
                                "notes" -> NotesScreen(c)
                                "mac" -> ComputerScreen(c)
                                "settings" -> SettingsScreen(c, openWeb = { web = it }, onConnect = { forceConnect = true }, onWizard = { wizard = true })
                                else -> HomeScreen(c, dialogs)
                            }
                        }
                        BottomTabs(tab, tabsShown) { tab = it; deck.store.put("tab", it) }
                    }
                    if (conn == Conn.LOST) Box(Modifier.fillMaxWidth().background(s.red).padding(6.dp), contentAlignment = Alignment.Center) {
                        T("Нет связи с компьютером — жду его в сети, переподключусь сам", 14.sp, Color.White, FontWeight.SemiBold)
                    }
                    dialogs.Host()
                }
            }
            AnimatedVisibility(banner != null, Modifier.align(Alignment.TopCenter).padding(top = 16.dp), enter = slideInVertically { -it }, exit = slideOutVertically { -it }) {
                banner?.let { e ->
                    Row(Modifier.widthIn(min = 420.dp).clip(RoundedCornerShape(18.dp)).background(Color(0xFF10241F)).border(1.dp, s.green, RoundedCornerShape(18.dp))
                        .clickable { banner = null }.padding(horizontal = 22.dp, vertical = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                        Ic("check", 32.dp, s.green); Spacer(Modifier.width(14.dp))
                        Column { T("Экспорт закончился", 20.sp, Color.White, FontWeight.Bold)
                            T("«${e.s("name")}»: +${e.i("added")} кадров" + (if (e.i("target") > 0) " · ${e.i("done")} из ${e.i("target")}" else ""), 16.sp, Color(0xFFCFE9DF)) }
                    }
                }
            }
            toast?.let { m ->
                Box(Modifier.align(Alignment.BottomCenter).padding(bottom = 96.dp).clip(RoundedCornerShape(14.dp)).background(s.inner)
                    .border(1.dp, s.border, RoundedCornerShape(14.dp)).padding(horizontal = 22.dp, vertical = 14.dp)) { T(m, 16.sp) }
            }
        }
    }
}

private fun saveWidgetOpts(deck: Deck, all: JSONObject?, w: JSONObject, opts: JSONObject) {
    val spaces = spacesOf(all).map { JSONObject(it.toString()) }
    for (sp in spaces) for (x in sp.a("widgets").objs()) if (x.s("id") == w.s("id")) x.put("opts", opts)
    deck.post("/api/config", JSONObject().put("spaces", JSONArray(spaces)))
}

@Composable private fun TopBar(c: Ctx) {
    val s = LocalSkin.current
    val now by produceState(System.currentTimeMillis()) { while (true) { value = System.currentTimeMillis(); delay(5000) } }
    val cal = Calendar.getInstance().apply { timeInMillis = now }
    val sys = c.state.o("sys"); val w = c.all.o("weather")
    Row(Modifier.fillMaxWidth().padding(start = 22.dp, end = 22.dp, top = 10.dp, bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Column {
            T("${Fmt.pad(cal.get(Calendar.HOUR_OF_DAY))}:${Fmt.pad(cal.get(Calendar.MINUTE))}", 38.sp, weight = FontWeight.Bold)
            T(Fmt.DAYS[cal.get(Calendar.DAY_OF_WEEK) - 1].replaceFirstChar { it.uppercase() } + ", ${cal.get(Calendar.DAY_OF_MONTH)} ${Fmt.MON[cal.get(Calendar.MONTH)]}", 14.sp, s.muted)
        }
        Spacer(Modifier.width(18.dp))
        Row(Modifier.clip(RoundedCornerShape(999.dp)).background(s.inner).border(1.dp, s.border, RoundedCornerShape(999.dp)).padding(horizontal = 14.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically) {
            if (w.d("temp") != null) { Ic(weatherIcon(w.i("code")), 22.dp); Spacer(Modifier.width(8.dp)); T("${w.d("temp")?.toInt()}°", 18.sp, weight = FontWeight.Bold)
                Spacer(Modifier.width(8.dp)); T("${w.s("text")} · ${w.s("place")}", 15.sp, s.muted, maxLines = 1) }
            else { Ic("cloud", 20.dp, s.muted); Spacer(Modifier.width(8.dp)); T("Город для погоды — в настройках", 15.sp, s.muted) }
        }
        Spacer(Modifier.weight(1f))
        val root = sys.a("disks").objs().firstOrNull { !it.b("external") }
        Stat("CPU", "${sys.d("cpu")?.toInt() ?: "—"}%", (sys.d("cpu") ?: 0.0) > 85)
        Stat("Темп.", "${sys.o("temp").d("cpu")?.toInt() ?: "—"}°", (sys.o("temp").d("cpu") ?: 0.0) > 85)
        Stat("Память", "${sys.o("mem").d("pct")?.toInt() ?: "—"}%", (sys.o("mem").d("pct") ?: 0.0) > 90)
        Stat("Диск", Fmt.bytes(root.d("free")), (root.d("pct") ?: 0.0) > 92)
        c.all.o("shoots").a("volumes").objs().firstOrNull()?.let { v ->
            val d = sys.a("disks").objs().firstOrNull { it.s("mount") == v.s("mount") }
            Stat(v.s("name"), d?.let { Fmt.bytes(it.d("free")) } ?: "нет", d == null || (d.d("pct") ?: 0.0) > 92)
        }
        val awake = c.state.b("awake")
        Box(Modifier.size(48.dp).clip(RoundedCornerShape(14.dp)).background(if (awake) s.amber.copy(.2f) else s.inner)
            .border(1.dp, if (awake) s.amber else s.border, RoundedCornerShape(14.dp)).clickable { c.deck.action("awake") }, contentAlignment = Alignment.Center) {
            Ic("cup", 24.dp, if (awake) s.amber else s.text)
        }
    }
}

@Composable private fun Stat(label: String, value: String, warn: Boolean) {
    val s = LocalSkin.current
    Column(Modifier.padding(end = 8.dp).clip(RoundedCornerShape(12.dp)).background(s.inner).border(1.dp, s.border, RoundedCornerShape(12.dp))
        .padding(horizontal = 12.dp, vertical = 6.dp)) {
        T(label.uppercase(), 10.sp, s.muted, maxLines = 1); T(value, 16.sp, if (warn) s.red else s.text, FontWeight.Bold, maxLines = 1)
    }
}

@Composable private fun BottomTabs(tab: String, shown: List<String>?, onTab: (String) -> Unit) {
    val s = LocalSkin.current
    Row(Modifier.fillMaxWidth().background(s.tabs).padding(horizontal = 22.dp, vertical = 6.dp), horizontalArrangement = Arrangement.Center) {
        for ((id, ic, name) in TABS) {
            if (shown != null && id != "home" && id != "settings" && id !in shown) continue
            val on = tab == id
            Column(Modifier.widthIn(max = 170.dp).weight(1f).clip(RoundedCornerShape(14.dp)).background(if (on) s.inner else Color.Transparent)
                .clickable { onTab(id) }.padding(vertical = 6.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Ic(ic, 24.dp, if (on) s.accent else s.muted); T(name, 13.sp, if (on) s.text else s.muted)
            }
        }
    }
}
