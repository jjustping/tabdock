package com.jjustping.tabdock.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.util.Base64
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jjustping.tabdock.data.Deck
import com.jjustping.tabdock.data.Store
import com.jjustping.tabdock.data.a
import com.jjustping.tabdock.data.o
import com.jjustping.tabdock.data.objs
import com.jjustping.tabdock.data.s
import org.json.JSONArray
import org.json.JSONObject

/**
 * Own skins ("Свой скин"): a small JSON recipe on top of one of the built-in skins —
 * accent colour, background (colour, gradient or a shoot cover), card style and corner radius.
 * Kept on this device; shared between devices as a short "tabdock-theme:…" text.
 */
object Themes {
    val custom = mutableStateListOf<Skin>()
    private var recipes = listOf<JSONObject>()
    private var store: Store? = null

    fun load(s: Store) {
        store = s
        recipes = runCatching { JSONArray(s.string("themes") ?: "[]").objs() }.getOrDefault(emptyList())
        custom.clear(); custom.addAll(recipes.map { build(it) })
    }
    fun recipe(id: String) = recipes.firstOrNull { it.s("id") == id }
    fun save(t: JSONObject) {
        recipes = recipes.filter { it.s("id") != t.s("id") } + t
        persist()
    }
    fun delete(id: String) { recipes = recipes.filter { it.s("id") != id }; persist() }
    private fun persist() {
        store?.put("themes", JSONArray(recipes).toString())
        custom.clear(); custom.addAll(recipes.map { build(it) })
    }

    fun export(t: JSONObject): String =
        "tabdock-theme:" + Base64.encodeToString(JSONObject(t.toString()).apply { remove("cover") }.toString().toByteArray(), Base64.NO_WRAP)

    /** Accepts the "tabdock-theme:…" text or plain JSON; returns the recipe with a fresh id. */
    fun import(text: String): JSONObject? = runCatching {
        val raw = text.trim()
        val json = if (raw.startsWith("tabdock-theme:")) String(Base64.decode(raw.removePrefix("tabdock-theme:"), Base64.DEFAULT)) else raw
        val t = JSONObject(json)
        require(t.has("accent") || t.has("base"))
        t.put("id", newId()).put("name", t.s("name", "Импортированный").take(40))
    }.getOrNull()

    fun newId() = "custom-" + java.lang.Long.toString(System.currentTimeMillis(), 36)

    fun build(t: JSONObject): Skin {
        val base = SKINS.firstOrNull { it.id == t.s("base") } ?: SKINS[0]
        val acc = parse(t.s("accent")) ?: base.accent
        val c1 = parse(t.s("bg1")) ?: Color(0xFF0B1020)
        val c2 = parse(t.s("bg2")) ?: c1
        val style = runCatching { CardStyle.valueOf(t.s("style", base.style.name)) }.getOrDefault(base.style)
        val cover = t.s("cover").ifBlank { null }
        val bgType = t.s("bg", "base")
        val bg: Brush = when {
            bgType == "cover" && cover != null -> SolidColor(if (base.light) Color(0xFFDDE3EA) else Color.Black)
            bgType == "solid" -> SolidColor(c1)
            bgType == "gradient" -> Brush.linearGradient(listOf(c1, c2))
            else -> base.bg
        }
        val card: Brush = when (style) {
            CardStyle.GLASS -> if (base.light) Brush.linearGradient(listOf(Color.White.copy(.82f), Color.White.copy(.6f)))
                               else Brush.linearGradient(listOf(Color.White.copy(.16f), Color.White.copy(.05f), Color.White.copy(.08f)))
            else -> base.card
        }
        val onAcc = if (acc.luminance() > .5f) Color(0xFF111111) else Color.White
        val primary: Brush = if (style == CardStyle.GLOSS)
            Brush.verticalGradient(listOf(lerpColor(acc, Color.White, .45f), acc, lerpColor(acc, Color.Black, .2f), lerpColor(acc, Color.White, .2f)))
        else SolidColor(acc)
        return base.copy(id = t.s("id"), name = t.s("name", "Свой скин"), desc = "Свой · на основе «${base.name}»",
            bg = bg, card = card, accent = acc, onAccent = onAcc, primary = primary, style = style,
            radius = (t.optInt("radius", base.radius.value.toInt())).coerceIn(4, 36).dp,
            bgImage = if (bgType == "cover") cover else null,
            border = if (style == CardStyle.GLASS && !base.light) Color.White.copy(.18f) else base.border)
    }

