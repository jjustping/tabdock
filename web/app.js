/* TabDock — tablet UI (vanilla JS, no build step) */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let S = { state: {}, reminders: [], notes: [], shoots: { items: [] }, weather: {}, calendar: {}, config: {}, apps: [] };
let noteFilter = "";
let showDone = false;
let offline = false;

// ---------------- api ----------------
async function api(path, body) {
  const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, opt);
  if (r.status === 401) { location.reload(); throw new Error("401"); }
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}
function setOffline(v) {
  if (v && !offlineSince) offlineSince = Date.now();
  if (!v) offlineSince = 0;
  if (v !== offline) { offline = v; $("#offline").classList.toggle("hidden", !v); if (!v) $("#offline").textContent = "Нет связи с Mac — переподключаюсь…"; }
  if (v) tryFailover();
}

async function loadAll() {
  try { S = await api("/api/all"); setOffline(false); renderAll(); }
  catch (e) { setOffline(true); }
}
async function loadState() {
  try { S.state = await api("/api/state"); setOffline(false); renderLive(); }
  catch (e) { setOffline(true); }
}

function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.add("show");
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 2200);
}

// ---------------- formatting ----------------
const RU_DAYS = ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"];
const RU_MON = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
const RU_DS = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"];
const pad = (n) => String(n).padStart(2, "0");
function fmtBytes(b) { if (b == null) return "—"; const u = ["Б", "КБ", "МБ", "ГБ", "ТБ"]; let i = 0; while (b >= 1000 && i < 4) { b /= 1000; i++; } return (b >= 100 || i === 0 ? b.toFixed(0) : b.toFixed(1)) + " " + u[i]; }
function fmtDate(ts) { if (!ts) return ""; const d = new Date(ts * 1000); return d.getDate() + " " + RU_MON[d.getMonth()] + (d.getFullYear() !== new Date().getFullYear() ? " " + d.getFullYear() : ""); }
function fmtUptime(s) { const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60); return (d ? d + " д " : "") + h + " ч " + m + " мин"; }
function fmtDur(s) { if (s == null) return ""; s = Math.max(0, Math.round(s)); return Math.floor(s / 60) + ":" + pad(s % 60); }
function todayStr(off = 0) { const d = new Date(Date.now() + off * 864e5); return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); }
function dueLabel(due) {
  if (!due) return null;
  const t = todayStr(), tm = todayStr(1);
  if (due < t) return { cls: "over", txt: "просрочено · " + due.slice(8) + "." + due.slice(5, 7) };
  if (due === t) return { cls: "today", txt: "сегодня" };
  if (due === tm) return { cls: "", txt: "завтра" };
  const d = new Date(due + "T12:00"); return { cls: "", txt: RU_DS[d.getDay()] + ", " + d.getDate() + " " + RU_MON[d.getMonth()] };
}
function md(src) {
  const lines = esc(src || "").split("\n"); let html = "", inList = false;
  const inline = (s) => s.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`(.+?)`/g, "<code>$1</code>")
    .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
  for (const l of lines) {
    if (/^\s*[-•]\s+/.test(l)) { if (!inList) { html += "<ul>"; inList = true; } html += "<li>" + inline(l.replace(/^\s*[-•]\s+/, "")) + "</li>"; continue; }
    if (inList) { html += "</ul>"; inList = false; }
    if (l.trim()) html += "<p>" + inline(l) + "</p>";
  }
  if (inList) html += "</ul>";
  return html;
}
const STATUS = { new: "Не начато", selecting: "Отбор", editing: "В работе", done: "Готово", delivered: "Сдано" };

// ---------------- sheet ----------------
function openSheet(html, onMount) {
  $("#sheetBody").innerHTML = html; $("#sheet").classList.remove("hidden");
  if (onMount) onMount($("#sheetBody"));
}
function closeSheet() { $("#sheet").classList.add("hidden"); $("#sheetBody").innerHTML = ""; }
$("#sheet").addEventListener("click", (e) => { if (e.target.id === "sheet") closeSheet(); });

// double-tap confirm for dangerous actions (like on DJ-Pi)
function armed(el, fn) {
  if (el.classList.contains("armed")) { el.classList.remove("armed"); clearTimeout(el._t); fn(); return; }
  $$(".armed").forEach((x) => x.classList.remove("armed"));
  el.classList.add("armed"); toast("Нажмите ещё раз для подтверждения");
  el._t = setTimeout(() => el.classList.remove("armed"), 3000);
}

// ---------------- tabs ----------------
function showTab(name) {
  $$(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $$(".view").forEach((v) => v.classList.toggle("active", v.dataset.view === name));
  localStorage.setItem("dock_tab", name);
  renderAll();
}
document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-tab]");
  if (t) showTab(t.dataset.tab);
});

// ---------------- render: top ----------------
function renderClock() {
  const d = new Date();
  $("#time").textContent = pad(d.getHours()) + ":" + pad(d.getMinutes());
  $("#date").textContent = RU_DAYS[d.getDay()][0].toUpperCase() + RU_DAYS[d.getDay()].slice(1) + ", " + d.getDate() + " " + RU_MON[d.getMonth()];
}
function renderTop() {
  const s = S.state.sys || {}, w = S.weather || {};
  $("#weatherChip").innerHTML = w.temp != null
    ? `${w.icon} <b>${Math.round(w.temp)}°</b> <span class="muted">${esc(w.text)} · ${esc(w.place || "")}</span>`
    : `<span class="muted">${w.configured === false ? "☁︎ Город для погоды — в Настройках" : "☁︎ Погода…"}</span>`;
  const t = s.temp || {}, m = s.mem || {};
  const root = (s.disks || []).find((d) => !d.external);
  const cls = (v, w1, w2) => v == null ? "" : v >= w2 ? "hot" : v >= w1 ? "warn" : "";
  $("#topStats").innerHTML = `
    <div class="stat ${cls(s.cpu, 70, 90)}"><small>CPU</small><b>${s.cpu != null ? Math.round(s.cpu) + "%" : "—"}</b></div>
    <div class="stat ${cls(t.cpu, 75, 90)}"><small>Темп.</small><b>${t.cpu != null ? Math.round(t.cpu) + "°" : "—"}</b></div>
    <div class="stat ${cls(m.pct, 80, 92)}"><small>Память</small><b>${m.pct != null ? Math.round(m.pct) + "%" : "—"}</b></div>
    <div class="stat ${cls(root && root.pct, 85, 95)}"><small>Диск</small><b>${root ? fmtBytes(root.free) : "—"}</b></div>`;
  $("#awakeBtn").classList.toggle("on", !!S.state.awake);
}

