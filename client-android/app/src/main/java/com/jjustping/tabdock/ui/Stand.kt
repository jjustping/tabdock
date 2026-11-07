package com.jjustping.tabdock.ui

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.res.Configuration
import android.os.BatteryManager
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
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
import java.util.Calendar

/** Is the device on a charger? (sticky broadcast, updates live) */
@Composable fun rememberCharging(): Boolean {
    val ctx = LocalContext.current
    var on by remember { mutableStateOf(isCharging(ctx.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED)))) }
    DisposableEffect(Unit) {
        val r = object : android.content.BroadcastReceiver() { override fun onReceive(c: Context?, i: Intent?) { on = isCharging(i) } }
        ctx.registerReceiver(r, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        onDispose { runCatching { ctx.unregisterReceiver(r) } }
    }
    return on
}
private fun isCharging(i: Intent?) = (i?.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) ?: 0) != 0

@Composable fun isLandscape() = LocalConfiguration.current.orientation == Configuration.ORIENTATION_LANDSCAPE

/**
 * "Подставка": a calm bedside / desk screen for a phone on a stand — big clock, weather, what's playing,
 * the nearest shoot deadline. The content drifts a few pixels every minute so OLED screens don't burn in.
 * Tap anywhere (except the player buttons) to go back to the dock.
 */
@Composable
fun StandScreen(c: Ctx, onExit: () -> Unit) {
    val s = LocalSkin.current
    val now by produceState(System.currentTimeMillis()) { while (true) { value = System.currentTimeMillis(); delay(1000L * (60 - Calendar.getInstance().get(Calendar.SECOND)).coerceAtLeast(1)) } }
    val cal = Calendar.getInstance().apply { timeInMillis = now }
    val minute = (now / 60000).toInt()
    val shift = listOf(0 to 0, 6 to -4, -5 to 5, 4 to 6, -6 to -3)[minute % 5]
    val w = c.all.o("weather"); val m = c.state.o("media").o("player")
    val land = isLandscape()
    val accent = s.accent
    val textMain = Color(0xFFEDEFF3); val textDim = Color(0xFF8D96A5)

    Box(Modifier.fillMaxSize().background(Color.Black).clickable { onExit() }) {
        val content: @Composable () -> Unit = {
            Column(horizontalAlignment = if (land) Alignment.Start else Alignment.CenterHorizontally) {
                T("${Fmt.pad(cal.get(Calendar.HOUR_OF_DAY))}:${Fmt.pad(cal.get(Calendar.MINUTE))}", if (land) 120.sp else 96.sp, textMain, FontWeight.Light)
                T(Fmt.DAYS[cal.get(Calendar.DAY_OF_WEEK) - 1].replaceFirstChar { it.uppercase() } + ", ${cal.get(Calendar.DAY_OF_MONTH)} ${Fmt.MON[cal.get(Calendar.MONTH)]}", 22.sp, textDim)
                if (w.d("temp") != null) Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 14.dp)) {
                    Ic(weatherIcon(w.i("code")), 30.dp, textMain); Spacer(Modifier.width(10.dp))
                    T("${w.d("temp")?.toInt()}°", 30.sp, textMain, FontWeight.SemiBold); Spacer(Modifier.width(10.dp))
                    T(w.s("text"), 18.sp, textDim, maxLines = 1)
                }
            }
            if (land) Spacer(Modifier.width(48.dp)) else Spacer(Modifier.height(36.dp))
            Column(Modifier.width(if (land) 330.dp else 320.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                // player
                val playing = m.s("state") == "playing"
                Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(Color.White.copy(.06f)).padding(16.dp)) {
                    T(if (m.s("title").isNotBlank()) m.s("title") else "Ничего не играет", 18.sp, textMain, FontWeight.SemiBold, maxLines = 1)
                    T(listOf(m.s("artist"), m.s("album")).filter { it.isNotBlank() }.joinToString(" · ").ifBlank { "Apple Music / Spotify" }, 14.sp, textDim, maxLines = 1)
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.padding(top = 12.dp)) {
                        for ((ic, cmd) in listOf("prev" to "previous", (if (playing) "pause" else "play") to "playpause", "next" to "next"))
                            Box(Modifier.size(54.dp, 44.dp).clip(RoundedCornerShape(14.dp)).background(if (cmd == "playpause") accent.copy(.9f) else Color.White.copy(.08f))
                                .clickable { c.deck.media(cmd) }, contentAlignment = Alignment.Center) { Ic(ic, 22.dp, if (cmd == "playpause") s.onAccent else textMain) }
                    }
                }
                // nearest deadline / work in progress
                val shoots = c.all.o("shoots").a("items").objs().filter { !it.b("hidden") && it.s("status") !in setOf("done", "delivered") }
                val next = shoots.filter { it.s("deadline").isNotBlank() }.minByOrNull { it.s("deadline") }
                Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(Color.White.copy(.06f)).padding(16.dp)) {
                    if (next != null) {
                        T("Ближайший срок · ${Fmt.due(next.s("deadline")).first}", 13.sp, accent, FontWeight.SemiBold)
                        T(next.s("name"), 18.sp, textMain, FontWeight.SemiBold, maxLines = 1)
                        T("${next.i("done")} из ${next.i("target").takeIf { it > 0 } ?: next.i("total")} ${next.s("done_label")}", 14.sp, textDim)
                    } else {
                        T("Съёмки", 13.sp, accent, FontWeight.SemiBold)
                        T(if (shoots.isEmpty()) "Всё сдано" else "В работе: ${shoots.size}", 18.sp, textMain, FontWeight.SemiBold)
                    }
                }
            }
        }
        Box(Modifier.fillMaxSize().padding(28.dp).offset(shift.first.dp, shift.second.dp), contentAlignment = Alignment.Center) {
            if (land) Row(verticalAlignment = Alignment.CenterVertically) { content() }
            else Column(horizontalAlignment = Alignment.CenterHorizontally) { content() }
        }
        T("Коснитесь, чтобы вернуться", 12.sp, Color(0xFF4A505B), modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 18.dp))
    }
}
