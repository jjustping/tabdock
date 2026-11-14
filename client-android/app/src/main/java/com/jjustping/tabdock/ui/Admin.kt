package com.jjustping.tabdock.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
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
import com.jjustping.tabdock.data.a
import com.jjustping.tabdock.data.b
import com.jjustping.tabdock.data.d
import com.jjustping.tabdock.data.i
import com.jjustping.tabdock.data.o
import com.jjustping.tabdock.data.objs
import com.jjustping.tabdock.data.s
import com.jjustping.tabdock.data.strs
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

// ---------------- 0.14: for admins and developers ----------------

private fun ago(ts: Double?): String {
    if (ts == null || ts <= 0) return ""
    val s = (System.currentTimeMillis() / 1000.0 - ts).toLong().coerceAtLeast(0)
    return when { s < 60 -> "сейчас"; s < 3600 -> "${s / 60} мин назад"; s < 86400 -> "${s / 3600} ч назад"; else -> "${s / 86400} дн назад" }
}

private fun isoTs(iso: String): Double? = runCatching { java.time.Instant.parse(iso).epochSecond.toDouble() }.getOrNull()

@Composable private fun Dot(ok: Boolean?, ) {
    val s = LocalSkin.current
    Box(Modifier.size(10.dp).clip(CircleShape).background(when (ok) { true -> s.green; false -> s.red; null -> s.amber }))
}

@Composable private fun AdminRow(ok: Boolean?, title: String, sub: String, onClick: (() -> Unit)? = null, trailing: @Composable () -> Unit = {}) {
    val s = LocalSkin.current
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).let { m -> if (onClick != null) m.clickable(onClick = onClick) else m }
        .padding(vertical = 6.dp, horizontal = 2.dp), verticalAlignment = Alignment.CenterVertically) {
        Dot(ok); Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            T(title, 15.sp, weight = FontWeight.SemiBold, maxLines = 1)
            if (sub.isNotBlank()) T(sub, 13.sp, s.muted, maxLines = 1)
        }
        trailing()
    }
}

private fun admin(c: Ctx) = c.state.o("admin")
private fun cfgList(c: Ctx, key: String) = c.all.o("config").a(key).objs()

/** «Хосты»: devices and services on the network, with Wake-on-LAN. */
@Composable fun HostsW(c: Ctx) {
    val s = LocalSkin.current
    val hosts = cfgList(c, "hosts")
    if (hosts.isEmpty()) { Empty("Добавьте роутер, NAS или сервер — значок ⚙ выше"); return }
    val st = admin(c).o("hosts")
    Column(Modifier.verticalScroll(rememberScrollState())) {
        for (h in hosts) {
            val r = st.o(h.s("id"))
            val up = r?.let { it.b("up") }
            val sub = when {
                r == null -> "проверяю…"
                up == true -> (r.d("ms")?.let { "${it.toInt()} мс · " } ?: "") + "работает " + ago(r.d("since")).removeSuffix(" назад").let { if (it == "сейчас") "" else it }
                else -> (r.s("err").ifBlank { "не отвечает" }) + " · " + ago(r.d("since"))
            }
            AdminRow(up, h.s("name"), sub.trimEnd(' ', '·')) {
                if (h.s("mac").isNotBlank()) Box(Modifier.clip(RoundedCornerShape(10.dp)).background(s.inner)
                    .clickable { c.deck.action("wol", h.s("id")) }.padding(horizontal = 10.dp, vertical = 6.dp)) { T("Разбудить", 13.sp, s.accent) }
            }
        }
    }
}

/** «Бэкапы»: when each backup last ran; red when it is older than allowed. */
@Composable fun BackupsW(c: Ctx) {
    val list = cfgList(c, "backups")
    if (list.isEmpty()) { Empty("Добавьте Time Machine или папку бэкапа — значок ⚙ выше"); return }
    val st = admin(c).o("backups")
    for (b in list) {
        val r = st.o(b.s("id"))
        AdminRow(r?.b("ok"), b.s("name"), when {
            r == null -> "проверяю…"
            r.s("err").isNotBlank() -> r.s("err")
            else -> "последний " + ago(r.d("at")) + if (!r.b("ok")) " · дольше ${b.i("hours")} ч" else ""
        })
    }
}

