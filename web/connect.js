/* TabDock — finding dock servers on the home network (shared by login page and the app).
   Browsers cannot browse Bonjour, so we probe http://<ip>:<port>/api/hello across the /24 subnet.
   The list of known servers lives in localStorage (per origin) and is handed over in the URL hash
   (#servers=…) when jumping to another server, so every server's page knows the others. */
"use strict";
const DockConnect = (() => {
  const KEY = "dock_servers";
  const PORT = 8787;

  function saved() {
    let list = [];
    try { list = JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { list = []; }
    const m = location.hash.match(/servers=([^&]+)/);
    if (m) {
      try {
        const extra = JSON.parse(decodeURIComponent(escape(atob(decodeURIComponent(m[1])))));
        for (const s of extra) if (!list.find((x) => x.base === s.base)) list.push(s);
        localStorage.setItem(KEY, JSON.stringify(list));
      } catch (e) { /* ignore */ }
      history.replaceState(null, "", location.pathname + location.search);
    }
    return list;
  }
  function store(list) { localStorage.setItem(KEY, JSON.stringify(list.slice(0, 20))); }
  function remember(srv) {
    const list = saved().filter((x) => x.base !== srv.base);
    list.unshift({ base: srv.base, name: srv.name, model: srv.model || "", last: Date.now() });
    store(list);
  }
  function forget(base) { store(saved().filter((x) => x.base !== base)); }

  async function probe(base, ms = 1500) {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), ms);
    try {
      const r = await fetch(base + "/api/hello", { signal: ctl.signal, cache: "no-store" });
      const j = await r.json();
      return j && j.app === "tabdock" ? { ...j, base } : null;
    } catch (e) { return null; } finally { clearTimeout(t); }
  }

  function prefixes(extraIps) {
    const set = new Set();
    const add = (ip) => { const m = /^(\d+\.\d+\.\d+)\.\d+$/.exec(ip || ""); if (m) set.add(m[1]); };
    add(location.hostname);
    (extraIps || []).forEach(add);
    saved().forEach((s) => add(new URL(s.base).hostname));
    if (!set.size) ["192.168.1", "192.168.0", "192.168.3"].forEach((p) => set.add(p));
    return [...set];
  }

  // Scan whole /24 subnets; onFound(server) for every dock found; resolves with the list.
  async function scan({ extraIps = [], onFound, onProgress } = {}) {
    const ports = [...new Set([PORT, +location.port || PORT])];
    const targets = [];
    for (const p of prefixes(extraIps)) for (let i = 1; i < 255; i++) for (const port of ports) targets.push(`${location.protocol}//${p}.${i}:${port}`);
    const found = []; let done = 0, idx = 0;
    async function worker() {
      while (idx < targets.length) {
        const base = targets[idx++];
        const r = await probe(base, 1200);
        done++;
        if (onProgress) onProgress(done, targets.length);
        if (r) { found.push(r); if (onFound) onFound(r); }
      }
    }
    await Promise.all(Array.from({ length: 48 }, worker));
    return found;
  }

  function go(base) {
    const payload = encodeURIComponent(btoa(unescape(encodeURIComponent(JSON.stringify(saved())))));
    location.href = base + "/#servers=" + payload;
  }

  return { saved, remember, forget, probe, scan, go, PORT };
})();