// ---------------- render: reminders ----------------
function remindersSorted() {
  const items = S.reminders || [];
  const open = items.filter((i) => !i.done).sort((a, b) => (b.important - a.important) || ((a.due || "9999") < (b.due || "9999") ? -1 : (a.due || "9999") > (b.due || "9999") ? 1 : 0) || b.created - a.created);
  const done = items.filter((i) => i.done).sort((a, b) => (b.done_at || 0) - (a.done_at || 0));
  return { open, done };
}
function remRow(r) {
  const due = dueLabel(r.due);
  return `<div class="rem ${r.done ? "done" : ""}" data-id="${r.id}">
    <button class="check" data-act="toggle">✓</button>
    <div class="txt" data-act="edit">${esc(r.text)}
      ${due || r.list ? `<div class="meta">${due ? `<span class="tag due ${due.cls}">${due.txt}</span>` : ""}${r.list ? `<span class="tag">${esc(r.list)}</span>` : ""}</div>` : ""}
    </div>
    ${r.important ? '<span class="star">★</span>' : ""}
  </div>`;
}
function renderReminders() {
  const { open, done } = remindersSorted();
  const el = $("#remindersCard");
  const keep = document.activeElement && document.activeElement.id === "remInput" ? $("#remInput").value : null;
  el.innerHTML = `<h2>Напоминания <span class="count">${open.length || ""}</span>
      <button class="act" id="remDoneBtn">${done.length ? (showDone ? "Скрыть выполненные" : "Выполненные · " + done.length) : ""}</button></h2>
    <form class="add-row" id="remForm"><input type="text" id="remInput" placeholder="Новое напоминание…" autocomplete="off" enterkeyhint="done">
      <button class="btn sq" type="button" id="remMore" title="Дата и важность">📅</button>
      <button class="btn primary sq" type="submit">+</button></form>
    <div class="list">${open.map(remRow).join("") || '<div class="empty">Всё сделано ✨</div>'}
      ${showDone && done.length ? `<div class="day-h">Выполненные</div>${done.map(remRow).join("")}
        <div style="text-align:center;padding:10px"><button class="btn danger" id="remClear">Очистить выполненные</button></div>` : ""}</div>`;
  if (keep !== null) { const i = $("#remInput"); i.value = keep; i.focus(); }
  $("#remForm").onsubmit = async (e) => {
    e.preventDefault(); const text = $("#remInput").value.trim(); if (!text) return;
    $("#remInput").value = "";
    const r = await api("/api/reminders", { op: "add", text }); S.reminders = r.reminders; renderReminders();
  };
  $("#remMore").onclick = () => editReminder(null, $("#remInput").value);
  $("#remDoneBtn").onclick = () => { showDone = !showDone; renderReminders(); };
  const clr = $("#remClear"); if (clr) clr.onclick = (e) => armed(e.target, async () => { const r = await api("/api/reminders", { op: "clear_done" }); S.reminders = r.reminders; renderReminders(); });
  $$(".rem", el).forEach((row) => {
    row.onclick = async (e) => {
      const act = e.target.closest("[data-act]"); if (!act) return;
      const id = row.dataset.id;
      if (act.dataset.act === "toggle") {
        row.classList.toggle("done");
        const r = await api("/api/reminders", { op: "toggle", id }); S.reminders = r.reminders;
        setTimeout(renderReminders, 350);
      } else editReminder(S.reminders.find((x) => x.id === id));
    };
  });
}
function editReminder(r, presetText) {
  const isNew = !r; r = r || { text: presetText || "", due: "", important: false, list: "" };
  const lists = [...new Set((S.reminders || []).map((x) => x.list).filter(Boolean))];
  openSheet(`<h3>${isNew ? "Новое напоминание" : "Напоминание"}</h3>
    <div class="field"><input type="text" id="rText" value="${esc(r.text)}" placeholder="Что сделать?"></div>
    <div class="field"><label>Срок</label><div class="seg" id="rDueSeg">
      <button data-d="">Без срока</button><button data-d="${todayStr()}">Сегодня</button><button data-d="${todayStr(1)}">Завтра</button>
      <button data-d="${todayStr(7)}">Через неделю</button></div>
      <input type="date" id="rDue" value="${esc(r.due || "")}" style="margin-top:8px"></div>
    <div class="field"><label>Список / тег</label><input type="text" id="rList" value="${esc(r.list || "")}" placeholder="например: Фото, Дом, Диджеинг" list="rLists">
      <datalist id="rLists">${lists.map((l) => `<option value="${esc(l)}">`).join("")}</datalist></div>
    <div class="field"><div class="seg"><button id="rImp" class="${r.important ? "on" : ""}">★ Важное</button></div></div>
    <div class="actions-row">${isNew ? "" : '<button class="btn danger left" id="rDel">Удалить</button>'}
      <button class="btn" id="rCancel">Отмена</button><button class="btn primary" id="rSave">Сохранить</button></div>`, (b) => {
    const syncSeg = () => $$("#rDueSeg button", b).forEach((x) => x.classList.toggle("on", x.dataset.d === $("#rDue").value));
    syncSeg();
    $$("#rDueSeg button", b).forEach((x) => x.onclick = () => { $("#rDue").value = x.dataset.d; syncSeg(); });
    $("#rDue").onchange = syncSeg;
    $("#rImp").onclick = (e) => e.target.classList.toggle("on");
    $("#rCancel").onclick = closeSheet;
    if (!isNew) $("#rDel").onclick = (e) => armed(e.target, async () => { const x = await api("/api/reminders", { op: "delete", id: r.id }); S.reminders = x.reminders; closeSheet(); renderReminders(); });
    $("#rSave").onclick = async () => {
      const body = { text: $("#rText").value.trim(), due: $("#rDue").value || null, list: $("#rList").value.trim(), important: $("#rImp").classList.contains("on") };
      if (!body.text) return;
      const x = await api("/api/reminders", isNew ? { op: "add", ...body } : { op: "edit", id: r.id, ...body });
      S.reminders = x.reminders; if (isNew) $("#remInput") && ($("#remInput").value = ""); closeSheet(); renderReminders();
    };
    if (isNew) setTimeout(() => $("#rText").focus(), 50);
  });
}