/** «Docker»: containers, start / stop / restart, the last lines of the log. */
@Composable fun DockerW(c: Ctx) {
    val s = LocalSkin.current
    val d = admin(c).o("docker")
    var open by remember { mutableStateOf<String?>(null) }
    var logs by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    when {
        d == null -> { Empty("Проверяю Docker…"); return }
        !d.b("installed") -> { Empty("Docker на компьютере не найден"); return }
        d.s("error").isNotBlank() -> { Empty(d.s("error")); return }
    }
    val list = d.a("containers").objs()
    if (list.isEmpty()) { Empty("Контейнеров нет"); return }
    Column(Modifier.verticalScroll(rememberScrollState())) {
        for (ct in list) {
            val name = ct.s("name"); val running = ct.s("state") == "running"
            AdminRow(if (running) true else if (ct.s("state") in setOf("restarting", "paused")) null else false, name,
                ct.s("status") + " · " + ct.s("image"), onClick = { open = if (open == name) null else name; logs = null })
            if (open == name) {
                Row(Modifier.horizontalScroll(rememberScrollState()).padding(start = 20.dp, bottom = 6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (!running) Seg("Запустить", false) { c.deck.post("/api/action", JSONObject().put("action", "docker").put("arg", name).put("op", "start"), refresh = false) }
                    if (running) Seg("Перезапустить", false) { c.deck.post("/api/action", JSONObject().put("action", "docker").put("arg", name).put("op", "restart"), refresh = false) }
                    if (running) Seg("Остановить", false) { c.deck.post("/api/action", JSONObject().put("action", "docker").put("arg", name).put("op", "stop"), refresh = false) }
                    Seg("Журнал", logs != null) {
                        if (logs != null) logs = null
                        else scope.launch { logs = runCatching { c.deck.api!!.obj("/api/docker/logs?name=" + java.net.URLEncoder.encode(name, "UTF-8"), 15000).s("text") }.getOrElse { "Не получилось: ${it.message}" } }
                    }
                }
                logs?.let { text ->
                    Box(Modifier.fillMaxWidth().heightIn(max = 260.dp).clip(RoundedCornerShape(10.dp)).background(Color.Black.copy(.35f))
                        .verticalScroll(rememberScrollState(Int.MAX_VALUE)).padding(10.dp)) {
                        T(text.ifBlank { "Журнал пуст" }, 11.sp, s.text, mono = true)
                    }
                }
            }
        }
    }
}

/** «Сборки»: the last GitHub Actions run of each repository. */
@Composable fun CiW(c: Ctx) {
    val ctx = LocalContext.current
    val repos = c.all.o("config").a("gh_repos").strs()
    if (repos.isEmpty()) { Empty("Добавьте репозитории GitHub — значок ⚙ выше"); return }
    val st = admin(c).o("ci")
    for (r in repos) {
        val x = st.o(r)
        val state = x.s("state")
        val ok = when (state) { "success" -> true; "failure", "timed_out", "startup_failure", "error" -> false; else -> null }
        val word = when (state) {
            "success" -> "прошла"; "failure" -> "упала"; "cancelled" -> "отменена"; "in_progress" -> "идёт"; "queued", "waiting", "pending" -> "в очереди"
            "none" -> "сборок нет"; "error" -> x.s("err"); "" -> "проверяю…"; else -> state
        }
        AdminRow(ok, r, listOf(x.s("workflow"), word, x.s("branch"), ago(isoTs(x.s("at")))).filter { it.isNotBlank() }.joinToString(" · "),
            onClick = x.s("url").takeIf { it.startsWith("https://github.com/") }?.let { u -> {
                runCatching { ctx.startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(u)).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)) }
                Unit
            } })
    }
}

