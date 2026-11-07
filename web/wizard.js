/* TabDock — first-run setup: usage scenarios → spaces, photo workflow, weather, skin, connecting a tablet. */
"use strict";

const WZ = { step: 0, usage: new Set(["photo"]), editor: "c1", rule: { type: "color_or_export", color: 4, rating: 5 },
  folder: "", folderApp: "Photon Studio", place: null, skin: null, catalogs: null };
const COLOR_DOTS = { 1: "#ff453a", 2: "#ff9f0a", 3: "#ffd60a", 4: "#30d158", 5: "#0a84ff", 6: "#ff6ac1", 7: "#bf5af2" };

function wizardSteps() {
  const st = ["hello", "usage"];
  if (WZ.usage.has("photo")) st.push("photo");
  st.push("weather", "look", "connect", "done");
  return st;
}
function showWizard(force) {
  if (!force && (S.config || {}).setup_done) return;
  WZ.step = 0; WZ.skin = currentSkin();
  if (S.config && S.config.usage && S.config.usage.length) WZ.usage = new Set(S.config.usage);
  if (S.config && S.config.done_rule) WZ.rule = { ...WZ.rule, ...S.config.done_rule };
  let el = $("#wizard");
  if (!el) { el = document.createElement("div"); el.id = "wizard"; document.body.appendChild(el); }
  el.classList.remove("hidden");
  const q = location.search.match(/[?&]wz=(\d)/); if (q) WZ.step = +q[1];   // screenshots of a given step
  renderWizard();
}
function closeWizard() { const el = $("#wizard"); if (el) el.classList.add("hidden"); }

