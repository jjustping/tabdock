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
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.graphics.ColorMatrix
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jjustping.tabdock.data.Deck
import com.jjustping.tabdock.data.a
import com.jjustping.tabdock.data.b
import com.jjustping.tabdock.data.objs
import com.jjustping.tabdock.data.s
import kotlinx.coroutines.delay
import org.json.JSONObject
import java.net.URLEncoder

private fun refImg(rel: String, size: String) = "/api/refs/img?size=$size&rel=" + URLEncoder.encode(rel, "UTF-8")

/** «Референсы» widget: the newest pictures of the folder on the computer; a tap opens the viewer. */
@Composable fun RefsW(c: Ctx) {
    val s = LocalSkin.current
    val data by produceState<JSONObject?>(null, c.all) { value = runCatching { c.deck.api!!.obj("/api/refs") }.getOrNull() }
    val d = data ?: return
    val items = d.a("items").objs()
    if (items.isEmpty()) {
        T(if (d.b("exists")) "Папка пуста — положите в неё картинки на компьютере" else "Картинки берутся из папки на компьютере: «Изображения → TabDock Референсы». Подпапки — отдельные доски.",
            14.sp, s.muted)
        Spacer(Modifier.height(10.dp))
        Btn("Открыть папку на компьютере", "folder") { c.deck.action("open_refs") }
        return
    }
    Grid(items.take(if (LocalCompact.current) 6 else 8), if (LocalCompact.current) 3 else 4) { f ->
        RemoteImage(c.deck, refImg(f.s("rel"), "thumb"), Modifier.fillMaxWidth().aspectRatio(1f).clip(RoundedCornerShape(10.dp))
            .clickable { c.openRefs(f.s("rel")) })
    }
}

/** Main colours of a picture, most common first, without near-duplicates (for the palette under the reference). */
fun palette(img: ImageBitmap, count: Int = 6): List<Int> {
    val src = img.asAndroidBitmap()
    val small = android.graphics.Bitmap.createScaledBitmap(src.copy(android.graphics.Bitmap.Config.ARGB_8888, false), 48, 48, true)
    val buckets = HashMap<Int, IntArray>()           // 4 bits per channel → [n, r, g, b]
    for (y in 0 until small.height) for (x in 0 until small.width) {
        val p = small.getPixel(x, y)
        val r = (p shr 16) and 255; val g = (p shr 8) and 255; val b = p and 255
        val k = ((r shr 4) shl 8) or ((g shr 4) shl 4) or (b shr 4)
        val acc = buckets.getOrPut(k) { IntArray(4) }
        acc[0]++; acc[1] += r; acc[2] += g; acc[3] += b
    }
    val out = ArrayList<Int>()
    val minShare = small.width * small.height / 80          // edges of shapes blend colours: skip the rare ones
    for (acc in buckets.values.sortedByDescending { it[0] }) {
        if (acc[0] < minShare && out.size >= 3) break
        val r = acc[1] / acc[0]; val g = acc[2] / acc[0]; val b = acc[3] / acc[0]
        if (out.none { o -> val dr = ((o shr 16) and 255) - r; val dg = ((o shr 8) and 255) - g; val db = (o and 255) - b; dr * dr + dg * dg + db * db < 2400 })
            out += (r shl 16) or (g shl 8) or b
        if (out.size >= count) break
    }
    return out
}

private fun hex(c: Int) = "#%06X".format(c and 0xFFFFFF)

