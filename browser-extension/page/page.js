"use strict";

const $ = function (s) { return document.querySelector(s); };

const DEFAULTS = {
  intervalMin: 180,
  browserNotif: true,
  notifyOnDrop: true,
  tgToken: "",
  tgChatId: "",
  tgName: "",
  theme: "auto",
  folders: [],
  wbDest: "-1257786"
};

let items = [];
let settings = Object.assign({}, DEFAULTS);
let currentId = null;
let currentFolder = "__all__";
let refreshTimer = null;
let selected = new Set();
let dragId = null;
let chartData = null;
let chartHover = null;
let armBulkDelete = 0;

function fmt(p, cur) {
  const c = cur || "RUB";
  try {
    return new Intl.NumberFormat(fmtLocale(), {
      style: "currency",
      currency: c,
      minimumFractionDigits: 0,
      maximumFractionDigits: 2
    }).format(p);
  } catch (e) {
    return new Intl.NumberFormat(fmtLocale()).format(p) + " " + c;
  }
}

function storeName(item) {
  if (item.source === "wb") return "Wildberries";
  if (item.source === "ozon") return "Ozon";
  try {
    return new URL(item.url).hostname.replace(/^www\./, "");
  } catch (e) {
    return t("storeGeneric");
  }
}

function baseName(item) {
  return item.customTitle || item.title || t("untitled");
}

function relTime(ts) {
  if (!ts) return t("relNever");
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 90) return t("relJustNow");
  const m = Math.floor(s / 60);
  if (m < 60) return t("relMinsAgo", m);
  const h = Math.floor(m / 60);
  if (h < 24) return t("relHoursAgo", h);
  return new Date(ts).toLocaleDateString(fmtLocale(), { day: "numeric", month: "short" });
}