// ---------------- render: shoots ----------------
function shootSub(s) {
  const parts = [];
  if (s.shot_from) parts.push(fmtDate(s.shot_from));
  if (s.source === "manual") parts.push("вручную");
  else parts.push(s.done + " из " + s.target + (s.target_manual ? " (цель)" : s.picked ? " отобранных" : " кадров") + " экспортировано");
  if (s.deadline) parts.push("срок " + s.deadline.slice(8) + "." + s.deadline.slice(5, 7));
  return parts.join(" · ");
}
function barCls(s) { return s.status === "done" || s.status === "delivered" ? "done" : s.status === "selecting" ? "sel" : ""; }
function renderShootsCard() {
  const items = (S.shoots.items || []).filter((s) => !s.hidden);
  const todo = items.filter((s) => s.status !== "done" && s.status !== "delivered");
  const frames = todo.reduce((a, s) => a + Math.max(0, s.target - s.done), 0);
  const top = items.slice(0, 3);
  $("#shootsCard").innerHTML = `<h2>Съёмки · Capture One <button class="act" data-tab="shoots">Все →</button></h2>
    <div class="shoots-summary">
      <div class="sum"><b>${todo.length}</b><small>в работе / ждут</small></div>
      <div class="sum"><b>${frames}</b><small>кадров осталось</small></div>
      <div class="sum"><b>${items.length - todo.length}</b><small>готово</small></div></div>
    ${wfolioAlert()}
    ${top.map((s) => `<div class="shoot" data-key="${esc(s.key)}">
        <div class="cover" style="${s.cover ? `background-image:url('${s.cover}')` : ""}"></div>
        <div class="info"><div class="name">${esc(s.name)}</div>
          <div class="sub"><span class="st ${s.status}">${STATUS[s.status] || s.status}</span> ${esc(shootSub(s))}</div>
          <div class="bar ${barCls(s)}"><i style="width:${Math.round(s.progress * 100)}%"></i></div></div>
        <div class="pct">${Math.round(s.progress * 100)}%</div></div>`).join("") || '<div class="empty">Каталог Capture One не найден</div>'}`;
  $$("#shootsCard .shoot").forEach((r) => r.onclick = () => editShoot(r.dataset.key));
}
function renderShootsView() {
  const sh = S.shoots || {}, items = sh.items || [];
  const errs = (sh.errors || []).map((e) => `<div class="card" style="border-color:var(--red)">⚠️ ${esc(e.catalog)}: ${esc(e.error)}</div>`).join("");
  $("#shootsView").innerHTML = `<div class="toolbar"><h2 style="margin:0;font-size:24px">Съёмки</h2><div class="spacer"></div>
      <span class="muted" style="font-size:14px">${(sh.catalogs || []).length} каталог(а) · обновляется автоматически</span>
      <button class="btn" id="shAdd">+ Съёмка вручную</button></div>${errs}
    <div class="shoot-grid">${items.map((s) => `<div class="shoot-card ${s.hidden ? "hidden-shoot" : ""}" data-key="${esc(s.key)}">
      <div class="cover" style="${s.cover ? `background-image:url('${s.cover}')` : ""}"></div><span class="st st-float ${s.status}">${STATUS[s.status]}</span>
      <div class="body"><div class="row" style="align-items:flex-start"><div style="flex:1;min-width:0">
        <div class="name" style="font-size:19px;font-weight:650">${esc(s.name)}</div>
        <div class="sub muted" style="font-size:13px;margin-top:3px">${esc([s.catalog_name, s.camera, s.client].filter(Boolean).join(" · "))}</div></div>
        <div class="pct" style="font-size:26px;width:auto">${Math.round(s.progress * 100)}%</div></div>
        <div class="bar ${barCls(s)}"><i style="width:${Math.round(s.progress * 100)}%"></i></div>
        <div class="nums">${s.source === "manual" ? `<span><b>${s.done}</b> / ${s.target} готово</span>` :
          `<span><b>${s.total}</b> кадров</span><span><b>${s.picked}</b> отобрано</span><span><b>${s.exported}</b> экспорт</span>`}
          ${s.deadline ? `<span>срок <b>${s.deadline.slice(8)}.${s.deadline.slice(5, 7)}</b></span>` : ""}</div>
        ${galleryFor(s.key) ? `<div class="hint"><span class="tag due ${gDays(galleryFor(s.key)).cls}">wfolio · ${esc(gDays(galleryFor(s.key)).txt)}</span></div>` : ""}
        ${s.note ? `<div class="hint" style="color:var(--muted)">${esc(s.note)}</div>` : ""}
      </div></div>`).join("")}</div>
    <p class="hint">Как считается прогресс: съёмка = альбом в каталоге Capture One. «Экспорт» — кадры, у которых есть запись в истории процессинга (вывода).
      Цель — отобранные кадры (★ или цветная метка), если они есть, иначе все кадры; цель и статус можно задать вручную, нажав на съёмку.</p>
    <div id="wfolioSec">${wfolioSection()}</div>`;
  bindWfolio($("#shootsView"));
  if (/[?&]scroll=wfolio/.test(location.search) && !renderShootsView._scrolled) { renderShootsView._scrolled = true; $("#wfolioSec").scrollIntoView(); }
  $$(".shoot-card").forEach((c) => c.onclick = () => editShoot(c.dataset.key));
  $("#shAdd").onclick = () => addManualShoot();
}
function editShoot(key) {
  const s = (S.shoots.items || []).find((x) => x.key === key); if (!s) return;
  const manual = s.source === "manual";
  openSheet(`<h3>${esc(s.name)}</h3>
    <div class="field"><label>Статус ${s.status_manual ? "(задан вручную)" : "(автоматически: " + STATUS[s.status_auto] + ")"}</label>
      <div class="seg" id="sSeg"><button data-s="">Авто</button>${Object.keys(STATUS).map((k) => `<button data-s="${k}">${STATUS[k]}</button>`).join("")}</div></div>
    <div class="row">
      <div class="field"><label>Цель, кадров ${manual ? "" : "(пусто = " + (s.picked || s.total) + ")"}</label><input type="number" id="sTarget" inputmode="numeric" value="${s.target_manual || manual ? s.target : ""}"></div>
      ${manual ? `<div class="field"><label>Готово, кадров</label><input type="number" id="sDone" inputmode="numeric" value="${s.done}"></div>` : ""}
      <div class="field"><label>Срок сдачи</label><input type="date" id="sDeadline" value="${esc(s.deadline || "")}"></div></div>
    <div class="field"><label>Клиент</label><input type="text" id="sClient" value="${esc(s.client)}"></div>
    <div class="field"><label>Заметка</label><input type="text" id="sNote" value="${esc(s.note)}" placeholder="что осталось, пожелания клиента…"></div>
    ${galleryFor(s.key) ? `<div class="hint" style="color:var(--text)">🔗 wfolio: ${esc(gTitle(galleryFor(s.key)))} · ${esc(gDays(galleryFor(s.key)).txt)}</div>` : ""}
    ${manual ? "" : `<div class="hint">${s.total} кадров · ${s.picked} отобрано · ${s.exported} экспортировано${s.last_export ? " · последний экспорт " + fmtDate(s.last_export) : ""} · каталог ${esc(s.catalog_name)}</div>`}
    <div class="actions-row">
      ${manual ? '<button class="btn danger left" id="sDel">Удалить</button>' : `<button class="btn left" id="sHide">${s.hidden ? "Показать" : "Скрыть"}</button><button class="btn" id="sOpen">Открыть в Capture One</button>`}
      <button class="btn" id="sCancel">Отмена</button><button class="btn primary" id="sSave">Сохранить</button></div>`, (b) => {
    let st = s.status_manual ? s.status : "";
    const sync = () => $$("#sSeg button", b).forEach((x) => x.classList.toggle("on", x.dataset.s === st));
    sync(); $$("#sSeg button", b).forEach((x) => x.onclick = () => { st = x.dataset.s; sync(); });
    $("#sCancel").onclick = closeSheet;
    const save = async (extra) => {
      const body = { op: "set", key, status: st || null, target: parseInt($("#sTarget").value) || null,
        deadline: $("#sDeadline").value || null, client: $("#sClient").value.trim(), note: $("#sNote").value.trim(), ...extra };
      if (manual) body.done = parseInt($("#sDone").value) || 0;
      const r = await api("/api/shoots", body); S.shoots = r.shoots; closeSheet(); renderAll();
    };
    $("#sSave").onclick = () => save({});
    if (manual) $("#sDel").onclick = (e) => armed(e.target, async () => { const r = await api("/api/shoots", { op: "delete", key }); S.shoots = r.shoots; closeSheet(); renderAll(); });
    else {
      $("#sHide").onclick = () => save({ hidden: !s.hidden });
      $("#sOpen").onclick = async () => { const r = await api("/api/action", { action: "open_shoot", catalog: s.catalog }); toast(r.message); };
    }
  });
}
function addManualShoot() {
  openSheet(`<h3>Съёмка вручную</h3><div class="hint" style="margin:-8px 0 14px">Для съёмок вне каталога (сессии, другой компьютер). Прогресс — вручную.</div>
    <div class="field"><label>Название</label><input type="text" id="mName"></div>
    <div class="row"><div class="field"><label>Сколько кадров сдать</label><input type="number" id="mTarget" inputmode="numeric"></div>
    <div class="field"><label>Срок</label><input type="date" id="mDeadline"></div></div>
    <div class="actions-row"><button class="btn" id="mCancel">Отмена</button><button class="btn primary" id="mSave">Добавить</button></div>`, () => {
    $("#mCancel").onclick = closeSheet;
    $("#mSave").onclick = async () => {
      const name = $("#mName").value.trim(); if (!name) return;
      const r = await api("/api/shoots", { op: "add", name, target: parseInt($("#mTarget").value) || 0, deadline: $("#mDeadline").value || null });
      S.shoots = r.shoots; closeSheet(); renderAll();
    };
    setTimeout(() => $("#mName").focus(), 50);
  });
}

