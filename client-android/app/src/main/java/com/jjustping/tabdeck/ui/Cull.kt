package com.jjustping.tabdeck.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
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
import com.jjustping.tabdeck.data.Deck
import com.jjustping.tabdeck.data.b
import com.jjustping.tabdeck.data.i
import com.jjustping.tabdeck.data.objs
import com.jjustping.tabdeck.data.s
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import java.net.URLEncoder

/** Capture One colour tags: index → colour (0 = none). */
val TAG_COLORS = listOf(Color.Transparent, Color(0xFFFF453A), Color(0xFFFF9F0A), Color(0xFFFFD60A), Color(0xFF30D158),
    Color(0xFF0A84FF), Color(0xFFFF6AC1), Color(0xFFBF5AF2))
val TAG_NAMES = listOf("без метки", "красная", "оранжевая", "жёлтая", "зелёная", "синяя", "розовая", "фиолетовая")

data class Frame(val img: Int, val name: String, val rating: Int, val color: Int, val exported: Boolean)

/** Culling: grid of frames → fullscreen viewer; stars and colour tags go to Capture One through the server. */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun CullScreen(deck: Deck, shoot: JSONObject, onClose: () -> Unit) {
    val s = LocalSkin.current
    val key = shoot.s("key")
    val ek = URLEncoder.encode(key, "UTF-8")
    val frames = remember { mutableStateListOf<Frame>() }
    var error by remember { mutableStateOf<String?>(null) }
    var filter by remember { mutableStateOf("all") }
    var viewer by remember { mutableStateOf<Int?>(null) }
    var viewIds by remember { mutableStateOf(listOf<Int>()) }
    var autoNext by remember { mutableStateOf(deck.store.string("cull_next") != "0") }
    val scope = rememberCoroutineScope()

    LaunchedEffect(key) {
        runCatching { deck.api!!.obj("/api/cull/images?key=$ek", 15000) }
            .onSuccess { r -> frames.clear(); frames.addAll(r.optJSONArray("images").objs().map { Frame(it.i("img"), it.s("name"), it.i("rating"), it.i("color"), it.b("exported")) }) }
            .onFailure { error = it.message }
    }
    val shown = frames.filter { f -> when (filter) {
        "none" -> f.rating == 0 && f.color == 0; "r1" -> f.rating >= 1; "r3" -> f.rating >= 3
        "notexp" -> !f.exported; else -> if (filter.startsWith("c")) f.color == filter.drop(1).toInt() else true } }

    fun apply(f: Frame, rating: Int? = null, color: Int? = null, advance: () -> Unit = {}) {
        val idx = frames.indexOfFirst { it.img == f.img }; if (idx < 0) return
        val old = frames[idx]
        val new = old.copy(rating = rating ?: old.rating, color = color ?: old.color)
        frames[idx] = new
        scope.launch {
            val body = JSONObject().put("key", key).put("changes", JSONArray().put(JSONObject().put("img", f.img)
                .apply { rating?.let { put("rating", it) }; color?.let { put("color", it) } }))
            val r = runCatching { deck.api!!.post("/api/cull/tag", body, 35000) }.getOrNull()
            if (r == null || !r.optBoolean("ok")) { frames[idx] = old; deck.toast(r?.optString("message") ?: "Нет связи с компьютером") }
        }
        if (autoNext) advance()
    }

    Column(Modifier.fillMaxSize()) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(bottom = 10.dp)) {
            val compact = LocalCompact.current
            Btn(if (compact) null else "Назад", "prev") { if (viewer != null) viewer = null else onClose() }
            Spacer(Modifier.width(if (compact) 10.dp else 14.dp))
            Column(Modifier.weight(1f)) {
                T(if (compact) shoot.s("name") else "Отбор · ${shoot.s("name")}", if (compact) 18.sp else 22.sp, weight = FontWeight.Bold, maxLines = 1)
                T("${frames.size} кадров · ★ ${frames.count { it.rating > 0 }} · с меткой ${frames.count { it.color > 0 }} · экспорт ${frames.count { it.exported }}", 13.sp, s.muted)
            }
            Seg(if (compact) "Авто ▸" else "Автопереход", autoNext) { autoNext = !autoNext; deck.store.put("cull_next", if (autoNext) "1" else "0") }
        }
        if (viewer == null) {
            Row(Modifier.horizontalScroll(rememberScrollState()).padding(bottom = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for ((k, n) in listOf("all" to "Все", "none" to "Без оценки", "r1" to "★1+", "r3" to "★3+", "notexp" to "Не экспортированы")) Seg(n, filter == k) { filter = k }
                for (ci in 1..7) Box(Modifier.size(40.dp).clip(CircleShape).background(TAG_COLORS[ci])
                    .border(3.dp, if (filter == "c$ci") s.text else Color.Transparent, CircleShape).clickable { filter = if (filter == "c$ci") "all" else "c$ci" })
            }
            error?.let { T(it, 15.sp, s.red) }
            LazyVerticalGrid(GridCells.Adaptive(if (LocalCompact.current) 150.dp else 180.dp), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                itemsIndexed(shown, key = { _, f -> f.img }) { i, f ->
                    Column(Modifier.clip(RoundedCornerShape(12.dp)).background(s.inner).clickable { viewIds = shown.map { it.img }; viewer = i }) {
                        Box(Modifier.fillMaxWidth().aspectRatio(1.5f)) {
                            RemoteImage(deck, "/api/cull/thumb?key=$ek&img=${f.img}", Modifier.fillMaxSize())
                            if (f.color > 0) Box(Modifier.align(Alignment.TopStart).padding(8.dp).size(16.dp).clip(CircleShape).background(TAG_COLORS[f.color]).border(2.dp, Color.White, CircleShape))
                            if (f.exported) Box(Modifier.align(Alignment.TopEnd).padding(6.dp).clip(RoundedCornerShape(6.dp)).background(Color.Black.copy(.55f)).padding(3.dp)) { Ic("check", 14.dp, Color.White) }
                        }
                        Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
                            T(f.name.substringBeforeLast('.'), 12.sp, s.muted, modifier = Modifier.weight(1f), maxLines = 1)
                            // on phones the grid stars are display-only: they are too small and too easy to hit while scrolling
                            if (LocalCompact.current) Stars(f.rating, 12, null) else Stars(f.rating, 13) { r -> apply(f, rating = if (r == f.rating) 0 else r) }
                        }
                    }
                }
            }
        } else {
            val list = viewIds.mapNotNull { id -> frames.firstOrNull { it.img == id } }
            val pager = rememberPagerState(initialPage = viewer!!.coerceIn(0, (list.size - 1).coerceAtLeast(0))) { list.size }
            Column(Modifier.fillMaxSize()) {
                HorizontalPager(pager, Modifier.weight(1f).fillMaxWidth(), key = { list[it].img }) { p ->
                    val f = list[p]
                    Box(Modifier.fillMaxSize().clip(RoundedCornerShape(14.dp)).background(Color.Black)) {
                        RemoteImage(deck, "/api/cull/thumb?key=$ek&img=${f.img}", Modifier.fillMaxSize(), crop = false, transparentBg = true)
                        RemoteImage(deck, "/api/cull/preview?key=$ek&img=${f.img}", Modifier.fillMaxSize(), crop = false, transparentBg = true)
                    }
                }
                val f = list.getOrNull(pager.currentPage)
                if (f != null) {
                    val next: () -> Unit = { scope.launch { if (pager.currentPage < list.size - 1) pager.animateScrollToPage(pager.currentPage + 1) } }
                    val compact = LocalCompact.current
                    val info: @Composable () -> Unit = {
                        T(f.name, 16.sp, weight = FontWeight.SemiBold, maxLines = 1)
                        T("${pager.currentPage + 1} из ${list.size}" + if (f.exported) " · экспортирован" else "", 13.sp, s.muted)
                    }
                    if (compact) Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) { info() }
                        Stars(f.rating, 26) { r -> apply(f, rating = if (r == f.rating) 0 else r, advance = next) }
                    }
                    Row(Modifier.fillMaxWidth().padding(top = if (compact) 8.dp else 10.dp), verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = if (compact) Arrangement.SpaceBetween else Arrangement.Start) {
                        if (!compact) {
                            Column(Modifier.width(220.dp)) { info() }
                            Stars(f.rating, 34) { r -> apply(f, rating = if (r == f.rating) 0 else r, advance = next) }
                            Spacer(Modifier.width(24.dp))
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(if (compact) 6.dp else 8.dp)) {
                            for (ci in 0..7) Box(Modifier.size(if (compact) 38.dp else 42.dp).clip(CircleShape).background(if (ci == 0) s.inner else TAG_COLORS[ci])
                                .border(3.dp, if (f.color == ci) s.text else Color.Transparent, CircleShape)
                                .clickable { apply(f, color = if (f.color == ci) 0 else ci, advance = next) }, contentAlignment = Alignment.Center) {
                                if (ci == 0) T("✕", 15.sp, s.muted)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable fun Stars(rating: Int, size: Int, onSet: ((Int) -> Unit)?) {
    val s = LocalSkin.current
    Row {
        for (r in 1..5) Box(Modifier.size((size + 8).dp).let { m -> if (onSet != null) m.clickable { onSet(r) } else m }, contentAlignment = Alignment.Center) {
            T("★", size.sp, if (r <= rating) s.amber else s.dim.copy(.5f))
        }
    }
}