function changePct(item) {
  const h = item.history || [];
  if (h.length < 2) return null;
  const first = h[0].p;
  const last = h[h.length - 1].p;
  if (!first) return null;
  return ((last - first) / first) * 100;
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

async function loadData() {
  const raw = await browser.storage.local.get({ items: [], settings: {} });
  items = raw.items;
  settings = Object.assign({}, DEFAULTS, raw.settings);
  if (!Array.isArray(settings.folders)) settings.folders = [];
}

async function saveSettings() {
  await browser.runtime.sendMessage({ type: "updateSettings", patch: settings });
}

function bgUpdateItem(id, patch) {
  return browser.runtime.sendMessage({ type: "updateItem", id: id, patch: patch });
}

function bgRemoveItems(ids) {
  return browser.runtime.sendMessage({ type: "removeItems", ids: ids });
}

function bgUpdateSettings(patch) {
  return browser.runtime.sendMessage({ type: "updateSettings", patch: patch });
}

function applyTheme() {
  let t = settings.theme || "auto";
  if (t === "auto") {
    t = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  document.documentElement.setAttribute("data-theme", t);
}

function folderCount(id) {
  if (id === "__all__") return items.length;
  if (id === "__fav__") {
    return items.filter(function (i) { return i.fav; }).length;
  }
  if (id === "__none__") {
    return items.filter(function (i) { return !i.folder; }).length;
  }
  return items.filter(function (i) { return i.folder === id; }).length;
}

function renderSidebar() {
  const nav = $("#folders");
  nav.textContent = "";
  const mk = function (id, label, removable) {
    const row = document.createElement("div");
    row.className = "folder" + (currentFolder === id ? " active" : "");
    const btn = document.createElement("button");
    btn.className = "folder-btn";
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = label;
    const cnt = document.createElement("span");
    cnt.className = "count";
    cnt.textContent = String(folderCount(id));
    btn.appendChild(name);
    btn.appendChild(cnt);
    btn.addEventListener("click", function () {
      currentFolder = id;
      renderSidebar();
      renderList();
    });
    if (id !== "__all__") {
      row.addEventListener("dragover", function (e) {
        if (!dragId) return;
        e.preventDefault();
        row.classList.add("drop");
      });
      row.addEventListener("dragleave", function () {
        row.classList.remove("drop");
      });
      row.addEventListener("drop", function (e) {
        e.preventDefault();
        row.classList.remove("drop");
        dropOnFolder(id);
      });
    }
    row.appendChild(btn);
    if (removable) {
      const del = document.createElement("button");
      del.className = "folder-del";
      del.title = t("deleteFolder");
      del.textContent = "×";
      del.addEventListener("click", async function (e) {
        e.stopPropagation();
        settings.folders = settings.folders.filter(function (f) { return f !== id; });
        if (currentFolder === id) currentFolder = "__all__";
        await bgUpdateSettings({ folders: settings.folders });
        for (const it of items) {
          if (it.folder === id) await bgUpdateItem(it.id, { folder: null });
        }
        await refresh();
      });
      row.appendChild(del);
    }
    nav.appendChild(row);
  };
  mk("__all__", t("allProducts"), false);
  if (items.some(function (i) { return i.fav; })) mk("__fav__", t("favorites"), false);
  for (const f of settings.folders) mk(f, f, true);
  if (settings.folders.length && items.some(function (i) { return !i.folder; })) {
    mk("__none__", t("noFolder"), false);
  }
}

async function addFolder() {
  const inp = $("#new-folder");
  const name = inp.value.trim();
  if (!name || name === "__all__" || name === "__none__") return;
  if (settings.folders.indexOf(name) === -1) {
    const folders = settings.folders.slice();
    folders.push(name);
    folders.sort(function (a, b) { return a.localeCompare(b, "ru"); });
    await bgUpdateSettings({ folders: folders });
  }
  inp.value = "";
  currentFolder = name;
  await refresh();
}

function effOrder(i) {
  return i.order != null ? i.order : i.added || 0;
}

async function dropOnFolder(id) {
  const ids = dragId && selected.has(dragId) ? Array.from(selected) : [dragId];
  dragId = null;
  if (!ids[0]) return;
  for (const itemId of ids) {
    const it = items.find(function (i) { return i.id === itemId; });
    if (!it) continue;
    if (id === "__fav__") {
      if (!it.fav) await bgUpdateItem(it.id, { fav: true });
    } else if (id === "__none__") {
      if (it.folder) await bgUpdateItem(it.id, { folder: null });
    } else if (it.folder !== id) {
      await bgUpdateItem(it.id, { folder: id });
    }
  }
  await refresh();
}

async function reorderItem(targetId, before) {
  const id = dragId;
  dragId = null;
  if (!id || id === targetId) return;
  const sortSel = $("#sort");
  const snapshot = visibleItems().map(function (i) { return i.id; });
  const raw = await browser.storage.local.get({ items: [] });
  const fresh = raw.items;
  const needInit =
    sortSel.value !== "custom" ||
    fresh.some(function (i) { return i.order == null; });
  if (needInit) {
    const rank = {};
    snapshot.forEach(function (fid, n) { rank[fid] = n; });
    const rest = fresh.filter(function (i) { return rank[i.id] == null; });
    rest.sort(function (a, b) { return (a.added || 0) - (b.added || 0); });
    rest.forEach(function (i, n) { rank[i.id] = snapshot.length + n; });
    for (const i of fresh) i.order = (rank[i.id] + 1) * 1000;
  }
  const dragged = fresh.find(function (i) { return i.id === id; });
  const ordered = fresh
    .slice()
    .sort(function (a, b) { return effOrder(a) - effOrder(b); })
    .filter(function (i) { return i.id !== id; });
  const ti = ordered.findIndex(function (i) { return i.id === targetId; });
  if (!dragged || ti === -1) return;
  const pos = before ? ti : ti + 1;
  const prevEl = ordered[pos - 1];
  const nextEl = ordered[pos];
  const lo = prevEl ? effOrder(prevEl) : effOrder(nextEl) - 2000;
  const hi = nextEl ? effOrder(nextEl) : effOrder(prevEl) + 2000;
  dragged.order = (lo + hi) / 2;
  if (needInit) {
    for (const i of fresh) {
      await bgUpdateItem(i.id, { order: i.order });
    }
  } else {
    await bgUpdateItem(id, { order: dragged.order });
  }
  sortSel.value = "custom";
  await refresh();
}

function renderStoreFilter() {
  const sel = $("#store");
  const prev = sel.value;
  sel.textContent = "";
  const names = [];
  for (const it of items) {
    const n = storeName(it);
    if (names.indexOf(n) === -1) names.push(n);
  }
  names.sort(function (a, b) { return a.localeCompare(b, "ru"); });
  const addOpt = function (v, label) {
    const o = document.createElement("option");
    o.value = v;
    o.textContent = label;
    sel.appendChild(o);
  };
  addOpt("all", t("allStores"));
  for (const n of names) addOpt(n, n);
  sel.value = prev && (prev === "all" || names.indexOf(prev) !== -1) ? prev : "all";
}

function visibleItems() {
  let list = items.slice();
  if (currentFolder === "__none__") {
    list = list.filter(function (i) { return !i.folder; });
  } else if (currentFolder === "__fav__") {
    list = list.filter(function (i) { return i.fav; });
  } else if (currentFolder !== "__all__") {
    list = list.filter(function (i) { return i.folder === currentFolder; });
  }
  const store = $("#store").value || "all";
  if (store !== "all") {
    list = list.filter(function (i) { return storeName(i) === store; });
  }
  const q = ($("#search").value || "").trim().toLowerCase();
  if (q) {
    list = list.filter(function (i) {
      return (
        (i.title || "").toLowerCase().indexOf(q) !== -1 ||
        (i.customTitle || "").toLowerCase().indexOf(q) !== -1 ||
        (i.note || "").toLowerCase().indexOf(q) !== -1 ||
        storeName(i).toLowerCase().indexOf(q) !== -1
      );
    });
  }
  const sort = $("#sort").value;
  const by = function (fn, dir) {
    list.sort(function (a, b) {
      const x = fn(a);
      const y = fn(b);
      if (x == null && y == null) return 0;
      if (x == null) return 1;
      if (y == null) return -1;
      if (x < y) return -dir;
      if (x > y) return dir;
      return 0;
    });
  };
  if (sort === "added-asc") by(function (i) { return i.added || 0; }, 1);
  else if (sort === "title") by(function (i) { return (i.title || "").toLowerCase(); }, 1);
  else if (sort === "price-asc") by(function (i) { return i.lastPrice; }, 1);
  else if (sort === "price-desc") by(function (i) { return i.lastPrice; }, -1);
  else if (sort === "change-asc") by(changePct, 1);
  else if (sort === "change-desc") by(changePct, -1);
  else if (sort === "custom") by(effOrder, 1);
  else by(function (i) { return i.added || 0; }, -1);
  if (sort !== "custom") {
    const favs = list.filter(function (i) { return i.fav; });
    if (favs.length && favs.length < list.length) {
      list = favs.concat(list.filter(function (i) { return !i.fav; }));
    }
  }
  return list;
}

function renderList() {
  const box = $("#list");
  const scroll = box.scrollTop;
  box.textContent = "";
  $("#empty").hidden = items.length > 0;
  const list = visibleItems();
  for (const it of list) {
    const row = document.createElement("div");
    row.className =
      "item" +
      (it.id === currentId ? " active" : "") +
      (selected.has(it.id) ? " selected" : "") +
      (it.paused ? " paused" : "");
    row.draggable = true;

    const check = document.createElement("input");
    check.type = "checkbox";
    check.className = "i-check";
    check.checked = selected.has(it.id);
    check.title = t("selectVisible");
    check.addEventListener("click", function (e) { e.stopPropagation(); });
    check.addEventListener("change", function () {
      if (check.checked) selected.add(it.id);
      else selected.delete(it.id);
      renderList();
    });

    const main = document.createElement("div");
    main.className = "i-main";
    const titleEl = document.createElement("div");
    titleEl.className = "i-title";
    titleEl.textContent =
      (it.fav ? "⭐ " : "") +
      (it.emoji ? it.emoji + " " : "") +
      baseName(it);
    const sub = document.createElement("div");
    sub.className = "i-sub muted";
    sub.textContent =
      (it.paused ? t("pauseTag") : "") +
      storeName(it) +
      (it.folder ? " · " + it.folder : "") +
      " · " + relTime(it.lastChecked) +
      (it.lastError ? " · ⚠ " + t("checkFailedShort") : "");
    main.appendChild(titleEl);
    main.appendChild(sub);
    if (it.note) {
      const nt = document.createElement("div");
      nt.className = "i-note muted";
      nt.textContent = "📝 " + it.note;
      nt.title = it.note;
      main.appendChild(nt);
    }

    const right = document.createElement("div");
    right.className = "i-right";
    const pr = document.createElement("div");
    pr.className = "i-price";
    pr.textContent = it.lastPrice != null ? fmt(it.lastPrice, it.currency) : t("dash");
    right.appendChild(pr);
    const pct = changePct(it);
    if (pct != null) {
      const ch = document.createElement("div");
      ch.className = "badge " + (pct < -0.05 ? "down" : pct > 0.05 ? "up" : "flat");
      ch.textContent = (pct > 0 ? "+" : "") + pct.toFixed(1) + "%";
      right.appendChild(ch);
    }
    if (it.target != null) {
      const tg = document.createElement("div");
      tg.className = "i-target muted";
      tg.textContent = t("goalPrefix") + fmt(it.target, it.currency);
      right.appendChild(tg);
    }

    const acts = document.createElement("div");
    acts.className = "i-actions";
    const mkAct = function (label, title, handler) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "act-btn";
      b.textContent = label;
      b.title = title;
      b.addEventListener("click", function (e) {
        e.stopPropagation();
        handler(b);
      });
      acts.appendChild(b);
      return b;
    };
    const favBtn = mkAct("★", it.fav ? t("favRemove") : t("favAdd"), async function () {
      await bgUpdateItem(it.id, { fav: !it.fav });
      await refresh();
    });
    if (it.fav) favBtn.classList.add("on");
    const pauseBtn = mkAct("⏸", it.paused ? t("pauseResume") : t("pauseTitle"), async function () {
      await bgUpdateItem(it.id, { paused: !it.paused });
      await refresh();
    });
    if (it.paused) pauseBtn.classList.add("on");
    mkAct("↻", t("checkOne"), async function (b) {
      b.disabled = true;
      await browser.runtime
        .sendMessage({ type: "checkOne", id: it.id })
        .catch(function () { return null; });
      await refresh();
    });
    mkAct("↗", t("openStoreShort"), function () {
      browser.tabs.create({ url: it.url });
    });
    mkAct("×", t("untrack"), async function (b) {
      if (b.dataset.arm !== "1") {
        b.dataset.arm = "1";
        b.textContent = t("confirmUntrackShort");
        b.classList.add("danger-act");
        setTimeout(function () {
          b.dataset.arm = "";
          b.textContent = "×";
          b.classList.remove("danger-act");
        }, 3000);
        return;
      }
      if (currentId === it.id) {
        currentId = null;
        $("#detail").hidden = true;
      }
      selected.delete(it.id);
      await bgRemoveItems([it.id]);
      await refresh();
    });

    row.appendChild(check);
    row.appendChild(main);
    row.appendChild(right);
    row.appendChild(acts);
    row.addEventListener("click", function () {
      currentId = it.id;
      renderList();
      renderDetail();
    });

    row.addEventListener("dragstart", function (e) {
      dragId = it.id;
      row.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", it.id);
    });
    row.addEventListener("dragend", function () {
      dragId = null;
      row.classList.remove("dragging");
      renderList();
    });
    row.addEventListener("dragover", function (e) {
      if (!dragId || dragId === it.id) return;
      e.preventDefault();
      const r = row.getBoundingClientRect();
      const above = e.clientY < r.top + r.height / 2;
      row.classList.toggle("drop-above", above);
      row.classList.toggle("drop-below", !above);
    });
    row.addEventListener("dragleave", function () {
      row.classList.remove("drop-above", "drop-below");
    });
    row.addEventListener("drop", function (e) {
      e.preventDefault();
      const r = row.getBoundingClientRect();
      const before = e.clientY < r.top + r.height / 2;
      row.classList.remove("drop-above", "drop-below");
      reorderItem(it.id, before);
    });

    box.appendChild(row);
  }
  if (!list.length && items.length) {
    const d = document.createElement("div");
    d.className = "muted pad";
    d.textContent = t("noFilterMatch");
    box.appendChild(d);
  }
  box.scrollTop = scroll;
  updateBulkbar();
}

function updateBulkbar() {
  $("#list").classList.toggle("has-selection", selected.size > 0);
  const bar = $("#bulkbar");
  bar.hidden = selected.size === 0;
  if (bar.hidden) return;
  $("#bulk-count").textContent = t("bulkSelected", selected.size);
  const sel = $("#bulk-folder");
  if (document.activeElement === sel) return;
  const prev = sel.value;
  sel.textContent = "";
  const addOpt = function (v, label) {
    const o = document.createElement("option");
    o.value = v;
    o.textContent = label;
    sel.appendChild(o);
  };
  addOpt("", t("noFolder"));
  for (const f of settings.folders) addOpt(f, f);
  if (prev === "" || settings.folders.indexOf(prev) !== -1) sel.value = prev;
}

function renderFolderSelect(it) {
  const sel = $("#d-folder");
  if (document.activeElement === sel) return;
  sel.textContent = "";
  const addOpt = function (v, label) {
    const o = document.createElement("option");
    o.value = v;
    o.textContent = label;
    sel.appendChild(o);
  };
  addOpt("", t("noFolder"));
  for (const f of settings.folders) addOpt(f, f);
  sel.value = it.folder && settings.folders.indexOf(it.folder) !== -1 ? it.folder : "";
}

function renderStats(it) {
  const box = $("#d-stats");
  box.textContent = "";
  const h = it.history || [];
  if (!h.length) return;
  let min = Infinity;
  let max = -Infinity;
  for (const pt of h) {
    if (pt.p < min) min = pt.p;
    if (pt.p > max) max = pt.p;
  }
  const mk = function (label, value) {
    const d = document.createElement("div");
    d.className = "stat";
    const l = document.createElement("div");
    l.className = "muted";
    l.textContent = label;
    const v = document.createElement("div");
    v.textContent = value;
    d.appendChild(l);
    d.appendChild(v);
    box.appendChild(d);
  };
  mk(t("statMin"), fmt(min, it.currency));
  mk(t("statMax"), fmt(max, it.currency));
  mk(t("statCount"), String(h.length));
}

function drawChart(it, hover) {
  const c = $("#d-chart");
  const dpr = window.devicePixelRatio || 1;
  const W = c.clientWidth || 380;
  const H = c.clientHeight || 230;
  c.width = Math.round(W * dpr);
  c.height = Math.round(H * dpr);
  const ctx = c.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);
  const h = it.history || [];
  const note = $("#d-note");
  if (h.length < 2) {
    chartData = null;
    $("#chart-tip").hidden = true;
    note.textContent = h.length
      ? t("chartOnePointPage")
      : t("chartNoHistory");
    return;
  }
  note.textContent =
    new Date(h[0].t).toLocaleDateString(fmtLocale()) +
    " — " +
    new Date(h[h.length - 1].t).toLocaleDateString(fmtLocale()) +
    " · " + t("samples", h.length);
  let min = Infinity;
  let max = -Infinity;
  for (const pt of h) {
    if (pt.p < min) min = pt.p;
    if (pt.p > max) max = pt.p;
  }
  if (it.target != null) {
    if (it.target < min) min = it.target;
    if (it.target > max) max = it.target;
  }
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const padL = 10;
  const padR = 10;
  const padT = 18;
  const padB = 10;
  const t0 = h[0].t;
  const t1 = h[h.length - 1].t;
  const x = function (t) {
    return padL + ((t - t0) / Math.max(1, t1 - t0)) * (W - padL - padR);
  };
  const y = function (p) {
    return padT + (1 - (p - min) / (max - min)) * (H - padT - padB);
  };
  const pts = h.map(function (pt) {
    return { x: x(pt.t), y: y(pt.p), t: pt.t, p: pt.p };
  });
  chartData = { it: it, pts: pts };
  if (hover == null) chartHover = null;
  const line = cssVar("--accent") || "#2783DE";
  ctx.beginPath();
  ctx.moveTo(x(h[0].t), y(h[0].p));
  for (let i = 1; i < h.length; i++) {
    ctx.lineTo(x(h[i].t), y(h[i - 1].p));
    ctx.lineTo(x(h[i].t), y(h[i].p));
  }
  ctx.lineTo(W - padR, y(h[h.length - 1].p));
  ctx.strokeStyle = line;
  ctx.lineWidth = 2;
  ctx.lineJoin = "round";
  ctx.stroke();
  ctx.lineTo(W - padR, H - padB);
  ctx.lineTo(padL, H - padB);
  ctx.closePath();
  ctx.fillStyle = line + "22";
  ctx.fill();
  if (it.target != null) {
    ctx.beginPath();
    ctx.setLineDash([5, 4]);
    ctx.moveTo(padL, y(it.target));
    ctx.lineTo(W - padR, y(it.target));
    ctx.strokeStyle = cssVar("--ok") || "#2e9e5b";
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.setLineDash([]);
  }
  ctx.fillStyle = cssVar("--muted") || "#888";
  ctx.font = "11px sans-serif";
  ctx.fillText(fmt(max, it.currency), padL + 2, padT - 5);
  ctx.fillText(fmt(min, it.currency), padL + 2, H - padB - 4);
  if (hover != null && pts[hover]) {
    const hp = pts[hover];
    ctx.beginPath();
    ctx.setLineDash([3, 3]);
    ctx.moveTo(hp.x, padT);
    ctx.lineTo(hp.x, H - padB);
    ctx.strokeStyle = cssVar("--muted") || "#888";
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.arc(hp.x, hp.y, 4, 0, Math.PI * 2);
    ctx.fillStyle = line;
    ctx.fill();
    ctx.strokeStyle = cssVar("--panel") || "#fff";
    ctx.lineWidth = 2;
    ctx.stroke();
  }
}