// ---------------- render: calendar + weather ----------------
function renderCalendar() {
  const c = S.calendar || {}, w = S.weather || {};
  const fc = (w.days || []).slice(0, 4).map((d, i) => {
    const dt = new Date(d.date + "T12:00");
    return `<div class="d">${i === 0 ? "сегодня" : RU_DS[dt.getDay()]}<b>${d.icon}</b>${Math.round(d.max)}° <span class="dim">${Math.round(d.min)}°</span>${d.rain ? `<div class="dim">💧${d.rain}%</div>` : ""}</div>`;
  }).join("");
  let evHtml = "";
  if (!c.ok) {
    evHtml = c.error === "disabled" ? '<div class="empty">Календарь выключен в Настройках</div>'
      : c.error === "loading" ? '<div class="empty">Загружаю события…</div>'
      : c.error === "timeout" ? '<div class="empty">Календарь не ответил.<br><span class="hint">Возможно, на Mac ждёт окно «разрешить доступ к Календарю» — нажмите «Разрешить».</span></div>'
      : `<div class="empty">Нет доступа к Календарю macOS.<br><span class="hint">Разрешите доступ на Mac: Системные настройки → Конфиденциальность → Календари (см. README).</span></div>`;
  } else {
    const groups = {};
    for (const e of c.events || []) {
      const d = e.start.slice(0, 10);
      (groups[d] = groups[d] || []).push(e);
    }
    const now = Date.now();
    const days = Object.keys(groups).sort();
    evHtml = days.map((d) => `<div class="day-h">${d === todayStr() ? "Сегодня" : d === todayStr(1) ? "Завтра" : d}</div>` + groups[d].map((e) => {
      const st = new Date(e.start), en = new Date(e.end);
      const past = en.getTime() < now;
      return `<div class="ev" style="${past ? "opacity:.45" : ""}"><div class="tm">${e.allDay ? "весь день" : pad(st.getHours()) + ":" + pad(st.getMinutes())}</div>
        <div class="dot" style="background:${esc(e.color)}"></div><div class="tt">${esc(e.title)}<small>${esc([e.calendar, e.location].filter(Boolean).join(" · "))}</small></div></div>`;
    }).join("")).join("") || '<div class="empty">Сегодня и завтра событий нет</div>';
  }
  $("#calendarCard").innerHTML = `<h2>Погода и календарь</h2>${fc ? `<div class="forecast">${fc}</div>` : ""}<div class="list">${evHtml}</div>`;
}

// ---------------- render: player ----------------
let volDragging = false;
function renderPlayer() {
  const m = S.state.media || {}, p = m.player;
  const el = $("#playerCard");
  if (volDragging) return;
  const vol = m.volume;
  el.innerHTML = `<h2>Сейчас играет ${p ? `<span class="dim" style="text-transform:none;letter-spacing:0">· ${esc(p.app)}</span>` : ""}</h2>
    <div class="player"><div class="art" style="${p && p.art ? `background-image:url('${esc(p.art)}')` : ""}">${p && p.art ? "" : "♪"}</div>
      <div class="meta"><div class="t">${p ? esc(p.title) : "Ничего не играет"}</div><div class="a">${p ? esc([p.artist, p.album].filter(Boolean).join(" — ")) : "Apple Music / Spotify"}</div>
      ${p && p.duration ? `<div class="progress-line"><i style="width:${Math.min(100, 100 * p.position / p.duration)}%"></i></div><div class="dim" style="font-size:12px;margin-top:4px">${fmtDur(p.position)} / ${fmtDur(p.duration)}</div>` : ""}</div></div>
    <div class="ctrls"><button class="btn" data-m="previous">⏮</button><button class="btn play" data-m="playpause">${p && p.state === "playing" ? "⏸" : "▶"}</button><button class="btn" data-m="next">⏭</button>
      <button class="btn" data-m="mute">${m.muted ? "🔇" : "🔊"}</button></div>
    <div class="vol">${vol == null ? '<span class="dim" style="font-size:13px">Громкость этого выхода нельзя менять программно</span>' :
      `<input type="range" min="0" max="100" value="${vol}" id="volRange" style="--p:${vol}%"><span class="v" id="volV">${vol}</span>`}</div>`;
  $$("[data-m]", el).forEach((b) => b.onclick = async () => { const r = await api("/api/media", { cmd: b.dataset.m }); S.state.media = r.media; renderPlayer(); });
  const vr = $("#volRange");
  if (vr) {
    let t;
    vr.addEventListener("pointerdown", () => volDragging = true);
    const end = () => { setTimeout(() => volDragging = false, 600); };
    vr.addEventListener("pointerup", end); vr.addEventListener("pointercancel", end);
    vr.oninput = () => {
      vr.style.setProperty("--p", vr.value + "%"); $("#volV").textContent = vr.value;
      clearTimeout(t); t = setTimeout(() => api("/api/media", { cmd: "volume", value: +vr.value }), 120);
    };
  }
}

// ---------------- render: quick actions ----------------
const SYS_TILES = [
  { a: "awake", ic: "☕", t: "Не спать" },
  { a: "screenshot", ic: "⌗", t: "Скриншот" },
  { a: "display_sleep", ic: "◐", t: "Экран выкл." },
  { a: "sleep", ic: "⏾", t: "Сон", confirm: true },
];
async function doAction(action, arg) {
  try { const r = await api("/api/action", { action, arg }); toast(r.message || (r.ok ? "Готово" : "Не получилось")); if ("awake" in r) { S.state.awake = r.awake; renderTop(); renderQuick(); } }
  catch (e) { toast("Ошибка: " + e.message); }
}
function appTile(a) {
  return `<button class="tile" data-app="${esc(a.name)}" ${a.installed ? "" : 'style="opacity:.35"'}><img src="/api/app_icon?name=${encodeURIComponent(a.name)}" onerror="this.outerHTML='<span class=ic>▢</span>'" alt="">${esc(a.name)}</button>`;
}
function renderQuick() {
  const apps = (S.apps || []).filter((a) => a.installed).slice(0, 8);
  $("#quickCard").innerHTML = `<h2>Быстрые действия <button class="act" data-tab="settings">Изменить</button></h2>
    <div class="tiles">${apps.map(appTile).join("")}
    ${SYS_TILES.map((t) => `<button class="tile ${t.a === "awake" && S.state.awake ? "on" : ""}" data-sys="${t.a}" ${t.confirm ? 'data-confirm="1"' : ""}><span class="ic">${t.ic}</span>${t.t}</button>`).join("")}</div>`;
  bindTiles($("#quickCard"));
}
function bindTiles(root) {
  $$("[data-app]", root).forEach((b) => b.onclick = () => doAction("open_app", b.dataset.app));
  $$("[data-sys]", root).forEach((b) => b.onclick = () => b.dataset.confirm ? armed(b, () => doAction(b.dataset.sys)) : doAction(b.dataset.sys));
  $$("[data-folder]", root).forEach((b) => b.onclick = () => doAction("open_path", b.dataset.folder));
}

