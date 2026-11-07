/* TabDock — spaces (Фото / Работа / Отдых / Система) made of widgets on a 12×6 grid.
   Loaded before app.js; uses app.js helpers ($, esc, ic, api, S, render* …) at call time. */
"use strict";

// ---------------- widget registry ----------------
// single: only one per space (legacy cards bound to fixed element ids); live: re-render every state tick
const WIDGETS = {
  reminders: { name: "Напоминания", icon: "check", desc: "Свой список задач со сроками", w: 4, h: 6, single: true, id: "remindersCard", render: () => renderReminders() },
  shoots: { name: "Съёмки", icon: "aperture", desc: "Прогресс обработки съёмок", w: 4, h: 4, single: true, id: "shootsCard", render: () => renderShootsCard() },
  calendar: { name: "Погода, сроки, календарь", icon: "calendar", desc: "Всё о ближайших днях в одной карточке", w: 4, h: 2, single: true, id: "calendarCard", render: () => renderCalendar() },
  player: { name: "Музыка", icon: "note", desc: "Apple Music / Spotify и громкость", w: 4, h: 3, single: true, id: "playerCard", render: () => renderPlayer(), live: true },
  quick: { name: "Быстрые действия", icon: "cup", desc: "Приложения, сон, скриншот, «не спать»", w: 4, h: 3, single: true, id: "quickCard", render: () => renderQuick() },
  clock: { name: "Часы", icon: "hourglass", desc: "Крупное время и дата", w: 4, h: 2, render: (el) => wClock(el) },
  weather: { name: "Погода", icon: "cloudsun", desc: "Сейчас и на 4 дня", w: 4, h: 2, render: (el) => wWeather(el) },
  deadlines: { name: "Ближайшие сроки", icon: "hourglass", desc: "Сдача съёмок, wfolio, напоминания", w: 4, h: 2, render: (el) => wDeadlines(el) },
  events: { name: "Календарь", icon: "calendar", desc: "События macOS на сегодня и завтра", w: 4, h: 3, render: (el) => wEvents(el) },
  macstat: { name: "Компьютер", icon: "computer", desc: "Процессор, температура, память", w: 4, h: 3, single: true, render: (el) => wMacstat(el), live: true },
  disks: { name: "Диски", icon: "drive", desc: "Свободное место, внешние диски", w: 4, h: 3, single: true, render: (el) => wDisks(el), live: true },
  note: { name: "Заметка", icon: "book", desc: "Одна заметка или чек-лист из справки", w: 4, h: 4, render: (el, w) => wNote(el, w) },
  focus: { name: "Фокус-таймер", icon: "hourglass", desc: "25 минут работы, 5 отдыха", w: 4, h: 2, single: true, render: (el) => wFocus(el) },
  network: { name: "Сеть", icon: "link", desc: "Роутер, DNS, интернет", w: 4, h: 3, single: true, render: (el) => wNetwork(el), live: true },
  shortcuts: { name: "Команды", icon: "frame", desc: "Кнопки для Apple Shortcuts", w: 4, h: 2, render: (el, w) => wShortcuts(el, w) },
  wfolio: { name: "Галереи wfolio", icon: "link", desc: "Сроки хранения галерей клиентов", w: 4, h: 3, single: true, render: (el) => wWfolio(el) },
};