function renderDetail() {
  const panel = $("#detail");
  const it = items.find(function (x) { return x.id === currentId; });
  if (!it) {
    currentId = null;
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  const a = $("#d-title");
  a.textContent = (it.emoji ? it.emoji + " " : "") + baseName(it);
  a.href = it.url;
  const favB = $("#d-fav");
  favB.classList.toggle("on", Boolean(it.fav));
  favB.title = it.fav ? t("favRemove") : t("favAdd");
  const pB = $("#d-pause");
  pB.classList.toggle("on", Boolean(it.paused));
  pB.title = it.paused ? t("pauseOnDetail") : t("pauseTitle");
  $("#d-store").textContent =
    (it.paused ? t("pauseOnPage") : "") +
    storeName(it) +
    " · " + t("addedAt", new Date(it.added).toLocaleDateString(fmtLocale())) +
    " · " + t("checkedAt", relTime(it.lastChecked));
  $("#d-price").textContent = it.lastPrice != null ? fmt(it.lastPrice, it.currency) : t("noPriceData");
  const pct = changePct(it);
  const ch = $("#d-change");
  if (pct != null) {
    ch.hidden = false;
    ch.className = "badge " + (pct < -0.05 ? "down" : pct > 0.05 ? "up" : "flat");
    ch.textContent = t("sinceTracking", (pct > 0 ? "+" : "") + pct.toFixed(1));
  } else {
    ch.hidden = true;
  }
  if (document.activeElement !== $("#d-target")) {
    $("#d-target").value = it.target != null ? String(it.target) : "";
  }
  if (document.activeElement !== $("#d-emoji")) {
    $("#d-emoji").value = it.emoji || "";
  }
  if (document.activeElement !== $("#d-name")) {
    $("#d-name").value = it.customTitle || "";
  }
  if (document.activeElement !== $("#d-note-text")) {
    $("#d-note-text").value = it.note || "";
  }
  renderFolderSelect(it);
  renderStats(it);
  drawChart(it);
  const errEl = $("#d-error");
  if (it.lastError) {
    errEl.hidden = false;
    errEl.textContent = t("checkFailedNote", t(it.lastError));
  } else {
    errEl.hidden = true;
  }
}

function renderWbDest() {
  const inp = $("#wb-dest");
  if (!inp || document.activeElement === inp) return;
  inp.value = settings.wbDest || "-1257786";
}

function renderAll() {
  applyTheme();
  renderSidebar();
  renderWbDest();
  renderStoreFilter();
  renderList();
  renderDetail();
  $("#version").textContent = t("versionFoot", browser.runtime.getManifest().version);
}

async function refresh() {
  await loadData();
  selected = new Set(
    Array.from(selected).filter(function (id) {
      return items.some(function (i) { return i.id === id; });
    })
  );
  renderAll();
}

browser.storage.onChanged.addListener(function (changes, area) {
  if (area !== "local") return;
  if (!changes.items && !changes.settings) return;
  if (refreshTimer) clearTimeout(refreshTimer);
  refreshTimer = setTimeout(function () {
    refreshTimer = null;
    refresh();
  }, 150);
});

window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyTheme);
window.addEventListener("resize", function () {
  if (currentId) renderDetail();
});