// ---------------- render: mac ----------------
function spark(vals, w = 300, h = 60) {
  if (!vals || vals.length < 2) return "";
  const step = w / (vals.length - 1);
  const pts = vals.map((v, i) => `${(i * step).toFixed(1)},${(h - (v / 100) * (h - 4) - 2).toFixed(1)}`).join(" ");
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline points="0,${h} ${pts} ${w},${h}" fill="rgba(79,209,197,.15)" stroke="none"/><polyline points="${pts}" fill="none" stroke="var(--accent)" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>`;
}
function renderMacMini() {
  const s = S.state.sys || {};
  $("#macMiniCard").innerHTML = `<h2>${esc(s.hostname || "Mac")} <button class="act" data-tab="mac">Подробно →</button></h2>
    <div class="mini-rows"><div><span>CPU</span>${s.cpu != null ? Math.round(s.cpu) + "%" : "—"}</div><div><span>Температура</span>${s.temp && s.temp.cpu != null ? Math.round(s.temp.cpu) + "°C" : "—"}</div>
    <div><span>Память</span>${s.mem ? fmtBytes(s.mem.used) + " / " + fmtBytes(s.mem.total) : "—"}</div><div><span>Работает</span>${s.uptime ? fmtUptime(s.uptime) : "—"}</div></div>
    ${spark(s.cpu_history)}`;
}
function renderMacView() {
  const s = S.state.sys || {}, t = s.temp || {}, m = s.mem || {};
  const disks = (s.disks || []).map((d) => `<div class="disk"><div class="nm">${d.external ? "💾" : "🖥\ufe0f"} ${esc(d.name)}</div>
      <div class="bar ${d.pct > 90 ? "" : "done"}"><i style="width:${d.pct}%;${d.pct > 90 ? "background:var(--red)" : ""}"></i></div>
      <div class="fr">${fmtBytes(d.free)} свободно<br><span class="dim">из ${fmtBytes(d.total)}</span></div>
      ${d.external ? `<button class="btn" data-eject="${esc(d.mount)}">⏏</button>` : ""}</div>`).join("");
  const folders = (S.config.folders || []).map((f) => `<button class="tile" data-folder="${esc(f.path)}"><span class="ic">📁</span>${esc(f.title)}</button>`).join("");
  $("#macView").innerHTML = `
    <div class="card"><h2>${esc(s.hostname || "")} · ${esc(s.chip || s.model || "")} · ${s.cores || "?"} ядер</h2>
      <div class="meters">
        <div class="meter"><small>Процессор</small><b>${s.cpu != null ? Math.round(s.cpu) : "—"}%</b>${spark(s.cpu_history)}</div>
        <div class="meter"><small>Температура SoC</small><b>${t.cpu != null ? Math.round(t.cpu) + "°" : "—"}</b><small>средняя ${t.cpu_avg != null ? Math.round(t.cpu_avg) + "°" : "—"} · SSD ${t.ssd != null ? Math.round(t.ssd) + "°" : "—"}</small>
          <small>${s.thermal === "throttled" ? "⚠️ троттлинг" : "охлаждение в норме"}</small></div>
        <div class="meter"><small>Память</small><b>${m.pct != null ? Math.round(m.pct) : "—"}%</b><small>${fmtBytes(m.used)} из ${fmtBytes(m.total)}${m.swap_mb ? " · swap " + Math.round(m.swap_mb) + " МБ" : ""}</small>
          <div class="bar"><i style="width:${m.pct || 0}%"></i></div></div>
        <div class="meter"><small>Нагрузка (1/5/15 мин)</small><b style="font-size:26px">${(s.load || []).join(" · ")}</b><small>работает ${s.uptime ? fmtUptime(s.uptime) : "—"}</small><small>IP ${esc(s.ip || "")}</small></div>
      </div></div>
    <div class="grid-2 section-gap">
      <div class="card"><h2>Диски</h2>${disks || '<div class="empty">—</div>'}</div>
      <div class="card"><h2>Система</h2><div class="tiles">
        ${SYS_TILES.map((x) => `<button class="tile ${x.a === "awake" && S.state.awake ? "on" : ""}" data-sys="${x.a}" ${x.confirm ? 'data-confirm="1"' : ""}><span class="ic">${x.ic}</span>${x.t}</button>`).join("")}
        ${folders}</div>
        <h2 style="margin-top:16px">Приложения</h2><div class="tiles">${(S.apps || []).filter((a) => a.installed).map(appTile).join("")}</div></div>
    </div>`;
  bindTiles($("#macView"));
  $$("[data-eject]").forEach((b) => b.onclick = () => armed(b, () => doAction("eject", b.dataset.eject)));
}

// ---------------- render: notes ----------------
const COLORS = ["blue", "teal", "green", "amber", "red", "violet"];
function renderNotesView() {
  const notes = S.notes || [];
  const tags = [...new Set(notes.map((n) => n.tag).filter(Boolean))];
  const list = notes.filter((n) => !noteFilter || n.tag === noteFilter).sort((a, b) => (b.pinned - a.pinned) || b.updated - a.updated);
  $("#notesView").innerHTML = `<div class="toolbar"><h2 style="margin:0 12px 0 0;font-size:24px">Справка</h2>
      <button class="fchip ${noteFilter ? "" : "on"}" data-f="">Все · ${notes.length}</button>
      ${tags.map((t) => `<button class="fchip ${noteFilter === t ? "on" : ""}" data-f="${esc(t)}">${esc(t)}</button>`).join("")}
      <div class="spacer"></div><button class="btn primary" id="nAdd">+ Заметка</button></div>
    <div class="notes-grid">${list.map((n) => `<div class="note ${n.color}" data-id="${n.id}"><h3>${n.pinned ? "📌 " : ""}${esc(n.title)}<button class="ed" data-ed>✎</button></h3>
      ${n.tag ? `<span class="tag">${esc(n.tag)}</span>` : ""}<div class="md">${md(n.body)}</div>
      ${(n.links || []).length ? `<div class="links">${n.links.map((l) => `<a href="${esc(l.url)}" target="_blank" rel="noopener">🔗 ${esc(l.title || l.url)}<small>${esc(l.url.replace(/^https?:\/\//, ""))}</small></a>`).join("")}</div>` : ""}
    </div>`).join("") || '<div class="empty">Пока пусто — добавьте первую шпаргалку</div>'}</div>`;
  $$("#notesView [data-f]").forEach((b) => b.onclick = () => { noteFilter = b.dataset.f; renderNotesView(); });
  $$("#notesView [data-ed]").forEach((b) => b.onclick = () => editNote(S.notes.find((n) => n.id === b.closest(".note").dataset.id)));
  $("#nAdd").onclick = () => editNote(null);
}
function editNote(n) {
  const isNew = !n; n = n || { title: "", tag: noteFilter, color: "blue", body: "", links: [], pinned: false };
  let links = (n.links || []).map((l) => ({ ...l }));
  let color = n.color;
  const tags = [...new Set((S.notes || []).map((x) => x.tag).filter(Boolean))];
  const linksHtml = () => links.map((l, i) => `<div class="row" style="margin-bottom:8px"><input type="text" data-li="${i}" data-k="title" value="${esc(l.title)}" placeholder="Название">
      <input type="text" data-li="${i}" data-k="url" value="${esc(l.url)}" placeholder="https://…" inputmode="url" style="flex:1.6"><button class="btn sq danger" data-rm="${i}" style="flex:none">×</button></div>`).join("");
  openSheet(`<h3>${isNew ? "Новая заметка" : "Заметка"}</h3>
    <div class="row"><div class="field" style="flex:2"><label>Заголовок</label><input type="text" id="nTitle" value="${esc(n.title)}"></div>
      <div class="field"><label>Раздел</label><input type="text" id="nTag" value="${esc(n.tag)}" list="nTags"><datalist id="nTags">${tags.map((t) => `<option value="${esc(t)}">`).join("")}</datalist></div></div>
    <div class="field"><label>Цвет</label><div class="seg" id="nColors">${COLORS.map((c) => `<button data-c="${c}" style="color:var(--${c === "teal" ? "accent" : c})">●</button>`).join("")}
      <button id="nPin" class="${n.pinned ? "on" : ""}" style="margin-left:auto">📌 Закрепить</button></div></div>
    <div class="field"><label>Текст — «- » список, **жирный**, \`код\`</label><textarea id="nBody">${esc(n.body)}</textarea></div>
    <div class="field"><label>Ссылки</label><div id="nLinks">${linksHtml()}</div><button class="btn" id="nAddLink">+ Ссылка</button></div>
    <div class="actions-row">${isNew ? "" : '<button class="btn danger left" id="nDel">Удалить</button>'}<button class="btn" id="nCancel">Отмена</button><button class="btn primary" id="nSave">Сохранить</button></div>`, (b) => {
    const syncC = () => $$("#nColors [data-c]", b).forEach((x) => x.classList.toggle("on", x.dataset.c === color));
    syncC(); $$("#nColors [data-c]", b).forEach((x) => x.onclick = () => { color = x.dataset.c; syncC(); });
    $("#nPin").onclick = (e) => e.target.classList.toggle("on");
    const readLinks = () => $$("#nLinks [data-li]", b).forEach((i) => links[+i.dataset.li][i.dataset.k] = i.value.trim());
    const bindLinks = () => $$("#nLinks [data-rm]", b).forEach((x) => x.onclick = () => { readLinks(); links.splice(+x.dataset.rm, 1); $("#nLinks").innerHTML = linksHtml(); bindLinks(); });
    bindLinks();
    $("#nAddLink").onclick = () => { readLinks(); links.push({ title: "", url: "" }); $("#nLinks").innerHTML = linksHtml(); bindLinks(); };
    $("#nCancel").onclick = closeSheet;
    if (!isNew) $("#nDel").onclick = (e) => armed(e.target, async () => { const r = await api("/api/notes", { op: "delete", id: n.id }); S.notes = r.notes; closeSheet(); renderNotesView(); });
    $("#nSave").onclick = async () => {
      readLinks();
      const body = { title: $("#nTitle").value.trim() || "Без названия", tag: $("#nTag").value.trim(), color, pinned: $("#nPin").classList.contains("on"),
        body: $("#nBody").value, links: links.filter((l) => l.url).map((l) => ({ title: l.title, url: /^[a-z]+:/i.test(l.url) ? l.url : "https://" + l.url })) };
      const r = await api("/api/notes", isNew ? { op: "add", ...body } : { op: "edit", id: n.id, ...body });
      S.notes = r.notes; closeSheet(); renderNotesView();
    };
  });
}