/** Full-screen reference viewer: zoom, mirror, black and white, the gesture-drawing timer and the palette. */
@Composable fun RefsScreen(deck: Deck, start: String, onClose: () -> Unit) {
    val s = LocalSkin.current
    val data by produceState<JSONObject?>(null) { value = runCatching { deck.api!!.obj("/api/refs") }.getOrNull() }
    var board by remember { mutableStateOf<String?>(null) }
    var rel by remember { mutableStateOf(start) }
    var flip by remember { mutableStateOf(false) }
    var gray by remember { mutableStateOf(false) }
    var timer by remember { mutableIntStateOf(0) }           // seconds per picture, 0 = off
    var left by remember { mutableIntStateOf(0) }
    var shuffle by remember { mutableStateOf(false) }
    val all = data?.a("items")?.objs().orEmpty()
    val list = all.filter { board == null || it.s("board") == board }
    fun step(dir: Int) {
        if (list.isEmpty()) return
        val i = list.indexOfFirst { it.s("rel") == rel }
        rel = if (shuffle && list.size > 1) list.filter { it.s("rel") != rel }.random().s("rel")
              else list[((if (i < 0) 0 else i) + dir + list.size) % list.size].s("rel")
    }
    // gesture drawing: every picture stays for the chosen time, then the next one comes by itself
    LaunchedEffect(timer, rel) {
        if (timer <= 0) return@LaunchedEffect
        left = timer
        while (left > 0) { delay(1000); left-- }
        step(1)
    }
    val thumb = refImg(rel, "thumb")
    val colors by produceState(emptyList<Int>(), rel) {
        var img: ImageBitmap? = null
        for (i in 0 until 10) { img = deck.cached(thumb) ?: deck.image(thumb); if (img != null) break; delay(300) }
        value = img?.let { runCatching { palette(it) }.getOrDefault(emptyList()) } ?: emptyList()
    }
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Btn("Закрыть", "prev") { onClose() }
            val boards = data?.a("boards")?.objs().orEmpty()
            if (boards.isNotEmpty()) {
                Seg("Все", board == null) { board = null }
                for (b in boards) Seg(b.s("name"), board == b.s("name")) {
                    board = b.s("name"); all.firstOrNull { it.s("board") == board }?.let { rel = it.s("rel") }
                }
            }
        }
        Box(Modifier.weight(1f).fillMaxWidth().padding(vertical = 10.dp)) {
            val bw = remember { ColorFilter.colorMatrix(ColorMatrix().apply { setToSaturation(0f) }) }
            ZoomablePhoto(deck, thumb, refImg(rel, "view"), null, isCurrent = true, filter = if (gray) bw else null, flip = flip) {}
            if (timer > 0) Box(Modifier.align(Alignment.TopEnd).padding(12.dp).clip(RoundedCornerShape(12.dp)).background(Color.Black.copy(.6f))
                .padding(horizontal = 14.dp, vertical = 6.dp)) {
                T("%d:%02d".format(left / 60, left % 60), 28.sp, Color.White, FontWeight.Bold)
            }
        }
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Btn(icon = "prev") { step(-1) }
            Btn(icon = "next") { step(1) }
            Seg("Отразить", flip) { flip = !flip }
            Seg("Ч/Б", gray) { gray = !gray }
            Seg("Вперемешку", shuffle) { shuffle = !shuffle }
            Spacer(Modifier.width(6.dp))
            T("Таймер", 13.sp, s.muted)
            for ((sec, label) in listOf(0 to "выкл", 30 to "30 с", 60 to "1 мин", 120 to "2 мин", 300 to "5 мин", 600 to "10 мин"))
                Seg(label, timer == sec) { timer = sec }
        }
        if (colors.isNotEmpty()) Row(Modifier.fillMaxWidth().padding(top = 10.dp).horizontalScroll(rememberScrollState()),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            T("Палитра — касание копирует цвет на компьютер:", 13.sp, s.muted)
            for (col in colors) Row(Modifier.clip(RoundedCornerShape(10.dp)).background(s.inner).clickable { deck.action("copy_color", hex(col)) }
                .padding(horizontal = 8.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(26.dp).clip(CircleShape).background(Color(0xFF000000.toInt() or col)).border(1.dp, s.border, CircleShape))
                Spacer(Modifier.width(6.dp))
                T(hex(col), 13.sp, weight = FontWeight.SemiBold)
            }
        }
    }
}