    fun parse(hex: String?): Color? = runCatching {
        val h = hex!!.trim().removePrefix("#"); require(h.length == 6)
        Color(0xFF000000 or h.toLong(16))
    }.getOrNull()
    fun hex(c: Color) = "#%06X".format(c.toArgb() and 0xFFFFFF)
    private fun lerpColor(a: Color, b: Color, t: Float) = Color(a.red + (b.red - a.red) * t, a.green + (b.green - a.green) * t, a.blue + (b.blue - a.blue) * t, 1f)
}

private val SWATCHES = listOf(0xFF4FD1C5, 0xFF0A84FF, 0xFF5E5CE6, 0xFFBF5AF2, 0xFFFF375F, 0xFFFF453A, 0xFFFF9F0A,
    0xFFFFD60A, 0xFF30D158, 0xFF64D2FF, 0xFFE2552B, 0xFFF2F2F2, 0xFF8E8E93, 0xFF17171A).map { Color(it) }
private val BG_SWATCHES = listOf(0xFF0A0C0F, 0xFF0B1020, 0xFF1B1035, 0xFF2A2470, 0xFF0A2A5C, 0xFF02303A, 0xFF04402A,
    0xFF3A2410, 0xFF3D0F1E, 0xFF2F8FE8, 0xFFC9ECFF, 0xFFF4F3EF, 0xFFECECEC, 0xFF000000).map { Color(it) }

fun copyText(ctx: Context, text: String) {
    (ctx.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).setPrimaryClip(ClipData.newPlainText("TabDock", text))
}
fun pasteText(ctx: Context): String? =
    (ctx.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(ctx)?.toString()

/** Theme editor with a live preview. [id] null = new skin. */
@Composable
fun ThemeEditor(deck: Deck, all: JSONObject?, id: String?, onClose: () -> Unit) {
    val ctx = LocalContext.current
    val active = LocalSkin.current          // the skin on screen now (device choice or the computer's default)
    val start = remember(id) {
        val base = SKINS.firstOrNull { it.id == active.id } ?: Themes.recipe(active.id)?.let { r -> SKINS.firstOrNull { it.id == r.s("base") } } ?: SKINS[0]
        id?.let { Themes.recipe(it) }?.let { JSONObject(it.toString()) }
            ?: JSONObject().put("id", Themes.newId()).put("name", "Мой скин").put("base", base.id)
                .put("accent", Themes.hex(active.accent)).put("bg", "base").put("style", base.style.name).put("radius", base.radius.value.toInt())
    }
    var t by remember(id) { mutableStateOf(start) }
    var hexInput by remember(id) { mutableStateOf(t.s("accent")) }
    fun set(k: String, v: Any?) { t = JSONObject(t.toString()).put(k, v) }
    val preview = Themes.build(t)
    val s = LocalSkin.current
    val compact = LocalCompact.current
    val covers = all.o("shoots").a("items").objs().mapNotNull { sh -> sh.s("cover").ifBlank { null }?.let { sh.s("name") to it } }.take(12)

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Btn(if (compact) null else "Назад", "prev") { onClose() }
            Spacer(Modifier.width(12.dp))
            T(if (id == null) "Новый скин" else "Свой скин", 22.sp, weight = FontWeight.Bold, modifier = Modifier.weight(1f))
        }
        // live preview: the skin applied to a mini card
        ProvideSkin(preview) { ThemePreview(deck) }
        DeckCard("Название и основа") {
            TextInput(t.s("name"), { set("name", it.take(40)) }, "Название", Modifier.fillMaxWidth())
            T("Основа (тексты, светлая или тёмная):", 13.sp, s.muted, modifier = Modifier.padding(top = 10.dp, bottom = 6.dp))
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for (k in SKINS) Seg(k.name, t.s("base") == k.id) {
                    // a new base brings its own card style and corners; the accent and background stay
                    t = JSONObject(t.toString()).put("base", k.id).put("style", k.style.name).put("radius", k.radius.value.toInt())
                }
            }
        }
        DeckCard("Акцентный цвет") {
            Swatches(SWATCHES, Themes.parse(t.s("accent"))) { c -> set("accent", Themes.hex(c)); hexInput = Themes.hex(c) }
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 10.dp)) {
                TextInput(hexInput, { hexInput = it; Themes.parse(it)?.let { c -> set("accent", Themes.hex(c)) } }, "#4FD1C5", Modifier.width(160.dp))
                Spacer(Modifier.width(10.dp)); T("свой цвет в формате #RRGGBB", 13.sp, s.dim)
            }
        }
        DeckCard("Фон") {
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for ((k, n) in listOf("base" to "Как у основы", "solid" to "Цвет", "gradient" to "Градиент", "cover" to "Обложка съёмки")) Seg(n, t.s("bg", "base") == k) { set("bg", k) }
            }
            when (t.s("bg", "base")) {
                "solid" -> { Spacer(Modifier.height(10.dp)); Swatches(BG_SWATCHES, Themes.parse(t.s("bg1"))) { set("bg1", Themes.hex(it)) } }
                "gradient" -> {
                    T("Первый цвет", 13.sp, s.muted, modifier = Modifier.padding(top = 10.dp, bottom = 6.dp))
                    Swatches(BG_SWATCHES, Themes.parse(t.s("bg1"))) { set("bg1", Themes.hex(it)) }
                    T("Второй цвет", 13.sp, s.muted, modifier = Modifier.padding(top = 10.dp, bottom = 6.dp))
                    Swatches(BG_SWATCHES + SWATCHES, Themes.parse(t.s("bg2"))) { set("bg2", Themes.hex(it)) }
                }
                "cover" -> {
                    if (covers.isEmpty()) T("Обложек пока нет — они появятся, когда Capture One покажет кадры съёмок.", 13.sp, s.muted, modifier = Modifier.padding(top = 10.dp))
                    else Row(Modifier.horizontalScroll(rememberScrollState()).padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        for ((name, path) in covers) Column(Modifier.width(150.dp).clip(RoundedCornerShape(12.dp))
                            .border(3.dp, if (t.s("cover") == path) s.accent else Color.Transparent, RoundedCornerShape(12.dp)).clickable { set("cover", path) }) {
                            RemoteImage(deck, path, Modifier.fillMaxWidth().height(90.dp))
                            T(name, 12.sp, s.muted, maxLines = 1, modifier = Modifier.padding(6.dp))
                        }
                    }
                    T("Обложка ложится размытой подложкой под виджеты. Работает на этом компьютере (обложка берётся с него).", 12.sp, s.dim, modifier = Modifier.padding(top = 8.dp))
                }
            }
        }
        DeckCard("Карточки") {
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for ((k, n) in listOf("FLAT" to "Плоские", "GLASS" to "Стекло", "GLOSS" to "Глянец", "WINDOW" to "Окна Mac OS X")) Seg(n, t.s("style") == k) { set("style", k) }
            }
            T("Скругление углов", 13.sp, s.muted, modifier = Modifier.padding(top = 10.dp, bottom = 6.dp))
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for (r in listOf(6, 10, 16, 22, 28, 34)) Seg("$r", t.optInt("radius", 16) == r) { set("radius", r) }
            }
        }
        Actions {
            if (id != null) Btn("Удалить", danger = true) {
                Themes.delete(id); if (deck.skin.value == id) deck.setSkin(t.s("base", "classic")); onClose()
            }
            Btn("Скопировать для другого устройства", "link") { copyText(ctx, Themes.export(t)); deck.toast("Скопировано. Вставьте на другом устройстве: Настройки → Оформление → «Вставить скин»") }
            Btn("Сохранить и включить", primary = true) { Themes.save(t); deck.setSkin(t.s("id")); onClose() }
        }
        Spacer(Modifier.height(10.dp))
    }
}

