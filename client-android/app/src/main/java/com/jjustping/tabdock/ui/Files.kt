package com.jjustping.tabdock.ui

import android.content.Intent
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jjustping.tabdock.data.Files
import com.jjustping.tabdock.data.Fmt
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** «Файлы»: send files to the computer, open what came from it, and the history of both directions. */
@Composable fun FilesScreen(c: Ctx) {
    val s = LocalSkin.current
    val ctx = LocalContext.current
    val history by c.deck.transfers.list.collectAsState()
    val sending by c.deck.sending.collectAsState()
    val pick = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris: List<Uri> ->
        if (uris.isEmpty()) return@rememberLauncherForActivityResult
        // keep the right to read them, so they can be opened from the history later
        for (u in uris) runCatching { ctx.contentResolver.takePersistableUriPermission(u, Intent.FLAG_GRANT_READ_URI_PERMISSION) }
        c.deck.sendFiles(uris)
    }
    val compact = LocalCompact.current
    LazyColumn(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            DeckCard("Передача файлов") {
                T("Файлы с компьютера приходят в «Загрузки → TabDock» на этом устройстве. На компьютере: значок TabDock → «Передача файлов…».",
                    14.sp, s.muted)
                Spacer(Modifier.size(12.dp))
                val send: @Composable (Modifier) -> Unit = { m -> Btn("Отправить на компьютер", "transfer", primary = true, modifier = m, enabled = sending == null) { pick.launch(arrayOf("*/*")) } }
                val folder: @Composable (Modifier) -> Unit = { m -> Btn("Открыть папку", "folder", modifier = m) { Files.openFolder(ctx) } }
                if (compact) Column(verticalArrangement = Arrangement.spacedBy(8.dp)) { send(Modifier.fillMaxWidth()); folder(Modifier.fillMaxWidth()) }
                else Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) { send(Modifier); folder(Modifier) }
                sending?.let { T("Отправляю $it…", 14.sp, s.accent, modifier = Modifier.padding(top = 10.dp), maxLines = 1) }
                T("Из любого приложения: «Поделиться» → TabDock.", 12.sp, s.dim, modifier = Modifier.padding(top = 10.dp))
            }
        }
        item {
            Row(Modifier.fillMaxWidth().padding(top = 4.dp, start = 4.dp, end = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                T("История", 17.sp, weight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                if (history.isNotEmpty()) T("Очистить", 14.sp, s.muted, modifier = Modifier.clip(RoundedCornerShape(8.dp))
                    .clickable { c.deck.transfers.clear() }.padding(horizontal = 8.dp, vertical = 4.dp))
            }
        }
        if (history.isEmpty()) item { Empty("Пока ничего не передавали") }
        items(history, key = { it.optLong("at").toString() + it.optString("name") + it.optString("dir") }) { it ->
            val inc = it.optString("dir") == "in"
            val name = it.optString("name")
            val uri = it.optString("uri").takeIf { u -> u.isNotBlank() }?.let(Uri::parse)
            Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(s.inner).border(1.dp, s.border, RoundedCornerShape(14.dp))
                .clickable {
                    if (uri == null || !Files.open(ctx, uri, name)) c.deck.toast("Файл «$name» больше недоступен — его удалили или переместили")
                }.padding(horizontal = 12.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                T(if (inc) "↓" else "↑", 20.sp, if (inc) s.green else s.accent, FontWeight.Bold)
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    T(name, 15.sp, weight = FontWeight.SemiBold, maxLines = 1)
                    val size = it.optLong("size", -1).takeIf { n -> n >= 0 }?.let { n -> Fmt.bytes(n.toDouble()) + " · " } ?: ""
                    T((if (inc) "с компьютера" else "на компьютер") + " · " + size + when_(it.optLong("at")), 12.sp, s.muted, maxLines = 1)
                }
                if (inc) Box(Modifier.size(40.dp).clip(RoundedCornerShape(12.dp)).clickable { Files.openFolder(ctx) }, contentAlignment = Alignment.Center) {
                    Ic("folder", 22.dp, s.muted)
                }
            }
        }
    }
}

private fun when_(t: Long): String {
    if (t <= 0) return ""
    val d = Date(t); val today = SimpleDateFormat("yyyyMMdd", Locale.ROOT).let { it.format(d) == it.format(Date()) }
    return SimpleDateFormat(if (today) "сегодня HH:mm" else "d MMM, HH:mm", Locale("ru")).format(d)
}