function renderWizard() {
  const steps = wizardSteps(), name = steps[WZ.step], el = $("#wizard");
  const dots = steps.map((s, i) => `<i class="${i === WZ.step ? "on" : i < WZ.step ? "past" : ""}"></i>`).join("");
  let body = "", next = "Дальше", canBack = WZ.step > 0;
  if (name === "hello") {
    body = `<div class="wz-hero"><img src="/static/icon.svg" alt=""><h1>Привет! Это TabDock</h1>
      <p>Планшет, который лежит без дела, становится доком для работы: задачи, съёмки, музыка, состояние компьютера.
      Настроим всё под вас — займёт минуту. Потом всё можно поменять.</p></div>`;
    next = "Начать";
  } else if (name === "usage") {
    body = `<h2>Для чего вам док?</h2><p class="muted">Можно выбрать несколько — для каждого будет своё пространство с виджетами.</p>
      <div class="wz-cards">${USAGE.map((u) => `<button class="wz-card ${WZ.usage.has(u.id) ? "on" : ""}" data-u="${u.id}">${ic(u.icon)}<b>${esc(u.name)}</b><small>${esc(u.desc)}</small></button>`).join("")}</div>`;
  } else if (name === "photo") {
    const r = WZ.rule;
    body = `<h2>Съёмки</h2>
      <div class="field"><label>Где вы обрабатываете фото?</label><div class="seg" id="wzEd">
        <button data-ed="c1" class="${WZ.editor === "c1" ? "on" : ""}">Capture One</button>
        <button data-ed="folders" class="${WZ.editor === "folders" ? "on" : ""}">Photon Studio, Photoshop и др. (папки)</button>
        <button data-ed="none" class="${WZ.editor === "none" ? "on" : ""}">Пока не нужно</button></div></div>
      <div id="wzEdBox">${WZ.editor === "c1" ? `<div class="muted" id="wzCats">Ищу каталоги…</div>` : WZ.editor === "folders" ? `
        <div class="row"><input type="text" id="wzFolder" placeholder="/Volumes/SSD/Съёмки" value="${esc(WZ.folder)}" style="flex:2">
        <input type="text" id="wzFolderApp" value="${esc(WZ.folderApp)}"></div>
        <div class="hint">Папка, где каждая подпапка — съёмка. Готовые файлы — в подпапке «Export»/«Готово» (меняется в настройках).</div>` : ""}</div>
      ${WZ.editor === "c1" ? `<div class="field" style="margin-top:16px"><label>Что считать отданными кадрами?</label><div class="seg" id="wzRule">
        <button data-r="export" class="${r.type === "export" ? "on" : ""}">Экспортированные</button>
        <button data-r="color" class="${r.type === "color" ? "on" : ""}">С цветной меткой</button>
        <button data-r="color_or_export" class="${r.type === "color_or_export" ? "on" : ""}">Метка или экспорт</button>
        <button data-r="rating" class="${r.type === "rating" ? "on" : ""}">По рейтингу</button></div>
        ${r.type === "color" || r.type === "color_or_export" ? `<div class="wz-colors">${Object.entries(COLOR_DOTS).map(([k, c]) => `<button data-c="${k}" class="${+k === +r.color ? "on" : ""}" style="background:${c}"></button>`).join("")}<span class="muted">какой меткой вы отмечаете готовые</span></div>` : ""}
        ${r.type === "rating" ? `<div class="seg" style="margin-top:8px">${[1, 2, 3, 4, 5].map((n) => `<button data-rt="${n}" class="${+r.rating === n ? "on" : ""}">${"★".repeat(n)}+</button>`).join("")}</div>` : ""}
        <div class="hint">«Метка или экспорт» удобно, если раньше готовые кадры не отмечались: старые выгруженные съёмки не станут «0%».</div></div>` : ""}`;
  } else if (name === "weather") {
    body = `<h2>Погода</h2><p class="muted">Город для погоды на главной (данные Open-Meteo, без регистрации). Можно пропустить.</p>
      <form class="add-row" id="wzGeo"><input type="search" id="wzGeoQ" placeholder="Название города"><button class="btn primary">Найти</button></form>
      <div class="app-pick" id="wzGeoRes">${WZ.place ? `<button class="on">${esc(WZ.place.name)}</button>` : ""}</div>`;
  } else if (name === "look") {
    body = `<h2>Оформление</h2><p class="muted">Скин можно сменить в любой момент в «Настройках».</p>${skinsHtml()}`;
  } else if (name === "connect") {
    body = S.is_local ? `<h2>Подключите планшет или телефон</h2><div class="qr-box"><div class="qr">${S.qr || ""}</div><div>
        <p>Наведите камеру планшета на код — он подключится без пароля. Или поставьте приложение TabDock для Android (релизы на GitHub).</p>
        <div class="field"><label>Пароль для входа с других устройств (необязательно)</label><input type="password" id="wzPw" placeholder="Придумайте пароль"></div></div></div>`
      : `<h2>Это устройство уже подключено</h2><p class="muted">Чтобы подключать новые устройства по паролю, задайте его на компьютере: «Подключение» → «Пароль для входа».</p>`;
  } else if (name === "done") {
    const names = [...WZ.usage].map((u) => TEMPLATES[u].name).join(", ");
    body = `<div class="wz-hero">${ic("check", "wz-ok")}<h1>Готово!</h1><p>Пространства: <b>${esc(names)}</b>. Переключаются вкладками над виджетами или свайпом.
      Раскладку можно менять кнопкой ${ic("pencil")}, а первую настройку пройти заново в «Настройках».</p></div>`;
    next = "Открыть TabDock";
  }
  el.innerHTML = `<div class="wz"><div class="wz-top"><div class="wz-dots">${dots}</div><button class="btn" id="wzSkip">Пропустить</button></div>
    <div class="wz-body">${body}</div>
    <div class="actions-row">${canBack ? `<button class="btn left" id="wzBack">${ic("prev")} Назад</button>` : ""}<button class="btn primary" id="wzNext">${esc(next)}</button></div></div>`;
  bindWizard(name);
}