const USAGE = [
  { id: "photo", name: "Фото и съёмки", icon: "aperture", desc: "Capture One, Photon Studio, Photoshop: прогресс, сроки, wfolio" },
  { id: "work", name: "Работа и задачи", icon: "check", desc: "Задачи, заметки, календарь, фокус-таймер" },
  { id: "fun", name: "Отдых и музыка", icon: "note", desc: "Плеер, погода, часы, быстрые действия" },
  { id: "admin", name: "Система и сеть", icon: "computer", desc: "Нагрузка, диски, сеть, команды" },
];
const TEMPLATES = {
  photo: { name: "Фото", icon: "aperture", widgets: [["reminders", 4, 6], ["shoots", 4, 4], ["player", 4, 3], ["quick", 4, 3], ["calendar", 4, 2]] },
  work: { name: "Работа", icon: "check", widgets: [["reminders", 4, 6], ["note", 4, 4], ["clock", 4, 2], ["deadlines", 4, 2], ["events", 4, 2], ["focus", 4, 2]] },
  fun: { name: "Отдых", icon: "note", widgets: [["clock", 6, 2], ["weather", 6, 2], ["player", 6, 4], ["quick", 6, 4]] },
  admin: { name: "Система", icon: "computer", widgets: [["macstat", 6, 3], ["network", 6, 3], ["disks", 6, 3], ["shortcuts", 6, 3]] },
};
function wid() { return Math.random().toString(36).slice(2, 10); }
function spaceFromTemplate(key) {
  const t = TEMPLATES[key];
  return { id: key + wid().slice(0, 4), name: t.name, icon: t.icon, widgets: t.widgets.map(([type, w, h]) => ({ id: wid(), type, w, h, opts: {} })) };
}
function spaces() {
  const sp = (S.config && S.config.spaces) || [];
  return sp.length ? sp : [spaceFromTemplate("photo")];
}
let curSpace = (location.search.match(/[?&]space=([a-z0-9]+)/) || [])[1] || localStorage.getItem("dock_space") || "";
function currentSpace() { const all = spaces(); return all.find((x) => x.id === curSpace) || all[0]; }
let editMode = false;
let layoutKey = "";

// ---------------- grid render ----------------
function gridCols() { return window.innerWidth < 760 ? 4 : 12; }
function span(w) { const c = gridCols(); return c === 12 ? w : Math.max(2, Math.min(c, Math.round(w * c / 12))); }
function renderHome() {
  const all = spaces(), sp = currentSpace();
  const key = JSON.stringify([sp.id, sp.widgets.map((w) => [w.id, w.type, w.w, w.h]), all.map((x) => [x.id, x.name, x.icon]), editMode, gridCols()]);
  if (key !== layoutKey) {
    layoutKey = key;
    $("#spacebar").innerHTML = all.map((x) => `<button class="sp ${x.id === sp.id ? "on" : ""}" data-sp="${esc(x.id)}">${ic(x.icon)}<span>${esc(x.name)}</span></button>`).join("")
      + `<div class="spacer"></div>${editMode ? `<button class="btn" id="spAdd">${ic("plus")} Виджет</button><button class="btn" id="spMenu">${ic("gear")} Пространство</button><button class="btn primary" id="spDone">Готово</button>`
        : `<button class="sp edit" id="spEdit" title="Изменить раскладку">${ic("pencil")}</button>`}`;
    $("#spaceGrid").classList.toggle("editing", editMode);
    $("#spaceGrid").innerHTML = sp.widgets.map((w, i) => {
      const def = WIDGETS[w.type]; if (!def) return "";
      return `<div class="w" data-w="${esc(w.id)}" style="grid-column:span ${span(w.w)};grid-row:span ${w.h}">
        <div class="card wcard" ${def.id ? `id="${def.id}"` : `id="w_${esc(w.id)}"`}></div>
        ${editMode ? `<div class="wedit"><b>${esc(def.name)}</b><small>${w.w}×${w.h}</small>
          <div class="wbtns"><button data-act="left" ${i === 0 ? "disabled" : ""}>${ic("prev")}</button><button data-act="right" ${i === sp.widgets.length - 1 ? "disabled" : ""}>${ic("next")}</button></div>
          <div class="wbtns"><button data-act="w-">ширина −</button><button data-act="w+">+</button></div>
          <div class="wbtns"><button data-act="h-">высота −</button><button data-act="h+">+</button></div>
          ${w.type === "note" || w.type === "shortcuts" ? '<div class="wbtns"><button data-act="opts">Настроить</button></div>' : ""}
          <button class="wdel" data-act="del">${ic("plus")}</button></div>` : ""}
      </div>`;
    }).join("") || `<div class="empty" style="grid-column:1/-1">Пространство пустое — нажмите ${ic("pencil")} и добавьте виджеты</div>`;
    bindSpaceBar();
    if (editMode) bindEdit(sp);
  }
  for (const w of sp.widgets) { liveSig[w.id] = null; renderWidget(w); }
}
function renderWidget(w) {
  const def = WIDGETS[w.type]; if (!def) return;
  const el = def.id ? document.getElementById(def.id) : document.getElementById("w_" + w.id);
  if (!el) return;
  try { def.render(el, w); } catch (e) { el.innerHTML = `<div class="empty">Ошибка виджета: ${esc(e.message)}</div>`; }
}
// Live widgets are redrawn only when their own data changed (polling runs every 2.5 s).
const liveSig = {};
function sigFor(type) {
  const st = S.state || {}, sys = st.sys || {};
  if (type === "player") { const m = { ...(st.media || {}) }; delete m.at; return JSON.stringify(m); }
  if (type === "macstat") return [Math.round(sys.cpu || 0), Math.round((sys.temp || {}).cpu || 0), Math.round((sys.mem || {}).pct || 0), Math.floor((sys.uptime || 0) / 60), (sys.cpu_history || []).length].join(",");
  if (type === "network") return String((st.net || {}).at);
  if (type === "disks") return JSON.stringify((sys.disks || []).map((d) => [d.name, Math.round(d.free / 1e8)]));
  return String(Math.random());
}
function renderSpaceLive() {
  if (editMode) return;
  for (const w of currentSpace().widgets) {
    if (!WIDGETS[w.type] || !WIDGETS[w.type].live) continue;
    const sig = sigFor(w.type);
    if (liveSig[w.id] === sig) continue;
    liveSig[w.id] = sig; renderWidget(w);
  }
}
function bindSpaceBar() {
  $$("#spacebar [data-sp]").forEach((b) => b.onclick = () => { curSpace = b.dataset.sp; localStorage.setItem("dock_space", curSpace); renderHome(); });
  const e = $("#spEdit"); if (e) e.onclick = () => { editMode = true; renderHome(); };
  const d = $("#spDone"); if (d) d.onclick = () => { editMode = false; renderHome(); };
  const a = $("#spAdd"); if (a) a.onclick = () => widgetCatalog();
  const m = $("#spMenu"); if (m) m.onclick = () => spaceSheet();
}
// swipe left/right on the home grid switches spaces
(function () {
  let x0 = null, y0 = 0;
  document.addEventListener("pointerdown", (e) => { if (e.target.closest("#spaceGrid") && !editMode) { x0 = e.clientX; y0 = e.clientY; } });
  document.addEventListener("pointerup", (e) => {
    if (x0 === null) return; const dx = e.clientX - x0, dy = e.clientY - y0; x0 = null;
    if (Math.abs(dx) < 120 || Math.abs(dy) > 60 || e.target.closest("input,textarea,input[type=range]")) return;
    const all = spaces(), i = all.findIndex((s) => s.id === currentSpace().id);
    const n = all[(i + (dx < 0 ? 1 : -1) + all.length) % all.length];
    if (n && n.id !== currentSpace().id) { curSpace = n.id; localStorage.setItem("dock_space", curSpace); renderHome(); }
  });
})();
window.addEventListener("resize", () => { if (activeTab() === "home") renderHome(); });