$("#search").addEventListener("input", renderList);
$("#sort").addEventListener("change", renderList);
$("#store").addEventListener("change", renderList);

$("#btn-add-folder").addEventListener("click", addFolder);
$("#wb-dest").addEventListener("change", async function () {
  const v = $("#wb-dest").value.trim();
  settings.wbDest = v || "-1257786";
  await bgUpdateSettings({ wbDest: settings.wbDest });
});
$("#new-folder").addEventListener("keydown", function (e) {
  if (e.key === "Enter") addFolder();
});

$("#btn-check").addEventListener("click", async function () {
  const b = $("#btn-check");
  if (b.disabled) return;
  b.disabled = true;
  b.textContent = t("checking");
  try {
    await browser.runtime.sendMessage({ type: "checkNow" }).catch(function () { return null; });
    await refresh();
  } finally {
    b.disabled = false;
    b.textContent = t("checkAll");
  }
});

$("#btn-select").addEventListener("click", function () {
  const vis = visibleItems();
  const all = vis.length && vis.every(function (i) { return selected.has(i.id); });
  if (all) selected.clear();
  else for (const i of vis) selected.add(i.id);
  renderList();
});

$("#bulk-cancel").addEventListener("click", function () {
  selected.clear();
  renderList();
});

$("#bulk-move").addEventListener("click", async function () {
  const folder = $("#bulk-folder").value || null;
  const ids = Array.from(selected);
  for (const itemId of ids) {
    const it = items.find(function (i) { return i.id === itemId; });
    if (it && it.folder !== folder) await bgUpdateItem(itemId, { folder: folder });
  }
  selected.clear();
  await refresh();
});