function bindWizard(name) {
  $("#wzSkip").onclick = async () => { closeWizard(); S = await api("/api/config", { setup_done: true }); renderAll(); };
  const back = $("#wzBack"); if (back) back.onclick = () => { WZ.step--; renderWizard(); };
  $("#wzNext").onclick = async () => {
    if (name === "usage" && !WZ.usage.size) { toast("Выберите хотя бы один вариант"); return; }
    if (name === "photo" && WZ.editor === "folders") { WZ.folder = ($("#wzFolder") || {}).value || ""; WZ.folderApp = ($("#wzFolderApp") || {}).value || "Папки"; }
    if (name === "connect" && $("#wzPw") && $("#wzPw").value) {
      const r = await api("/api/password", { password: $("#wzPw").value }); toast(r.message); if (!r.ok) return;
    }
    if (name === "done") return finishWizard();
    WZ.step++; renderWizard();
  };
  $$("#wizard [data-u]").forEach((b) => b.onclick = () => { const u = b.dataset.u; WZ.usage.has(u) ? WZ.usage.delete(u) : WZ.usage.add(u); b.classList.toggle("on"); });
  $$("#wizard [data-ed]").forEach((b) => b.onclick = () => { WZ.editor = b.dataset.ed; renderWizard(); });
  $$("#wizard [data-r]").forEach((b) => b.onclick = () => { WZ.rule.type = b.dataset.r; renderWizard(); });
  $$("#wizard [data-c]").forEach((b) => b.onclick = () => { WZ.rule.color = +b.dataset.c; renderWizard(); });
  $$("#wizard [data-rt]").forEach((b) => b.onclick = () => { WZ.rule.rating = +b.dataset.rt; renderWizard(); });
  $$("#wizard [data-skin]").forEach((b) => b.onclick = () => { applySkin(b.dataset.skin); WZ.skin = b.dataset.skin; renderWizard(); });
  if (name === "photo" && WZ.editor === "c1") {
    api("/api/catalogs").then((d) => {
      const box = $("#wzCats"); if (!box) return;
      const active = new Set(d.active);
      box.innerHTML = d.found.filter((e) => e.exists).length
        ? `<div class="muted" style="margin-bottom:6px">Найдены каталоги (используется открытый в Capture One, остальное — в «Настройках»):</div>` +
          d.found.filter((e) => e.exists).map((e) => `<div class="srv" style="margin-bottom:6px">${ic(active.has(e.path) ? "check" : "disc")}<div class="n"><b>${esc(e.path.split("/").pop())}</b><small>${esc(e.path)}</small></div></div>`).join("")
        : "Каталоги Capture One пока не найдены — укажите путь позже в «Настройках».";
    }).catch(() => {});
  }
  const geo = $("#wzGeo");
  if (geo) geo.onsubmit = async (e) => {
    e.preventDefault(); const q = $("#wzGeoQ").value.trim(); if (!q) return;
    try {
      const res = await api("/api/geocode?q=" + encodeURIComponent(q));
      $("#wzGeoRes").innerHTML = res.map((r, i) => `<button data-g="${i}">${esc(r.name)}, ${esc([r.admin, r.country].filter(Boolean).join(", "))}</button>`).join("") || '<span class="muted">Ничего не найдено</span>';
      $$("#wzGeoRes [data-g]").forEach((b) => b.onclick = () => { WZ.place = res[+b.dataset.g]; $$("#wzGeoRes [data-g]").forEach((x) => x.classList.toggle("on", x === b)); });
    } catch (err) { $("#wzGeoRes").innerHTML = '<span class="muted">Нет интернета на компьютере — город можно выбрать позже</span>'; }
  };
}

async function finishWizard() {
  const order = ["photo", "work", "fun", "admin"].filter((u) => WZ.usage.has(u));
  const sp = order.map((u) => spaceFromTemplate(u));
  const body = { setup_done: true, usage: order, spaces: sp,
    tabs: ["notes", "mac", "connect", "settings"].concat(WZ.usage.has("photo") && WZ.editor !== "none" ? ["shoots"] : []) };
  if (WZ.usage.has("photo") && WZ.editor === "c1") body.done_rule = WZ.rule;
  if (WZ.usage.has("photo") && WZ.editor === "folders" && WZ.folder.trim())
    body.folder_roots = [...((S.config || {}).folder_roots || []), { path: WZ.folder.trim(), app: WZ.folderApp.trim() || "Папки" }];
  if (WZ.place) body.place = WZ.place;
  if (WZ.skin) body.skin = WZ.skin;
  S = await api("/api/config", body);
  curSpace = sp[0].id; localStorage.setItem("dock_space", curSpace);
  closeWizard(); showTab("home"); toast("TabDock настроен");
}
