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
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jjustping.tabdock.data.a
import com.jjustping.tabdock.data.o
import com.jjustping.tabdock.data.objs
import com.jjustping.tabdock.data.s
import com.jjustping.tabdock.data.strs
import org.json.JSONArray
import org.json.JSONObject

/** Kinds of a custom button: id, name, hint for the value field. */
val BUTTON_KINDS = listOf(
    Triple("hotkey", "Сочетание клавиш", "Например cmd+shift+4, ctrl+alt+t, f5, space"),
    Triple("text", "Вставить текст", "Текст, который вставится в активное окно"),
    Triple("url", "Открыть сайт", "https://…"),
    Triple("folder", "Открыть папку", "~/Documents/Проекты"),
    Triple("app", "Открыть приложение", "Название, как в списке приложений"),
    Triple("command", "Команда / скрипт", "Apple Shortcut на Mac или скрипт из ~/.config/tabdock/commands на Linux"),
)
private val BUTTON_ICONS = listOf("star", "frame", "link", "folder", "app", "play", "note", "computer", "display", "cup",
    "moon", "check", "calendar", "book", "gear", "volume", "qr", "reset", "drive", "pencil")
private val BUTTON_COLORS = listOf("", "#4FD1C5", "#0A84FF", "#BF5AF2", "#FF375F", "#FF9F0A", "#30D158", "#8E8E93")

fun buttonsOf(c: Ctx) = c.all.o("config").a("buttons").objs()

/** «Свои кнопки» widget: big tiles, one tap = one action on the computer. Long-press opens the editor. */
@Composable fun ButtonsW(c: Ctx, w: JSONObject) {
    val all = buttonsOf(c)
    val ids = w.o("opts").a("ids").strs()
    val list = if (ids.isEmpty()) all else ids.mapNotNull { id -> all.firstOrNull { it.s("id") == id } }
    if (list.isEmpty()) { Empty("Своих кнопок пока нет — значок ⚙ выше"); return }
    Grid(list, if (LocalCompact.current) 3 else 4) { b ->
        val col = Themes.parse(b.s("color"))
        Box(Modifier.fillMaxWidth()) {
            Tile(b.s("icon", "star"), b.s("title"), Modifier.fillMaxWidth().heightIn(min = 84.dp)) { c.deck.action("button", b.s("id")) }
            if (col != null) Box(Modifier.align(Alignment.TopEnd).padding(6.dp).size(10.dp).clip(CircleShape).background(col))
        }
    }
}

/** Editor of all custom buttons (shared by every device of this computer). */
@Composable fun ButtonsEditor(c: Ctx, onClose: () -> Unit) {
    val s = LocalSkin.current
    var list by remember { mutableStateOf(buttonsOf(c).map { JSONObject(it.toString()) }) }
    var editing by remember { mutableStateOf<JSONObject?>(null) }
    fun save(next: List<JSONObject>) { list = next; c.deck.post("/api/config", JSONObject().put("buttons", JSONArray(next))) }

    editing?.let { e ->
        var title by remember(e) { mutableStateOf(e.s("title")) }
        var kind by remember(e) { mutableStateOf(e.s("kind", "hotkey")) }
        var value by remember(e) { mutableStateOf(e.s("value")) }
        var icon by remember(e) { mutableStateOf(e.s("icon", "star")) }
        var color by remember(e) { mutableStateOf(e.s("color")) }
        Sheet(if (list.any { it.s("id") == e.s("id") }) "Кнопка" else "Новая кнопка") {
            TextInput(title, { title = it.take(40) }, "Название на кнопке", Modifier.fillMaxWidth())
            T("Что делает", 13.sp, s.muted, modifier = Modifier.padding(top = 10.dp, bottom = 6.dp))
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for ((k, n, _) in BUTTON_KINDS) Seg(n, kind == k) { kind = k }
            }
            Spacer(Modifier.height(10.dp))
            TextInput(value, { value = it }, BUTTON_KINDS.first { it.first == kind }.third, Modifier.fillMaxWidth())
            if (kind == "hotkey") T("Клавиши через «+»: cmd/ctrl/alt/shift + буква, цифра, f1–f12, enter, space, стрелки. На Mac один раз нужно разрешить TabDock «Универсальный доступ».",
                12.sp, s.dim, modifier = Modifier.padding(top = 6.dp))
            T("Значок и цвет", 13.sp, s.muted, modifier = Modifier.padding(top = 12.dp, bottom = 6.dp))
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                for (ic in BUTTON_ICONS) Box(Modifier.size(44.dp).clip(RoundedCornerShape(12.dp)).background(s.inner)
                    .border(2.dp, if (ic == icon) s.accent else Color.Transparent, RoundedCornerShape(12.dp)).clickable { icon = ic },
                    contentAlignment = Alignment.Center) { Ic(ic, 22.dp) }
            }
            Row(Modifier.horizontalScroll(rememberScrollState()).padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for (col in BUTTON_COLORS) Box(Modifier.size(32.dp).clip(CircleShape).background(Themes.parse(col) ?: s.inner)
                    .border(3.dp, if (col == color) s.text else s.border, CircleShape).clickable { color = col },
                    contentAlignment = Alignment.Center) { if (col.isEmpty()) T("✕", 12.sp, s.muted) }
            }
            Actions {
                if (list.any { it.s("id") == e.s("id") }) Btn("Удалить", danger = true) { save(list.filter { it.s("id") != e.s("id") }); editing = null }
                Btn("Отмена") { editing = null }
                Btn("Сохранить", primary = true, enabled = title.isNotBlank() && value.isNotBlank()) {
                    val b = JSONObject().put("id", e.s("id")).put("title", title.trim()).put("kind", kind).put("value", value.trim())
                        .put("icon", icon).put("color", color)
                    save(if (list.any { it.s("id") == e.s("id") }) list.map { if (it.s("id") == e.s("id")) b else it } else list + b)
                    editing = null
                }
            }
        }
        return
    }

    Sheet("Свои кнопки") {
        T("Каждая кнопка делает одно действие на компьютере: нажимает сочетание клавиш, вставляет текст, открывает сайт, папку или приложение, запускает команду. Кнопки общие для всех устройств этого компьютера.",
            14.sp, s.muted)
        Spacer(Modifier.height(10.dp))
        if (list.isEmpty()) Empty("Пока пусто — добавьте первую кнопку")
        for ((i, b) in list.withIndex()) Row(Modifier.fillMaxWidth().padding(vertical = 4.dp).clip(RoundedCornerShape(12.dp)).background(s.inner)
            .clickable { editing = b }.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
            Ic(b.s("icon", "star"), 22.dp, Themes.parse(b.s("color")) ?: s.accent); Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                T(b.s("title"), 15.sp, weight = FontWeight.SemiBold, maxLines = 1)
                T(BUTTON_KINDS.firstOrNull { it.first == b.s("kind") }?.second.orEmpty() + " · " + b.s("value"), 12.sp, s.muted, maxLines = 1)
            }
            if (i > 0) Box(Modifier.size(36.dp).clickable { save(list.toMutableList().also { l -> val t = l[i]; l[i] = l[i - 1]; l[i - 1] = t }) },
                contentAlignment = Alignment.Center) { Ic("prev", 18.dp, s.muted) }
        }
        Actions {
            Btn("Закрыть") { onClose() }
            Btn("Добавить кнопку", "plus", primary = true, enabled = list.size < 48) {
                editing = JSONObject().put("id", java.lang.Long.toString(System.currentTimeMillis(), 36)).put("kind", "hotkey").put("icon", "star")
            }
        }
    }
}