$("#bulk-check").addEventListener("click", async function () {
  const b = $("#bulk-check");
  if (b.disabled) return;
  b.disabled = true;
  const ids = Array.from(selected);
  let n = 0;
  try {
    for (const id of ids) {
      n++;
      b.textContent = t("bulkUpdating", n, ids.length);
      await browser.runtime
        .sendMessage({ type: "checkOne", id: id })
        .catch(function () { return null; });
    }
  } finally {
    b.disabled = false;
    b.textContent = t("bulkRefresh");
  }
  await refresh();
});

$("#bulk-delete").addEventListener("click", async function () {
  const b = $("#bulk-delete");
  if (Date.now() - armBulkDelete > 3000) {
    armBulkDelete = Date.now();
    b.textContent = t("confirmUntrack");
    setTimeout(function () {
      b.textContent = t("untrack");
      armBulkDelete = 0;
    }, 3000);
    return;
  }
  armBulkDelete = 0;
  b.textContent = t("untrack");
  const ids = Array.from(selected);
  selected.clear();
  if (ids.indexOf(currentId) !== -1) {
    currentId = null;
    $("#detail").hidden = true;
  }
  await bgRemoveItems(ids);
  await refresh();
});

$("#d-fav").addEventListener("click", async function () {
  if (!currentId) return;
  const it = items.find(function (x) { return x.id === currentId; });
  if (!it) return;
  await bgUpdateItem(currentId, { fav: !it.fav });
  await refresh();
});