/** «Git»: branch, changes, ahead / behind for local repositories; fetch and pull. */
@Composable fun GitW(c: Ctx) {
    val repos = cfgList(c, "repos")
    if (repos.isEmpty()) { Empty("Добавьте папки с репозиториями — значок ⚙ выше"); return }
    val st = admin(c).o("repos")
    var open by remember { mutableStateOf<String?>(null) }
    Column(Modifier.verticalScroll(rememberScrollState())) {
        for (r in repos) {
            val x = st.o(r.s("id"))
            val err = x.s("error")
            val sub = if (err.isNotBlank()) err else listOfNotNull(
                x.s("branch").ifBlank { null },
                x.i("changes").takeIf { it > 0 }?.let { "изменений: $it" },
                x.i("ahead").takeIf { it > 0 }?.let { "↑$it" }, x.i("behind").takeIf { it > 0 }?.let { "↓$it" },
                x.s("last").ifBlank { null }).joinToString(" · ")
            AdminRow(if (err.isNotBlank()) false else if (x.i("behind") > 0 || x.i("changes") > 0) null else if (x == null) null else true,
                r.s("name"), if (x == null) "проверяю…" else sub, onClick = { open = if (open == r.s("id")) null else r.s("id") })
            if (open == r.s("id")) Row(Modifier.padding(start = 20.dp, bottom = 6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Seg("Проверить сервер (fetch)", false) { c.deck.post("/api/action", JSONObject().put("action", "git").put("arg", r.s("id")).put("op", "fetch"), refresh = false) }
                Seg("Подтянуть (pull)", false) { c.deck.post("/api/action", JSONObject().put("action", "git").put("arg", r.s("id")).put("op", "pull"), refresh = false) }
            }
        }
    }
}

/** Disk health lines under «Диски» (SMART). */
@Composable fun SmartLines(c: Ctx) {
    val s = LocalSkin.current
    val list = admin(c).a("smart").objs()
    if (list.isEmpty()) return
    T("Здоровье дисков", 13.sp, s.muted, modifier = Modifier.padding(top = 8.dp, bottom = 2.dp))
    for (d in list) AdminRow(when (d.s("status")) { "ok" -> true; "failing" -> false; else -> null }, d.s("name"),
        d.s("raw") + (d.d("temp")?.let { " · ${it.toInt()}°" } ?: ""))
}

// ---------------- settings of these widgets (shared by all devices of the computer) ----------------
private val ADMIN_SETTINGS = mapOf(
    "hosts" to "Хосты", "backups" to "Бэкапы", "git" to "Git-репозитории", "ci" to "Сборки GitHub")

@Composable fun AdminEditor(c: Ctx, type: String, onClose: () -> Unit) {
    val s = LocalSkin.current
    val key = when (type) { "git" -> "repos"; "ci" -> "gh_repos"; else -> type }
    var items by remember {
        mutableStateOf(if (type == "ci") c.all.o("config").a("gh_repos").strs().map { JSONObject().put("repo", it) }
                       else cfgList(c, key).map { JSONObject(it.toString()) })
    }
    var ver by remember { mutableStateOf(0) }
    fun set(i: Int, k: String, v: Any) { items[i].put(k, v); ver++ }
    fun blank(): JSONObject = when (type) {
        "hosts" -> JSONObject().put("kind", "ping").put("name", "").put("target", "").put("mac", "")
        "backups" -> JSONObject().put("kind", "path").put("name", "").put("path", "").put("hours", 26)
        "git" -> JSONObject().put("name", "").put("path", "")
        else -> JSONObject().put("repo", "")
    }
    Sheet(ADMIN_SETTINGS[type] ?: "Настройки") {
        T(when (type) {
            "hosts" -> "Что проверять: ping — адрес или имя, HTTP — ссылка (ответ ниже 500 = работает), порт — адрес:порт. MAC-адрес — чтобы будить устройство по сети (Wake-on-LAN). Когда хост пропадает или появляется, приходит уведомление."
            "backups" -> "Time Machine (только Mac) или файл/папка, которые обновляет ваш бэкап (лог rsync, папка с копиями). Красным — если последний бэкап старше указанного числа часов."
            "git" -> "Папки с git-репозиториями на компьютере, например ~/code/tabdock. Видно ветку, изменения, ↑ не отправлено, ↓ можно подтянуть."
            else -> "Репозитории GitHub вида владелец/название. Закрытые — с токеном в файле ~/.config/tabdock/github-token на компьютере."
        }, 13.sp, s.muted)
        @Suppress("UNUSED_EXPRESSION") ver
        for ((i, it) in items.withIndex()) Column(Modifier.fillMaxWidth().padding(top = 10.dp).clip(RoundedCornerShape(12.dp)).background(s.inner).padding(10.dp)) {
            when (type) {
                "hosts" -> {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        for ((k, n) in listOf("ping" to "Ping", "http" to "HTTP", "tcp" to "Порт")) Seg(n, it.s("kind") == k) { set(i, "kind", k) }
                    }
                    Spacer(Modifier.size(6.dp))
                    TextInput(it.s("name"), { v -> set(i, "name", v.take(40)) }, "Название, например NAS", Modifier.fillMaxWidth())
                    TextInput(it.s("target"), { v -> set(i, "target", v.trim()) }, when (it.s("kind")) { "http" -> "https://nas.local:5001"; "tcp" -> "nas.local:22"; else -> "192.168.1.10 или nas.local" }, Modifier.fillMaxWidth().padding(top = 6.dp))
                    TextInput(it.s("mac"), { v -> set(i, "mac", v.trim()) }, "MAC для пробуждения (необязательно), aa:bb:cc:dd:ee:ff", Modifier.fillMaxWidth().padding(top = 6.dp))
                }
                "backups" -> {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Seg("Файл или папка", it.s("kind") != "timemachine") { set(i, "kind", "path") }
                        if (c.all.s("platform") == "darwin") Seg("Time Machine", it.s("kind") == "timemachine") { set(i, "kind", "timemachine") }
                    }
                    Spacer(Modifier.size(6.dp))
                    TextInput(it.s("name"), { v -> set(i, "name", v.take(40)) }, "Название", Modifier.fillMaxWidth())
                    if (it.s("kind") != "timemachine") TextInput(it.s("path"), { v -> set(i, "path", v) }, "~/backups/last.log или /mnt/backup", Modifier.fillMaxWidth().padding(top = 6.dp))
                    TextInput(it.i("hours", 26).toString(), { v -> set(i, "hours", v.filter(Char::isDigit).take(4).toIntOrNull() ?: 26) }, "Не старше, часов", Modifier.fillMaxWidth().padding(top = 6.dp))
                }
                "git" -> {
                    TextInput(it.s("name"), { v -> set(i, "name", v.take(40)) }, "Название (необязательно)", Modifier.fillMaxWidth())
                    TextInput(it.s("path"), { v -> set(i, "path", v) }, "~/code/project", Modifier.fillMaxWidth().padding(top = 6.dp))
                }
                else -> TextInput(it.s("repo"), { v -> set(i, "repo", v.trim()) }, "владелец/репозиторий", Modifier.fillMaxWidth())
            }
            Row(Modifier.padding(top = 6.dp)) { Spacer(Modifier.weight(1f)); Link("Убрать") { items = items.filterIndexed { j, _ -> j != i }; ver++ } }
        }
        Actions {
            Btn("Добавить", "plus") { items = items + blank() }
            Btn("Отмена") { onClose() }
            Btn("Сохранить", primary = true) {
                val body = if (type == "ci") JSONArray(items.map { it.s("repo") }.filter { it.isNotBlank() })
                           else JSONArray(items.filter { x -> (x.s("target") + x.s("path")).isNotBlank() || x.s("kind") == "timemachine" })
                c.deck.post("/api/config", JSONObject().put(key, body))
                onClose()
            }
        }
    }
}
