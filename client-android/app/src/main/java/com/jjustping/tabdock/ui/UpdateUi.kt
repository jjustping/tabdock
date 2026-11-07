package com.jjustping.tabdock.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jjustping.tabdock.BuildConfigShim
import com.jjustping.tabdock.data.AppUpdate
import com.jjustping.tabdock.data.Deck
import com.jjustping.tabdock.data.Updater
import kotlinx.coroutines.launch

/** «Доступна новая версия»: what changed + download and install the APK (or open the release page). */
@Composable
fun UpdateDialog(deck: Deck, u: AppUpdate, onClose: () -> Unit) {
    val s = LocalSkin.current
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var progress by remember { mutableStateOf<Float?>(null) }
    var msg by remember { mutableStateOf("") }
    Box(Modifier.fillMaxSize().background(Color.Black.copy(.55f)), contentAlignment = Alignment.Center) {
        DeckCard("Доступна новая версия", Modifier.widthIn(max = 640.dp).fillMaxWidth(.94f), pad = 20.dp) {
            T("TabDock ${u.version}", 22.sp, weight = FontWeight.Bold)
            T("У вас ${BuildConfigShim.VERSION}. Компьютер тоже стоит обновить — в меню значка TabDock или в панели в браузере.", 14.sp, s.muted)
            if (u.notes.isNotBlank()) Column(Modifier.padding(top = 12.dp).fillMaxWidth().heightIn(max = 320.dp).clip(RoundedCornerShape(12.dp))
                .background(s.inner).verticalScroll(rememberScrollState()).padding(12.dp)) {
                for (line in u.notes.lines()) {
                    val l = line.trimEnd()
                    when {
                        l.isBlank() -> {}
                        l.startsWith("## ") -> T(l.removePrefix("## "), 16.sp, weight = FontWeight.SemiBold, modifier = Modifier.padding(top = 6.dp))
                        else -> T(l.replace("**", "").replace("`", "").removePrefix("* ").let { if (line.startsWith("* ")) "• $it" else it }, 14.sp,
                            if (line.startsWith("  ")) s.muted else s.text)
                    }
                }
            }
            progress?.let { p -> T(if (p < 1f) "Скачиваю… ${(p * 100).toInt()}%" else "Скачано — открываю установку", 14.sp, s.muted, modifier = Modifier.padding(top = 10.dp)) }
            if (msg.isNotBlank()) T(msg, 14.sp, s.red, modifier = Modifier.padding(top = 10.dp))
            Row(Modifier.fillMaxWidth().padding(top = 14.dp), horizontalArrangement = Arrangement.spacedBy(10.dp, Alignment.End)) {
                Btn("Позже") { deck.store.put("update_skip", u.version); onClose() }
                if (u.page != null) Btn("Что нового") { Updater.openPage(ctx, u.page) }
                Btn("Обновить", primary = true, enabled = progress == null) {
                    if (u.apk == null) { u.page?.let { Updater.openPage(ctx, it) }; return@Btn }
                    if (!Updater.canInstall(ctx)) { msg = "Разрешите TabDock устанавливать приложения и нажмите «Обновить» ещё раз"; Updater.askInstallPermission(ctx); return@Btn }
                    scope.launch {
                        progress = 0f; msg = ""
                        runCatching { Updater.download(ctx, u) { p -> progress = p } }
                            .onSuccess { progress = 1f; Updater.install(ctx, it) }
                            .onFailure { progress = null; msg = "Не скачалось (${it.message}). Можно скачать вручную: «Что нового»." }
                    }
                }
            }
        }
    }
}