// ---------------- editing ----------------
let saveTimer;
function saveSpaces(all) {
  S.config.spaces = all; layoutKey = "";
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => api("/api/config", { spaces: all }).then((r) => { S.config = r.config; }).catch(() => toast("Не удалось сохранить раскладку")), 400);
}
function mutate(fn) { const all = JSON.parse(JSON.stringify(spaces())); const sp = all.find((x) => x.id === currentSpace().id) || all[0]; fn(sp, all); saveSpaces(all); renderHome(); }
function bindEdit(sp) {
  $$("#spaceGrid [data-act]").forEach((b) => b.onclick = (e) => {
    e.stopPropagation();
    const id = b.closest(".w").dataset.w, act = b.dataset.act;
    if (act === "opts") { const w = sp.widgets.find((x) => x.id === id); return w.type === "note" ? notePicker(w) : shortcutPicker(w); }
    mutate((s) => {
      const i = s.widgets.findIndex((x) => x.id === id); const w = s.widgets[i];
      if (act === "left" && i > 0) [s.widgets[i - 1], s.widgets[i]] = [s.widgets[i], s.widgets[i - 1]];
      if (act === "right" && i < s.widgets.length - 1) [s.widgets[i + 1], s.widgets[i]] = [s.widgets[i], s.widgets[i + 1]];
      if (act === "w-") w.w = Math.max(2, w.w - 1); if (act === "w+") w.w = Math.min(12, w.w + 1);
      if (act === "h-") w.h = Math.max(1, w.h - 1); if (act === "h+") w.h = Math.min(8, w.h + 1);
      if (act === "del") s.widgets.splice(i, 1);
    });
  });
}
function widgetCatalog() {
  const sp = currentSpace();
  openSheet(`<h3>Добавить виджет</h3><div class="wcat">${Object.entries(WIDGETS).map(([k, d]) => {
      const taken = d.single && sp.widgets.some((w) => w.type === k);
      return `<button class="wcat-i" data-add="${k}" ${taken ? "disabled" : ""}>${ic(d.icon)}<b>${esc(d.name)}</b><small>${taken ? "уже есть" : esc(d.desc)}</small></button>`;
    }).join("")}</div><div class="actions-row"><button class="btn" id="wcClose">Закрыть</button></div>`, (b) => {
    $("#wcClose").onclick = closeSheet;
    $$("[data-add]", b).forEach((x) => x.onclick = () => { const d = WIDGETS[x.dataset.add]; mutate((s) => s.widgets.push({ id: wid(), type: x.dataset.add, w: d.w, h: d.h, opts: {} })); closeSheet(); });
  });
}
function spaceSheet() {
  const sp = currentSpace(), all = spaces();
  const icons = ["home", "aperture", "check", "note", "computer", "book", "calendar", "cup", "star", "link", "drive", "moon"];
  let icon = sp.icon;
  openSheet(`<h3>Пространство</h3>
    <div class="field"><label>Название</label><input type="text" id="spName" value="${esc(sp.name)}"></div>
    <div class="field"><label>Значок</label><div class="seg" id="spIcons">${icons.map((n) => `<button data-i="${n}" class="${n === icon ? "on" : ""}">${ic(n)}</button>`).join("")}</div></div>
    <div class="field"><label>Добавить пространство из шаблона</label><div class="seg">${Object.entries(TEMPLATES).map(([k, t]) => `<button data-tpl="${k}">${ic(t.icon)} ${esc(t.name)}</button>`).join("")}<button data-tpl="">${ic("plus")} Пустое</button></div></div>
    <div class="actions-row">${all.length > 1 ? '<button class="btn danger left" id="spDel">Удалить это пространство</button>' : ""}
      <button class="btn" id="spL">${ic("prev")} Левее</button><button class="btn" id="spR">Правее ${ic("next")}</button>
      <button class="btn primary" id="spSave">Сохранить</button></div>`, (b) => {
    $$("#spIcons [data-i]", b).forEach((x) => x.onclick = () => { icon = x.dataset.i; $$("#spIcons [data-i]", b).forEach((y) => y.classList.toggle("on", y === x)); });
    $("#spSave").onclick = () => { mutate((s) => { s.name = $("#spName").value.trim() || s.name; s.icon = icon; }); closeSheet(); };
    $$("[data-tpl]", b).forEach((x) => x.onclick = () => {
      const n = x.dataset.tpl ? spaceFromTemplate(x.dataset.tpl) : { id: wid(), name: "Новое", icon: "home", widgets: [] };
      const next = JSON.parse(JSON.stringify(all)); next.push(n); saveSpaces(next); curSpace = n.id; localStorage.setItem("dock_space", n.id); closeSheet(); renderHome();
    });
    const move = (d) => { const next = JSON.parse(JSON.stringify(all)); const i = next.findIndex((x) => x.id === sp.id), j = i + d; if (j < 0 || j >= next.length) return; [next[i], next[j]] = [next[j], next[i]]; saveSpaces(next); renderHome(); };
    $("#spL").onclick = () => move(-1); $("#spR").onclick = () => move(1);
    const del = $("#spDel"); if (del) del.onclick = (e) => armed(e.target, () => { const next = all.filter((x) => x.id !== sp.id); saveSpaces(next); curSpace = next[0].id; closeSheet(); renderHome(); });
  });
}
function notePicker(w) {
  openSheet(`<h3>Какую заметку показывать</h3><div class="app-pick">${(S.notes || []).map((n) => `<button data-n="${n.id}" class="${w.opts.noteId === n.id ? "on" : ""}">${esc(n.title)}</button>`).join("") || '<span class="muted">Заметок нет — добавьте во вкладке «Справка»</span>'}</div>
    <div class="actions-row"><button class="btn" id="npClose">Готово</button></div>`, (b) => {
    $("#npClose").onclick = closeSheet;
    $$("[data-n]", b).forEach((x) => x.onclick = () => { mutate((s) => { s.widgets.find((y) => y.id === w.id).opts.noteId = x.dataset.n; }); closeSheet(); });
  });
}
async function shortcutPicker(w) {
  let list = []; try { list = await api("/api/shortcuts"); } catch (e) { /* ignore */ }
  const chosen = new Set(w.opts.names || []);
  openSheet(`<h3>Кнопки команд (Apple Shortcuts)</h3><div class="app-pick" id="scList">${list.map((n) => `<button data-s="${esc(n)}" class="${chosen.has(n) ? "on" : ""}">${esc(n)}</button>`).join("") || '<span class="muted">На Mac нет команд — создайте их в приложении «Команды»</span>'}</div>
    <div class="hint">Отметьте до 8 команд. Например, «Режим съёмки»: открыть Capture One, включить «Не беспокоить», плейлист.</div>
    <div class="actions-row"><button class="btn primary" id="scSave">Сохранить</button></div>`, (b) => {
    $$("[data-s]", b).forEach((x) => x.onclick = () => { const n = x.dataset.s; chosen.has(n) ? chosen.delete(n) : chosen.size < 8 && chosen.add(n); x.classList.toggle("on", chosen.has(n)); });
    $("#scSave").onclick = () => { mutate((s) => { s.widgets.find((y) => y.id === w.id).opts.names = [...chosen]; }); closeSheet(); };
  });
}