$("#d-pause").addEventListener("click", async function () {
  if (!currentId) return;
  const it = items.find(function (x) { return x.id === currentId; });
  if (!it) return;
  await bgUpdateItem(currentId, { paused: !it.paused });
  await refresh();
});

$("#d-chart").addEventListener("mousemove", function (e) {
  if (!chartData) return;
  const rect = e.target.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  let best = 0;
  let bestD = Infinity;
  chartData.pts.forEach(function (pt, i) {
    const d = Math.abs(pt.x - mx);
    if (d < bestD) { bestD = d; best = i; }
  });
  if (best !== chartHover) {
    chartHover = best;
    drawChart(chartData.it, best);
  }
  const tip = $("#chart-tip");
  const pt = chartData.pts[best];
  tip.hidden = false;
  tip.textContent =
    new Date(pt.t).toLocaleString(fmtLocale(), {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit"
    }) + " · " + fmt(pt.p, chartData.it.currency);
  const ww = $("#chart-wrap").clientWidth;
  tip.style.top = Math.max(4, pt.y - 32) + "px";
  tip.style.left = "0px";
  let lx = pt.x + 10;
  if (lx + tip.offsetWidth > ww - 4) lx = pt.x - tip.offsetWidth - 10;
  tip.style.left = Math.max(4, lx) + "px";
});