// ---------------- render: settings ----------------
function renderSettings() {
  const c = S.config || {}, w = S.weather || {};
  $("#settingsView").innerHTML = `<div class="grid-2">
    <div class="card"><h2>Погода</h2>
      <div class="field"><label>Город ${c.place ? "— сейчас: " + esc(c.place.name) : ""}</label>
        <form class="add-row" id="geoForm"><input type="search" id="geoQ" placeholder="Название города"><button class="btn primary" type="submit">Найти</button></form>
        <div id="geoRes" class="app-pick"></div></div>
      <div class="hint">Данные Open-Meteo (бесплатно, без ключа). В интернет уходят только координаты города.</div></div>
    <div class="card"><h2>Календарь macOS</h2>
      <div class="seg"><button id="calOn" class="${c.calendar !== false ? "on" : ""}">Показывать события</button><button id="calOff" class="${c.calendar === false ? "on" : ""}">Выключить</button></div>
      <div class="hint">${S.calendar && S.calendar.ok ? "Доступ есть (" + esc(S.calendar.source) + ")." : "Доступа пока нет — на Mac появится запрос, либо включите вручную (README)."}</div></div>
  </div>
  <div class="card section-gap"><h2>Приложения в быстрых действиях</h2>
    <div class="app-pick" id="appPick">${(c.apps || []).map((a) => `<button class="on" data-a="${esc(a)}">${esc(a)} ×</button>`).join("")}</div>
    <form class="add-row" id="appForm" style="margin-top:12px"><input type="search" id="appQ" placeholder="Добавить приложение: начните вводить название" list="appList"><datalist id="appList"></datalist><button class="btn primary">Добавить</button></form>
    <div class="hint">На главной показываются первые 8 установленных.</div></div>
  <div class="card section-gap"><h2>Каталоги Capture One</h2>
    ${(S.shoots.catalogs || []).map((p) => `<div class="mono" style="padding:6px 0">${esc(p)}</div>`).join("") || '<div class="muted">Не найдено</div>'}
    <div class="hint">${(c.c1_catalogs || []).length ? "Заданы вручную в data/config.json." : "Найдены автоматически (Spotlight + ~/Pictures). Чтобы указать вручную — впишите пути в «c1_catalogs» в data/config.json."}
    Каталог читается только для чтения — Capture One можно держать открытым.</div></div>
  <p class="hint">TabDock ${esc(S.state.version || "")} · данные хранятся на Mac в папке data/</p>`;
  $("#geoForm").onsubmit = async (e) => {
    e.preventDefault(); const q = $("#geoQ").value.trim(); if (!q) return;
    try {
      const res = await api("/api/geocode?q=" + encodeURIComponent(q));
      $("#geoRes").innerHTML = res.map((r, i) => `<button data-i="${i}">${esc(r.name)}, ${esc([r.admin, r.country].filter(Boolean).join(", "))}</button>`).join("") || '<span class="muted">Ничего не найдено</span>';
      $$("#geoRes [data-i]").forEach((b) => b.onclick = async () => { S = await api("/api/config", { place: res[+b.dataset.i] }); renderAll(); toast("Город сохранён"); });
    } catch (err) { toast("Нет интернета для поиска города"); }
  };
  $("#calOn").onclick = async () => { S = await api("/api/config", { calendar: true }); renderAll(); };
  $("#calOff").onclick = async () => { S = await api("/api/config", { calendar: false }); renderAll(); };
  $$("#appPick [data-a]").forEach((b) => b.onclick = async () => { S = await api("/api/config", { apps: c.apps.filter((a) => a !== b.dataset.a) }); renderAll(); });
  api("/api/apps_installed").then((list) => { $("#appList").innerHTML = list.map((a) => `<option value="${esc(a)}">`).join(""); }).catch(() => {});
  $("#appForm").onsubmit = async (e) => {
    e.preventDefault(); const a = $("#appQ").value.trim(); if (!a || (c.apps || []).includes(a)) return;
    S = await api("/api/config", { apps: [...(c.apps || []), a] }); renderAll();
  };
}
async function loadQR(el) {
  if (S.qr) { el.innerHTML = S.qr; return; }
  try { const r = await fetch("/api/qr.svg"); el.innerHTML = await r.text(); } catch (e) { el.textContent = "QR недоступен"; }
}
function showQR() {
  openSheet(`<h3>Подключить планшет</h3><div class="qr-box"><div class="qr" id="qrSheet"></div><div>
    <p>1. Планшет и Mac в одной Wi-Fi сети.<br>2. Наведите камеру планшета на код.<br>3. Откройте ссылку — и добавьте на главный экран (меню браузера → «Добавить на гл. экран»).</p>
    <div class="mono muted">${esc(S.url || "")}</div></div></div>
    <div class="actions-row"><button class="btn primary" id="qrClose">Готово</button></div>`, () => { loadQR($("#qrSheet")); $("#qrClose").onclick = closeSheet; });
}