@Composable private fun Swatches(colors: List<Color>, current: Color?, onPick: (Color) -> Unit) {
    val s = LocalSkin.current
    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        for (c in colors) Box(Modifier.size(38.dp).clip(CircleShape).background(c)
            .border(3.dp, if (current != null && Themes.hex(c) == Themes.hex(current)) s.text else s.border, CircleShape).clickable { onPick(c) })
    }
}

/** A tiny dock drawn with the skin being edited. */
@Composable private fun ThemePreview(deck: Deck) {
    val s = LocalSkin.current
    Box(Modifier.fillMaxWidth().height(210.dp).clip(RoundedCornerShape(18.dp)).background(s.bg)) {
        s.bgImage?.let { SkinBackground(deck, s) }
        Row(Modifier.fillMaxSize().padding(14.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            DeckCard("Напоминания", Modifier.weight(1f).fillMaxSize()) {
                T("Сдать галерею", 14.sp); T("завтра", 12.sp, s.muted)
                Spacer(Modifier.height(8.dp)); Bar(.6f, s.accent)
            }
            DeckCard("Музыка", Modifier.weight(1f).fillMaxSize()) {
                T("Ничего не играет", 14.sp); Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { Btn(icon = "prev") {}; Btn(icon = "play", primary = true) {} }
            }
        }
    }
}

/** Blurred shoot cover under the widgets (skins with a cover background). */
@Composable fun SkinBackground(deck: Deck, s: Skin) {
    val path = s.bgImage ?: return
    Box(Modifier.fillMaxSize()) {
        RemoteImage(deck, path, Modifier.fillMaxSize().blur(28.dp), transparentBg = true)
        Box(Modifier.fillMaxSize().background(if (s.light) Color.White.copy(.55f) else Color.Black.copy(.55f)))
    }
}