// ---------------- new widgets ----------------
function head(t, extra) { return `<h2>${esc(t)}${extra || ""}</h2>`; }
function wClock(el) {
  const d = new Date();
  el.innerHTML = `<div class="wclock"><b>${pad(d.getHours())}:${pad(d.getMinutes())}</b><span>${RU_DAYS[d.getDay()]}, ${d.getDate()} ${RU_MON[d.getMonth()]}</span></div>`;
}
function wWeather(el) {
  const w = S.weather || {};
  if (w.temp == null) { el.innerHTML = head("Погода") + `<div class="empty">${w.configured === false ? "Выберите город в «Настройках»" : "Нет данных о погоде (нет интернета на компьютере?)"}</div>`; return; }
  el.innerHTML = head("Погода", ` <span class="dim" style="text-transform:none;letter-spacing:0">· ${esc(w.place || "")}</span>`) + `<div class="wweather"><div class="now">${ic(weatherIcon(w.code), "wx")}<b>${Math.round(w.temp)}°</b><span>${esc(w.text)}<br><small class="muted">ощущается ${Math.round(w.feels)}° · ветер ${Math.round(w.wind)} м/с</small></span></div>
    <div class="forecast">${(w.days || []).slice(0, 4).map((d, i) => { const dt = new Date(d.date + "T12:00"); return `<div class="d">${i === 0 ? "сегодня" : RU_DS[dt.getDay()]}<b>${ic(weatherIcon(d.code), "wx")}</b>${Math.round(d.max)}° <span class="dim">${Math.round(d.min)}°</span></div>`; }).join("")}</div></div>`;
}
function wDeadlines(el) { el.innerHTML = head("Ближайшие сроки") + `<div class="list">${deadlinesHtml().replace('<div class="day-h">Ближайшие сроки</div>', "") || '<div class="empty">На две недели сроков нет</div>'}</div>`; }
function wEvents(el) {
  const c = S.calendar || {};
  if (!c.ok) { el.innerHTML = head("Календарь") + '<div class="empty">Нет доступа к Календарю macOS</div>'; return; }
  const now = Date.now();
  el.innerHTML = head("Календарь") + `<div class="list">${(c.events || []).map((e) => { const st = new Date(e.start), en = new Date(e.end);
    return `<div class="ev" style="${en < now ? "opacity:.45" : ""}"><div class="tm">${e.allDay ? "весь день" : pad(st.getHours()) + ":" + pad(st.getMinutes())}</div><div class="dot" style="background:${esc(e.color)}"></div><div class="tt">${esc(e.title)}<small>${e.start.slice(0, 10) === todayStr() ? "сегодня" : "завтра"}${e.location ? " · " + esc(e.location) : ""}</small></div></div>`; }).join("") || '<div class="empty">Сегодня и завтра событий нет</div>'}</div>`;
}
function wMacstat(el) {
  const s = S.state.sys || {}, t = s.temp || {}, m = s.mem || {};
  el.innerHTML = head(s.hostname || "Компьютер", `<button class="act" data-tab="mac">Подробно ${ic("chevron")}</button>`) + `<div class="mini-rows">
    <div><span>CPU</span>${s.cpu != null ? Math.round(s.cpu) + "%" : "—"}</div><div><span>Температура</span>${t.cpu != null ? Math.round(t.cpu) + "°" : "—"}</div>
    <div><span>Память</span>${m.pct != null ? Math.round(m.pct) + "%" : "—"}</div><div><span>Работает</span>${s.uptime ? fmtUptime(s.uptime) : "—"}</div></div>${spark(s.cpu_history)}`;
}
function wDisks(el) {
  const ds = (S.state.sys || {}).disks || [];
  el.innerHTML = head("Диски", `<button class="act" data-tab="mac">Все ${ic("chevron")}</button>`) + `<div class="list">${ds.filter((d) => d.bus !== "Disk Image").map((d) => `<div class="wdisk"><div class="row"><b>${esc(d.name)}</b><span class="muted">${fmtBytes(d.free)} свободно</span></div>
    <div class="bar ${d.pct > 90 ? "" : "done"}"><i style="width:${d.pct}%;${d.pct > 90 ? "background:var(--red)" : ""}"></i></div></div>`).join("")}</div>`;
}
function wNote(el, w) {
  const notes = S.notes || [];
  const n = notes.find((x) => x.id === w.opts.noteId) || notes.find((x) => x.pinned) || notes[0];
  if (!n) { el.innerHTML = head("Заметка") + '<div class="empty">Заметок нет — добавьте во вкладке «Справка»</div>'; return; }
  el.innerHTML = `<h2>${esc(n.title)}<button class="act" data-wned>${ic("pencil")}</button></h2><div class="list note-in" data-id="${n.id}"><div class="md">${md(n.body)}</div></div>`;
  el.querySelector("[data-wned]").onclick = () => editNote(n);
  el.querySelectorAll(".chk").forEach((li) => li.onclick = async () => {
    const lines = n.body.split("\n"), i = +li.dataset.line;
    lines[i] = lines[i].replace(/\[( |x|х)\]/i, (m, c) => c.trim() ? "[ ]" : "[x]");
    const r = await api("/api/notes", { op: "edit", id: n.id, body: lines.join("\n") }); S.notes = r.notes; wNote(el, w);
  });
}
const FOCUS = { work: 25 * 60, rest: 5 * 60 };
function focusState() { try { return JSON.parse(localStorage.getItem("dock_focus") || "null") || { mode: "work", end: 0, left: FOCUS.work }; } catch (e) { return { mode: "work", end: 0, left: FOCUS.work }; } }
function wFocus(el) {
  const f = focusState(); const running = f.end > Date.now();
  const left = running ? Math.round((f.end - Date.now()) / 1000) : f.left;
  el.innerHTML = head(f.mode === "work" ? "Фокус" : "Перерыв") + `<div class="wfocus"><b>${Math.floor(left / 60)}:${pad(left % 60)}</b>
    <div class="row"><button class="btn primary" data-f="go">${ic(running ? "pause" : "play")}</button><button class="btn" data-f="reset">${ic("reset")}</button>
    <button class="btn" data-f="mode">${f.mode === "work" ? "Перерыв" : "Работа"}</button></div></div>`;
  const save = (x) => { localStorage.setItem("dock_focus", JSON.stringify(x)); wFocus(el); };
  el.querySelector('[data-f="go"]').onclick = () => save(running ? { ...f, end: 0, left } : { ...f, end: Date.now() + left * 1000 });
  el.querySelector('[data-f="reset"]').onclick = () => save({ mode: f.mode, end: 0, left: FOCUS[f.mode] });
  el.querySelector('[data-f="mode"]').onclick = () => { const m = f.mode === "work" ? "rest" : "work"; save({ mode: m, end: 0, left: FOCUS[m] }); };
}
setInterval(() => {
  const f = focusState();
  if (f.end && f.end <= Date.now()) {
    const m = f.mode === "work" ? "rest" : "work";
    localStorage.setItem("dock_focus", JSON.stringify({ mode: m, end: 0, left: FOCUS[m] }));
    banner(f.mode === "work" ? "Время перерыва" : "Перерыв окончен", f.mode === "work" ? "25 минут фокуса позади — отдохните 5 минут" : "Можно возвращаться к работе");
  }
  // clock: once a minute; focus timer: every second only while it runs
  const minute = new Date().getMinutes(), running = focusState().end > Date.now();
  for (const w of currentSpace().widgets) {
    if (w.type === "clock" && liveSig[w.id] !== minute) { liveSig[w.id] = minute; renderWidget(w); }
    if (w.type === "focus" && (running || liveSig[w.id] !== "idle")) { liveSig[w.id] = running ? "run" : "idle"; renderWidget(w); }
  }
}, 1000);
function wNetwork(el) {
  const n = S.state.net || {};
  if (!n.at) { el.innerHTML = head("Сеть") + '<div class="empty">Проверяю сеть…</div>'; return; }
  const row = (ok, name, val) => `<div class="nrow"><span class="ndot" style="background:${ok ? "var(--green)" : "var(--red)"}"></span><b>${name}</b><span class="muted">${esc(val)}</span></div>`;
  const verdict = !n.gw_ms ? "Нет связи с роутером" : !n.dns_ok ? "DNS не отвечает — сайты не открываются" : !n.inet_ok ? "Нет выхода в интернет" : "Сеть в порядке";
  el.innerHTML = head("Сеть", ` <span class="dim" style="text-transform:none;letter-spacing:0">· ${esc(n.iface || "")}</span>`) + `<div class="list">
    ${row(n.gw_ms != null, "Роутер", n.gateway ? `${n.gateway} · ${n.gw_ms != null ? Math.round(n.gw_ms) + " мс" : "не отвечает"}${n.gw_loss ? " · потери " + Math.round(n.gw_loss) + "%" : ""}` : "не найден")}
    ${row(n.dns_ok, "DNS", n.dns_ok ? n.dns_ms + " мс" : (n.dns_err || "ошибка"))}
    ${row(n.inet_ok, "Интернет", n.inet_ok ? n.inet_ms + " мс" : (n.inet_err || "нет"))}
    <div class="nverdict ${verdict === "Сеть в порядке" ? "ok" : "bad"}">${esc(verdict)}</div></div>`;
}
function wShortcuts(el, w) {
  const names = w.opts.names || [];
  el.innerHTML = head("Команды") + (names.length ? `<div class="tiles">${names.map((n) => `<button class="tile" data-sc="${esc(n)}"><span class="ic">${ic("frame")}</span>${esc(n)}</button>`).join("")}</div>`
    : `<div class="empty">Выберите команды Apple Shortcuts<br><button class="btn" data-scpick style="margin-top:10px">Выбрать</button></div>`);
  el.querySelectorAll("[data-sc]").forEach((b) => b.onclick = () => doAction("shortcut", b.dataset.sc));
  const p = el.querySelector("[data-scpick]"); if (p) p.onclick = () => shortcutPicker(w);
}
function wWfolio(el) {
  const list = S.wfolio || [];
  el.innerHTML = head("Галереи wfolio", `<button class="act" data-tab="shoots">Все ${ic("chevron")}</button>`) + `<div class="list">${list.map((g) => { const d = gDays(g); const st = G_ST[(g.check || {}).status] || ["○", "var(--dim)"];
    return `<div class="wf"><span class="wf-dot" style="color:${st[1]}">●</span><div class="wf-n"><b>${esc(gTitle(g))}</b></div><span class="tag due ${d.cls}">${esc(d.txt)}</span></div>`; }).join("") || '<div class="empty">Галерей пока нет</div>'}</div>`;
}
