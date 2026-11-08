package com.jjustping.tabdock.ui

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
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
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
import com.jjustping.tabdock.data.Conn
import com.jjustping.tabdock.data.Deck
import com.jjustping.tabdock.data.Fmt
import com.jjustping.tabdock.data.a
import com.jjustping.tabdock.data.b
import com.jjustping.tabdock.data.d
import com.jjustping.tabdock.data.i
import com.jjustping.tabdock.data.o
import com.jjustping.tabdock.data.objs
import com.jjustping.tabdock.data.s
import com.jjustping.tabdock.data.weatherIcon
import kotlinx.coroutines.delay
import org.json.JSONArray
import org.json.JSONObject
import java.util.Calendar

private val TABS = listOf(Triple("home", "home", "Главная"), Triple("shoots", "aperture", "Съёмки"), Triple("notes", "book", "Справка"),
    Triple("mac", "computer", "Компьютер"), Triple("settings", "gear", "Настройки"))

@Composable
fun TabDockApp(deck: Deck) {
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
    var stand by remember { mutableStateOf(false) }
    var scanning by remember { mutableStateOf(false) }
    val update by deck.update.collectAsState()
    var standDismissed by remember { mutableStateOf(false) }
    val synced by deck.syncedAt.collectAsState()
    val dialogs = remember { Dialogs(deck) }
    dialogs.onCull = { cull = it }
    var toast by remember { mutableStateOf<String?>(null) }
    var banner by remember { mutableStateOf<JSONObject?>(null) }
    LaunchedEffect(Unit) { deck.toasts.collect { toast = it; delay(2400); if (toast == it) toast = null } }
    LaunchedEffect(Unit) { deck.events.collect { banner = it; delay(12000); if (banner === it) banner = null } }

    // phone = the short side is under 600dp (a phone in landscape stays a phone)
    val compact = androidx.compose.ui.platform.LocalConfiguration.current.smallestScreenWidthDp < 600
    // "Подставка" switches on by itself on a phone lying sideways on a charger (can be turned off in settings)
    val charging = rememberCharging(); val land = isLandscape()
    val autoStand = compact && land && charging && deck.store.string("stand_auto") != "0"
    LaunchedEffect(autoStand) { if (!autoStand) standDismissed = false }
    androidx.compose.runtime.CompositionLocalProvider(LocalCompact provides compact) {
    ProvideSkin(s) {
        Box(Modifier.fillMaxSize().background(s.bg)) {
            if (s.bgImage != null) SkinBackground(deck, s)
            when {
                scanning -> QrScanner(onResult = { text ->
                    scanning = false
                    if (deck.pairFromLink(text)) forceConnect = false
                    else deck.toast("Это не QR-код TabDock. Он показан на компьютере: в панели TabDock в браузере или в меню значка")
                }, onClose = { scanning = false })
                conn == Conn.NEED_PAIRING || forceConnect -> ConnectScreen(deck, onScan = { scanning = true }) { forceConnect = false }
                all == null -> WaitScreen(deck, conn) { forceConnect = true }
                web != null -> WebScreen(deck, web!!) { web = null }
                all != null && (wizard || (!setupSeen && !all.o("config").b("setup_done"))) -> SetupWizard(deck, all) { wizard = false; setupSeen = true; tab = "home" }
                all != null && (stand || (autoStand && !standDismissed)) && conn != Conn.NEED_PAIRING ->
                    StandScreen(Ctx(deck, all, state, {}, {}, {}, {})) { stand = false; standDismissed = true }
                cull != null -> Box(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(if (compact) 10.dp else 20.dp)) { CullScreen(deck, cull!!) { cull = null } }
                else -> {
                    val tabsShown = all.o("config").a("tabs")?.let { arr -> (0 until arr.length()).map { arr.getString(it) } }
                    val c = Ctx(deck, all, state, openShoot = { dialogs.shoot(it) }, openNote = { dialogs.note(it) },
                        goTab = { tab = it; deck.store.put("tab", it) },
                        editWidget = { w -> dialogs.widgetOpts(w, all) { opts -> saveWidgetOpts(deck, all, w, opts) } })
                    Column(Modifier.fillMaxSize().imePadding()) {
                        TopBar(c) { stand = true }
                        Box(Modifier.weight(1f).padding(horizontal = if (compact) 12.dp else 20.dp, vertical = 6.dp)) {
                            when (tab) {
                                "shoots" -> ShootsScreen(c)
                                "notes" -> NotesScreen(c)
                                "mac" -> ComputerScreen(c)
                                "settings" -> SettingsScreen(c, openWeb = { web = it }, onConnect = { forceConnect = true }, onWizard = { wizard = true }, onScan = { scanning = true })
                                else -> HomeScreen(c, dialogs)
                            }
                        }
                        BottomTabs(tab, tabsShown) { tab = it; deck.store.put("tab", it) }
                    }
                    if (conn == Conn.LOST || conn == Conn.STARTING) {
                        // one short line over the top bar; the VPN explanation opens on tap
                        var more by remember { mutableStateOf(false) }
                        val vpn = com.jjustping.tabdock.data.Lan.vpn
                        val at = if (synced > 0) java.text.SimpleDateFormat("HH:mm", java.util.Locale.getDefault()).format(java.util.Date(synced)) else null
                        Column(Modifier.fillMaxWidth().statusBarsPadding().background(if (conn == Conn.LOST) s.red else s.inner)
                            .clickable(enabled = vpn) { more = !more }.padding(horizontal = 12.dp, vertical = 5.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                            T(when {
                                conn == Conn.STARTING -> "Подключаюсь к компьютеру…" + (at?.let { " · данные от $it" } ?: "")
                                vpn -> "Нет связи: VPN на этом устройстве не пускает в домашнюю сеть" + (at?.let { " · данные от $it" } ?: "") + (if (more) "" else " · подробнее")
                                else -> "Нет связи с компьютером" + (at?.let { " · данные от $it" } ?: "") + " · переподключусь сам"
                            }, 13.sp, if (conn == Conn.LOST) Color.White else s.muted, FontWeight.SemiBold, maxLines = 1)
                            if (more && vpn) T(com.jjustping.tabdock.data.Lan.VPN_HINT, 13.sp, Color.White, maxLines = 4,
                                align = androidx.compose.ui.text.style.TextAlign.Center, modifier = Modifier.padding(top = 3.dp))
                        }
                    }
                    dialogs.Host()
                    update?.let { u -> UpdateDialog(deck, u) { deck.update.value = null } }
                }
            }
            AnimatedVisibility(banner != null, Modifier.align(Alignment.TopCenter).padding(top = 16.dp), enter = slideInVertically { -it }, exit = slideOutVertically { -it }) {
                banner?.let { e ->
                    Row(Modifier.widthIn(min = if (compact) 0.dp else 420.dp).padding(horizontal = 12.dp).clip(RoundedCornerShape(18.dp)).background(Color(0xFF10241F)).border(1.dp, s.green, RoundedCornerShape(18.dp))
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
}

private fun saveWidgetOpts(deck: Deck, all: JSONObject?, w: JSONObject, opts: JSONObject) {
    val spaces = spacesOf(all).map { JSONObject(it.toString()) }
    for (sp in spaces) for (x in sp.a("widgets").objs()) if (x.s("id") == w.s("id")) x.put("opts", opts)
    deck.post("/api/config", JSONObject().put("spaces", JSONArray(spaces)))
}

@Composable private fun TopBar(c: Ctx, onStand: () -> Unit) {
    val s = LocalSkin.current
    val now by produceState(System.currentTimeMillis()) { while (true) { value = System.currentTimeMillis(); delay(5000) } }
    val cal = Calendar.getInstance().apply { timeInMillis = now }
    val sys = c.state.o("sys"); val w = c.all.o("weather")
    if (LocalCompact.current) {
        // phone: time + weather on one line, the computer's numbers in a scrollable strip below
        // (lying sideways the strip moves into the same line, to keep the height for widgets)
        val land = isLandscape()
        Column(Modifier.fillMaxWidth().padding(start = 14.dp, end = 14.dp, top = 8.dp, bottom = 2.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                T("${Fmt.pad(cal.get(Calendar.HOUR_OF_DAY))}:${Fmt.pad(cal.get(Calendar.MINUTE))}", 30.sp, weight = FontWeight.Bold)
                Spacer(Modifier.width(10.dp))
                T(Fmt.DS[cal.get(Calendar.DAY_OF_WEEK) - 1] + ", ${cal.get(Calendar.DAY_OF_MONTH)} ${Fmt.MON[cal.get(Calendar.MONTH)]}", 14.sp, s.muted, modifier = if (land) Modifier else Modifier.weight(1f), maxLines = 1)
                if (land) { Spacer(Modifier.width(14.dp)); Row(Modifier.weight(1f).horizontalScroll(rememberScrollState()), verticalAlignment = Alignment.CenterVertically) { PhoneStats(c) } }
                if (w.d("temp") != null) { Ic(weatherIcon(w.i("code")), 20.dp); Spacer(Modifier.width(6.dp)); T("${w.d("temp")?.toInt()}°", 18.sp, weight = FontWeight.Bold) }
                Spacer(Modifier.width(10.dp))
                Box(Modifier.size(40.dp).clip(RoundedCornerShape(12.dp)).background(s.inner).border(1.dp, s.border, RoundedCornerShape(12.dp)).clickable { onStand() },
                    contentAlignment = Alignment.Center) { Ic("display", 20.dp) }
            }
            if (!land) Row(Modifier.horizontalScroll(rememberScrollState()).padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) { PhoneStats(c) }
        }
        return
    }
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
            else { Ic("cloud", 20.dp, s.muted); Spacer(Modifier.width(8.dp)); T(when { !w.b("configured") -> "Город для погоды — в настройках"; w.s("error").isNotBlank() -> "Погода: нет связи с сервисом"; else -> "Погода загружается…" }, 15.sp, s.muted, maxLines = 1) }
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
        Box(Modifier.padding(end = 8.dp).size(48.dp).clip(RoundedCornerShape(14.dp)).background(s.inner).border(1.dp, s.border, RoundedCornerShape(14.dp))
            .clickable { onStand() }, contentAlignment = Alignment.Center) { Ic("display", 24.dp) }
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


/** No data yet: connecting, loading, or the paired computer is not answering. */
@Composable private fun WaitScreen(deck: Deck, conn: Conn, onOther: () -> Unit) {
    val s = LocalSkin.current
    val name by deck.serverName.collectAsState()
    Column(Modifier.fillMaxSize().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        Ic("computer", 56.dp, s.accent); Spacer(Modifier.height(14.dp))
        T(when (conn) { Conn.LOST -> "Жду компьютер" + (if (name.isNotBlank()) " «$name»" else ""); Conn.CONNECTED -> "Загружаю данные…"; else -> "TabDock · ищу компьютер…" },
            22.sp, weight = FontWeight.Bold, align = androidx.compose.ui.text.style.TextAlign.Center)
        if (conn == Conn.LOST) {
            T(if (com.jjustping.tabdock.data.Lan.vpn) com.jjustping.tabdock.data.Lan.VPN_HINT + " Подключусь сам, как только связь появится."
              else "Подключусь сам, как только он появится в сети. Проверьте, что компьютер включён, TabDock на нём запущен и устройства в одной Wi-Fi сети.",
                15.sp, s.muted, align = androidx.compose.ui.text.style.TextAlign.Center, modifier = Modifier.widthIn(max = 560.dp).padding(top = 8.dp))
            Spacer(Modifier.height(18.dp))
            Btn("Другой компьютер", "computer") { onOther() }
        }
    }
}


@Composable private fun PhoneStats(c: Ctx) {
    val sys = c.state.o("sys")
    val root = sys.a("disks").objs().firstOrNull { !it.b("external") }
    Stat("CPU", "${sys.d("cpu")?.toInt() ?: "—"}%", (sys.d("cpu") ?: 0.0) > 85)
    Stat("Темп.", "${sys.o("temp").d("cpu")?.toInt() ?: "—"}°", (sys.o("temp").d("cpu") ?: 0.0) > 85)
    Stat("Память", "${sys.o("mem").d("pct")?.toInt() ?: "—"}%", (sys.o("mem").d("pct") ?: 0.0) > 90)
    Stat("Диск", Fmt.bytes(root.d("free")), (root.d("pct") ?: 0.0) > 92)
    c.all.o("shoots").a("volumes").objs().firstOrNull()?.let { v ->
        val d = sys.a("disks").objs().firstOrNull { it.s("mount") == v.s("mount") }
        Stat(v.s("name"), d?.let { Fmt.bytes(it.d("free")) } ?: "нет", d == null || (d.d("pct") ?: 0.0) > 92)
    }
}