// ---------------- wfolio ----------------
function gTitle(g) { return g.title || (g.check && g.check.title) || g.url.replace(/^https?:\/\//, "").slice(0, 40); }
function galleryFor(key) { return (S.wfolio || []).find((g) => g.shoot_key === key); }
function gDays(g) {
  const st = (g.check || {}).status;
  if (st === "expired") return { cls: "over", txt: "ссылка истекла" };
  if (g.days_left == null) return { cls: "", txt: "бессрочно" };
  if (g.days_left < 0) return { cls: "over", txt: "срок вышел " + (-g.days_left) + " дн. назад" };
  if (g.days_left === 0) return { cls: "over", txt: "истекает сегодня" };
  return { cls: g.days_left <= 3 ? "over" : g.days_left <= 14 ? "today" : "", txt: "ещё " + g.days_left + " дн. · до " + g.expires.slice(8) + "." + g.expires.slice(5, 7) };
}
const G_ST = { active: ["●", "var(--green)", "открывается"], expired: ["●", "var(--red)", "истекла"], error: ["●", "var(--amber)", "нет ответа"] };
function wfolioAlert() {
  const soon = (S.wfolio || []).filter((g) => g.days_left != null && g.days_left <= 14 && (g.check || {}).status !== "expired");
  if (!soon.length) return "";
  const g = soon[0];
  return `<div class="wf-alert" data-tab="shoots">⏳ wfolio: «${esc(gTitle(g))}» — ${esc(gDays(g).txt)}${soon.length > 1 ? ` и ещё ${soon.length - 1}` : ""}</div>`;
}
function wfolioSection() {
  const list = S.wfolio || [];
  const shootName = (k) => ((S.shoots.items || []).find((x) => x.key === k) || {}).name;
  return `<div class="toolbar section-gap"><h2 style="margin:0;font-size:24px">Галереи wfolio</h2><div class="spacer"></div>
      <button class="btn" id="wfAdd">+ Галерея</button></div>
    <div class="card">${list.map((g) => {
      const st = G_ST[(g.check || {}).status] || ["○", "var(--dim)", "ещё не проверена"];
      const d = gDays(g);
      return `<div class="wf" data-id="${g.id}"><span class="wf-dot" style="color:${st[1]}" title="${st[2]}">${st[0]}</span>
        <div class="wf-n"><b>${esc(gTitle(g))}</b><small>${esc([g.client, shootName(g.shoot_key) ? "съёмка: " + shootName(g.shoot_key) : "", st[2]].filter(Boolean).join(" · "))}</small></div>
        <span class="tag due ${d.cls}">${esc(d.txt)}</span>
        <a class="btn" href="${esc(g.url)}" target="_blank" rel="noopener">Открыть</a><button class="btn sq" data-wfed>✎</button></div>`;
    }).join("") || '<div class="empty">Добавьте ссылку на галерею клиента и срок хранения — док напомнит, когда он подходит к концу</div>'}</div>
    <p class="hint">У wfolio нет открытого API, поэтому галереи добавляются по ссылке, а срок хранения — вручную (как в настройках проекта wfolio).
      Док раз в 6 часов сам открывает ссылку и проверяет, жива ли галерея. Логин и пароль wfolio не нужны и не хранятся.</p>`;
}
function bindWfolio(root) {
  const add = $("#wfAdd", root); if (add) add.onclick = () => editGallery(null);
  $$("[data-wfed]", root).forEach((b) => b.onclick = () => editGallery((S.wfolio || []).find((g) => g.id === b.closest(".wf").dataset.id)));
}
function editGallery(g) {
  const isNew = !g; g = g || { url: "", title: "", client: "", expires: "", shoot_key: "" };
  const plus = (n) => todayStr(n);
  const shoots = (S.shoots.items || []).filter((x) => !x.hidden);
  openSheet(`<h3>${isNew ? "Галерея wfolio" : esc(gTitle(g))}</h3>
    <div class="field"><label>Ссылка на галерею (как клиенту)</label><input type="text" id="gUrl" inputmode="url" value="${esc(g.url)}" placeholder="https://вашсайт.ru/disk/…"></div>
    <div class="row"><div class="field"><label>Название</label><input type="text" id="gTitle" value="${esc(g.title)}" placeholder="возьму со страницы, если пусто"></div>
      <div class="field"><label>Клиент</label><input type="text" id="gClient" value="${esc(g.client)}"></div></div>
    <div class="field"><label>Срок хранения до</label><div class="seg" id="gSeg"><button data-d="">Бессрочно</button><button data-d="${plus(14)}">+2 недели</button>
      <button data-d="${plus(30)}">+1 месяц</button><button data-d="${plus(90)}">+3 месяца</button></div>
      <input type="date" id="gExp" value="${esc(g.expires || "")}" style="margin-top:8px"></div>
    <div class="field"><label>Съёмка в Capture One</label><select id="gShoot"><option value="">— не привязана —</option>
      ${shoots.map((x) => `<option value="${esc(x.key)}" ${x.key === g.shoot_key ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select></div>
    ${!isNew && g.check ? `<div class="hint">Проверено ${new Date(g.check.at * 1000).toLocaleString("ru")}: ${esc((G_ST[g.check.status] || [, , "?"])[2])}${g.check.http ? " (HTTP " + g.check.http + ")" : ""}${g.check.protected ? " · галерея под паролем" : ""}</div>` : ""}
    <div class="actions-row">${isNew ? "" : '<button class="btn danger left" id="gDel">Удалить</button><button class="btn" id="gCheck">Проверить сейчас</button>'}
      <button class="btn" id="gCancel">Отмена</button><button class="btn primary" id="gSave">Сохранить</button></div>`, (b) => {
    const sync = () => $$("#gSeg button", b).forEach((x) => x.classList.toggle("on", x.dataset.d === $("#gExp").value));
    sync(); $$("#gSeg button", b).forEach((x) => x.onclick = () => { $("#gExp").value = x.dataset.d; sync(); }); $("#gExp").onchange = sync;
    $("#gCancel").onclick = closeSheet;
    const done = (r) => { S.wfolio = r.wfolio; closeSheet(); renderAll(); };
    if (!isNew) {
      $("#gDel").onclick = (e) => armed(e.target, async () => done(await api("/api/wfolio", { op: "delete", id: g.id })));
      $("#gCheck").onclick = async () => { done(await api("/api/wfolio", { op: "check", id: g.id })); toast("Проверю за пару секунд"); setTimeout(loadAll, 4000); };
    }
    $("#gSave").onclick = async () => {
      const body = { url: $("#gUrl").value.trim(), title: $("#gTitle").value.trim(), client: $("#gClient").value.trim(), expires: $("#gExp").value || null, shoot_key: $("#gShoot").value || null };
      if (!body.url) { toast("Нужна ссылка"); return; }
      const r = await api("/api/wfolio", isNew ? { op: "add", ...body } : { op: "edit", id: g.id, ...body });
      if (!r.ok) { toast("Ссылка выглядит неправильно"); return; }
      done(r); if (isNew) setTimeout(loadAll, 5000);
    };
    if (isNew) setTimeout(() => $("#gUrl").focus(), 50);
  });
}

// ---------------- connect ----------------
let scanState = { running: false, done: 0, total: 0, found: new Map() };
function autoOn() { return localStorage.getItem("dock_auto") !== "0"; }
function renderConnect() {
  const sys = S.state.sys || {}, here = location.origin;
  const list = [...scanState.found.values()];
  for (const s of DockConnect.saved()) if (!scanState.found.has(s.base)) list.push({ ...s, offline: true });
  if (!list.find((x) => x.base === here)) list.unshift({ base: here, name: sys.hostname, model: sys.chip });
  const hasPw = S.auth && S.auth.password;
  $("#connectView").innerHTML = `<div class="grid-2">
    <div class="card"><h2>Этот Mac</h2>
      <div class="srv-big"><span class="ic">🖥️</span><div><b>${esc(sys.hostname || "Mac")}</b><div class="muted">${esc(sys.chip || "")} · ${esc(sys.ip || "")}:${location.port || 80}</div>
      <div class="muted" style="font-size:13px">в сети как «TabDock (${esc(sys.hostname || "")})» · Bonjour _tabdock._tcp</div></div></div>
      <h2 style="margin-top:18px">Вход с другого устройства</h2>
      <div class="qr-box"><div class="qr" id="qrInline" style="width:200px;height:200px"></div>
        <div><b>1. QR-код</b> — навести камеру планшета, пароль не нужен.<br><br><b>2. Пароль</b> — открыть адрес <span class="mono">http://${esc(sys.ip || "")}:${location.port || 80}</span> и ввести пароль.<br><br>
        <b>3. Поиск</b> — на странице входа планшет сам находит TabDock в сети.</div></div></div>
    <div class="card"><h2>Пароль для входа ${hasPw ? '<span class="st done" style="text-transform:none;letter-spacing:0">задан</span>' : '<span class="st new" style="text-transform:none;letter-spacing:0">не задан</span>'}</h2>
      ${S.is_local ? `<form class="add-row" id="pwForm"><input type="password" id="pwNew" placeholder="${hasPw ? "Новый пароль" : "Придумайте пароль"}" autocomplete="new-password"><button class="btn primary">Сохранить</button></form>
        ${hasPw ? '<button class="btn danger" id="pwDel">Убрать пароль</button>' : ""}
        <div class="hint">Пароль хранится на Mac в виде хэша (PBKDF2). Вводится один раз на каждом устройстве. 5 неверных попыток — пауза 5 минут.</div>`
      : `<div class="muted">Пароль задаётся только на самом Mac (откройте TabDock на Mac → «Подключение»), чтобы его нельзя было сменить с чужого устройства.</div>`}
      <h2 style="margin-top:20px">Ключ доступа</h2>
      <button class="btn danger" id="newTok">Новый ключ — отключить все устройства</button>
      <div class="hint">После этого планшетам нужно снова отсканировать QR или ввести пароль.</div></div>
  </div>
  <div class="card section-gap"><h2>TabDock в сети <button class="act" id="scanBtn">${scanState.running ? "Ищу… " + Math.round(100 * scanState.done / (scanState.total || 1)) + "%" : "Искать"}</button></h2>
    ${list.map((s) => {
      const cur = s.base === here, on = cur || scanState.found.has(s.base);
      return `<div class="srv"><span class="dot ${on ? "on" : ""}"></span><div class="n"><b>${esc(s.name || s.base)}${cur ? " · вы здесь" : ""}</b>
        <small>${esc(s.base.replace("http://", ""))}${s.model ? " · " + esc(s.model) : ""}${!on ? " · не в сети" : ""}</small></div>
        ${cur ? "" : `<button class="btn" data-go="${esc(s.base)}">Перейти</button><button class="btn sq danger" data-forget="${esc(s.base)}">×</button>`}</div>`;
    }).join("")}
    <div class="row" style="margin-top:12px"><div class="seg" style="flex:none"><button id="autoBtn" class="${autoOn() ? "on" : ""}">⟳ Автоподключение</button></div>
      <div class="hint" style="margin:0">Если этот Mac пропал из сети больше чем на 15 секунд, планшет сам перейдёт на другой найденный TabDock.</div></div>
    <div class="hint">Совет: закрепите за Mac mini постоянный IP в роутере (DHCP-резервирование) — тогда ярлык на планшете не сломается после перезагрузки роутера.</div></div>`;
  loadQR($("#qrInline"));
  $("#newTok").onclick = (e) => armed(e.target, async () => { S = await api("/api/config", { new_token: true }); renderAll(); toast("Новый ключ — подключите устройства заново"); });
  const f = $("#pwForm");
  if (f) f.onsubmit = async (e) => { e.preventDefault(); const r = await api("/api/password", { password: $("#pwNew").value }); toast(r.message); if (r.ok) loadAll(); };
  const d = $("#pwDel"); if (d) d.onclick = (e) => armed(e.target, async () => { const r = await api("/api/password", { remove: true }); toast(r.message); loadAll(); });
  $("#scanBtn").onclick = scanNetwork;
  $("#autoBtn").onclick = () => { localStorage.setItem("dock_auto", autoOn() ? "0" : "1"); renderConnect(); };
  $$("[data-go]").forEach((b) => b.onclick = () => DockConnect.go(b.dataset.go));
  $$("[data-forget]").forEach((b) => b.onclick = () => { DockConnect.forget(b.dataset.forget); scanState.found.delete(b.dataset.forget); renderConnect(); });
}
async function scanNetwork() {
  if (scanState.running) return;
  scanState = { running: true, done: 0, total: 0, found: new Map() };
  let last = 0;
  const rerender = () => { if (activeTab() === "connect" && Date.now() - last > 400) { last = Date.now(); renderConnect(); } };
  await DockConnect.scan({ extraIps: [(S.state.sys || {}).ip],
    onFound: (s) => { scanState.found.set(s.base, s); DockConnect.remember(s); rerender(); },
    onProgress: (d, t) => { scanState.done = d; scanState.total = t; rerender(); } });
  scanState.running = false;
  if (activeTab() === "connect") renderConnect();
  toast("Найдено TabDock: " + scanState.found.size);
}
// remember this server; when it disappears, try the others
let offlineSince = 0;
function rememberHere() { const s = S.state.sys || {}; if (s.hostname) DockConnect.remember({ base: location.origin, name: s.hostname, model: s.chip }); }
async function tryFailover() {
  if (!autoOn() || !offlineSince || Date.now() - offlineSince < 15000) return;
  for (const s of DockConnect.saved()) {
    if (s.base === location.origin) continue;
    const r = await DockConnect.probe(s.base);
    if (r) { $("#offline").textContent = "Mac недоступен — переключаюсь на " + (r.name || r.base) + "…"; setTimeout(() => DockConnect.go(r.base), 1200); return; }
  }
}

// ---------------- main ----------------
function activeTab() { return ($(".tabs button.active") || {}).dataset ? $(".tabs button.active").dataset.tab : "home"; }
function renderLive() {
  renderTop();
  const tab = activeTab();
  if (tab === "home") { renderPlayer(); if (S.state.awake !== renderQuick._aw) { renderQuick._aw = S.state.awake; renderQuick(); } }
  if (tab === "mac" && !$("#macView .armed")) renderMacView();
}
function renderAll() {
  renderTop();
  const tab = activeTab();
  if (tab === "home") { renderReminders(); renderShootsCard(); renderCalendar(); renderPlayer(); renderQuick(); }
  if (tab === "shoots") renderShootsView();
  if (tab === "notes") renderNotesView();
  if (tab === "mac") renderMacView();
  if (tab === "settings") renderSettings();
  if (tab === "connect") renderConnect();
}

$("#qrBtn").onclick = () => showTab("connect");
$("#awakeBtn").onclick = () => doAction("awake");
// Fullscreen: browsers allow it only after a tap, so on touch devices the first tap enters fullscreen.
const fsEl = document.documentElement;
const canFs = !!(fsEl.requestFullscreen || fsEl.webkitRequestFullscreen);
function enterFs() {
  const f = fsEl.requestFullscreen || fsEl.webkitRequestFullscreen;
  try { const p = f.call(fsEl, { navigationUI: "hide" }); if (p && p.catch) p.catch(() => {}); } catch (e) { /* ignore */ }
}
function inFs() { return !!(document.fullscreenElement || document.webkitFullscreenElement); }
const inApp = /TabDockApp\//.test(navigator.userAgent);   // Android app is fullscreen already
if (!canFs || inApp) $("#fsBtn").classList.add("hidden");
$("#fsBtn").onclick = () => inFs() ? document.exitFullscreen() : enterFs();
const autoFs = !inApp && localStorage.getItem("dock_fs") !== "0" && ("ontouchstart" in window || navigator.maxTouchPoints > 0);
if (autoFs && canFs) document.addEventListener("pointerup", () => { if (!inFs()) enterFs(); }, { capture: true });
document.addEventListener("fullscreenchange", () => $("#fsBtn").classList.toggle("on", inFs()));
renderClock(); setInterval(renderClock, 5000);

const sheetOpen = () => !$("#sheet").classList.contains("hidden");
const typing = () => { const a = document.activeElement; return a && (a.tagName === "INPUT" || a.tagName === "TEXTAREA"); };
setInterval(() => { if (!document.hidden) loadState(); }, 2500);
setInterval(() => { if (!document.hidden && !sheetOpen() && !typing()) loadAll(); }, 30000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) loadAll(); });

const saved = window.__TAB__ || localStorage.getItem("dock_tab");
if (saved && saved !== "home") { $$(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === saved)); $$(".view").forEach((v) => v.classList.toggle("active", v.dataset.view === saved)); }
if (/[?&]privacy=1/.test(location.search)) document.body.classList.add("privacy");
DockConnect.saved();
if (window.__INIT__) { S = window.__INIT__; renderAll(); rememberHere(); } else loadAll().then(rememberHere);