$("#d-chart").addEventListener("mouseleave", function () {
  if (chartHover != null && chartData) {
    chartHover = null;
    drawChart(chartData.it);
  }
  $("#chart-tip").hidden = true;
});

$("#d-close").addEventListener("click", function () {
  currentId = null;
  $("#detail").hidden = true;
  renderList();
});

$("#d-refresh").addEventListener("click", async function () {
  const b = $("#d-refresh");
  if (!currentId || b.classList.contains("spin")) return;
  b.classList.add("spin");
  let res = null;
  try {
    res = await browser.runtime
      .sendMessage({ type: "checkOne", id: currentId })
      .catch(function () { return null; });
    await refresh();
  } finally {
    b.classList.remove("spin");
  }
  if (!res || !res.ok) {
    $("#d-note").textContent = (res && res.error) || t("updateFailed");
  }
});

$("#d-save").addEventListener("click", async function () {
  if (!currentId) return;
  const raw = $("#d-target").value.trim().replace(",", ".");
  let target = null;
  if (raw) {
    const n = parseFloat(raw);
    if (!isFinite(n) || n <= 0) {
      $("#d-note").textContent = t("invalidTarget");
      return;
    }
    target = Math.round(n * 100) / 100;
  }
  const folder = $("#d-folder").value || null;
  const emoji = $("#d-emoji").value.trim();
  const name = $("#d-name").value.trim();
  const note = $("#d-note-text").value.trim();
  await bgUpdateItem(currentId, {
    target: target,
    folder: folder,
    emoji: emoji || null,
    customTitle: name || null,
    note: note || null
  });
  const b = $("#d-save");
  b.textContent = "✓";
  setTimeout(function () {
    b.textContent = t("save");
  }, 900);
  await refresh();
});

let armDelete = 0;
$("#d-delete").addEventListener("click", async function () {
  const b = $("#d-delete");
  if (Date.now() - armDelete > 3000) {
    armDelete = Date.now();
    b.textContent = t("deleteConfirm");
    setTimeout(function () {
      if (armDelete) b.textContent = t("delete");
      armDelete = 0;
    }, 3000);
    return;
  }
  const id = currentId;
  currentId = null;
  armDelete = 0;
  b.textContent = t("delete");
  $("#detail").hidden = true;
  await bgRemoveItems([id]);
  await refresh();
});

document.documentElement.lang = uiLocale();
document.title = t("pageTitle");
applyDom();
refresh();