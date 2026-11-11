"use strict";

const DEFAULTS = {
  intervalMin: 180,
  browserNotif: true,
  notifyOnDrop: true,
  tgToken: "",
  tgChatId: "",
  tgName: "",
  theme: "auto",
  notifyPctDrop: 0,
  wbDest: "-1257786"
};

let items = [];
let settings = Object.assign({}, DEFAULTS);
let currentId = null;
let refreshTimer = null;

function bgUpdateItem(id, patch) {
  return browser.runtime.sendMessage({ type: "updateItem", id: id, patch: patch });
}

function bgRemoveItems(ids) {
  return browser.runtime.sendMessage({ type: "removeItems", ids: ids });
}

function bgClearItems() {
  return browser.runtime.sendMessage({ type: "clearItems" });
}

const $ = (sel) => document.querySelector(sel);

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

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

function curSymbol(cur) {
  const c = cur || "RUB";
  try {
    const parts = new Intl.NumberFormat(fmtLocale(), { style: "currency", currency: c }).formatToParts(0);
    const part = parts.find((x) => x.type === "currency");
    return part ? part.value : c;
  } catch (e) {
    return c;
  }
}

function storeName(item) {
  if (item.source === "wb") return "WB";
  if (item.source === "ozon") return "Ozon";
  if (item.source === "web") {
    try {
      return new URL(item.url).hostname.replace(/^www\./, "");
    } catch (e) {
      return t("storeGeneric");
    }
  }
  return item.source;
}

function dispName(item) {
  return (
    (item.paused ? t("pausePrefix") : "") +
    (item.emoji ? item.emoji + " " : "") +
    (item.customTitle || item.title || t("untitled"))
  );
}

function relTime(ts) {
  if (!ts) return t("dash");
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 90) return t("relJustNow");
  const m = Math.floor(s / 60);
  if (m < 60) return t("relMinsAgo", m);
  const h = Math.floor(m / 60);
  if (h < 24) return t("relHoursAgo", h);
  return new Date(ts).toLocaleDateString(fmtLocale(), { day: "numeric", month: "short" });
}

function deltaPct(item) {
  const h = item.history;
  if (!h || h.length < 2) return 0;
  const win = h.slice(-30);
  const first = win[0].p;
  const last = win[win.length - 1].p;
  if (!first) return 0;
  return ((last - first) / first) * 100;
}

function isDark() {
  const t = settings.theme || "auto";
  if (t === "dark") return true;
  if (t === "light") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyTheme() {
  document.body.dataset.theme = isDark() ? "dark" : "light";
}

window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
  if ((settings.theme || "auto") === "auto") {
    applyTheme();
    renderMain();
  }
});

function svgEl(name, attrs) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", name);
  if (attrs) {
    Object.keys(attrs).forEach(function (key) {
      el.setAttribute(key, attrs[key]);
    });
  }
  return el;
}

function renderSpark(item) {
  const pts = (item.history || []).slice(-30);
  const w = 48;
  const h = 24;
  let color = isDark() ? "#6e6b66" : "#B8B5B0";
  const d = deltaPct(item);
  if (d < -0.5) color = "#46A171";
  else if (d > 0.5) color = "#E56458";
  let points;
  if (pts.length < 2) {
    points = "2," + h / 2 + " " + (w - 2) + "," + h / 2;
  } else {
    const vals = pts.map((x) => x.p);
    const min = Math.min.apply(null, vals);
    const max = Math.max.apply(null, vals);
    const span = max - min || 1;
    const step = (w - 4) / (pts.length - 1);
    points = pts
      .map(function (x, i) {
        const px = (2 + i * step).toFixed(1);
        const py = (h - 3 - ((x.p - min) / span) * (h - 6)).toFixed(1);
        return px + "," + py;
      })
      .join(" ");
  }
  const svg = svgEl("svg", {
    class: "spark",
    width: String(w),
    height: String(h),
    viewBox: "0 0 " + w + " " + h
  });
  svg.appendChild(
    svgEl("polyline", {
      points: points,
      fill: "none",
      stroke: color,
      "stroke-width": "1.8",
      "stroke-linecap": "round",
      "stroke-linejoin": "round"
    })
  );
  return svg;
}

function renderChart(item) {
  const pts = (item.history || []).slice(-60);
  const w = 316;
  const h = 148;
  if (pts.length < 2) {
    const note = document.createElement("div");
    note.className = "bar-note";
    note.textContent = t("chartOnePoint");
    return note;
  }
  const vals = pts.map((x) => x.p);
  const min = Math.min.apply(null, vals);
  const max = Math.max.apply(null, vals);
  const span = max - min || 1;
  const step = (w - 16) / (pts.length - 1);
  const coords = pts.map(function (x, i) {
    const px = 8 + i * step;
    const py = 14 + (1 - (x.p - min) / span) * (h - 34);
    return [px, py];
  });
  const line = coords.map((c) => c[0].toFixed(1) + "," + c[1].toFixed(1)).join(" ");
  const grid = isDark() ? "#3a3a3a" : "#F0EFED";
  const areaFill = isDark() ? "#1e3a55" : "#E5F2FC";
  const dotStroke = isDark() ? "#1f1f1f" : "#fff";
  const last = coords[coords.length - 1];
  const area =
    "M" + line + " L" + last[0].toFixed(1) + "," + (h - 4) + " 8," + (h - 4) + " Z";
  const svg = svgEl("svg", {
    width: "100%",
    height: String(h),
    viewBox: "0 0 " + w + " " + h,
    preserveAspectRatio: "none",
    "aria-label": t("chartAria")
  });
  svg.appendChild(svgEl("line", { x1: "0", y1: "38", x2: String(w), y2: "38", stroke: grid }));
  svg.appendChild(svgEl("line", { x1: "0", y1: "76", x2: String(w), y2: "76", stroke: grid }));
  svg.appendChild(svgEl("line", { x1: "0", y1: "114", x2: String(w), y2: "114", stroke: grid }));
  svg.appendChild(svgEl("path", { d: area, fill: areaFill }));
  svg.appendChild(
    svgEl("polyline", {
      points: line,
      fill: "none",
      stroke: "#2783DE",
      "stroke-width": "2.2",
      "stroke-linecap": "round",
      "stroke-linejoin": "round"
    })
  );
  svg.appendChild(
    svgEl("circle", {
      cx: last[0].toFixed(1),
      cy: last[1].toFixed(1),
      r: "4",
      fill: "#2783DE",
      stroke: dotStroke,
      "stroke-width": "1.6"
    })
  );
  return svg;
}

async function load() {
  const raw = await browser.storage.local.get({ items: [], settings: {} });
  items = raw.items;
  settings = Object.assign({}, DEFAULTS, raw.settings);
  applyTheme();
  renderMain();
  renderSettings();
}

function showScreen(id) {
  ["scr-main", "scr-detail", "scr-settings"].forEach(function (s) {
    document.getElementById(s).hidden = s !== id;
  });
}

function renderMain() {
  const list = $("#list");
  list.textContent = "";
  $("#count").hidden = items.length === 0;
  $("#count").textContent = String(items.length);
  $("#empty").hidden = items.length > 0;
  list.hidden = items.length === 0;

  if (items.length > 0) {
    const latest = Math.max.apply(null, items.map((x) => x.lastChecked || 0));
    $("#sub-text").textContent = t("relChecked", relTime(latest));
  } else {
    $("#sub-text").textContent = t("relLocalOnly");
  }

  const sorted = items.slice().sort((a, b) => (b.added || 0) - (a.added || 0));
  for (const item of sorted) {
    const row = el("button", "item");
    row.type = "button";

    const mid = el("div", "item-mid");
    mid.appendChild(el("div", "item-title", dispName(item)));
    const meta = el("div", "item-meta");
    meta.appendChild(el("span", "chip", storeName(item)));
    if (item.target != null) {
      meta.appendChild(el("span", "goal", t("goalPrefix") + fmt(item.target, item.currency)));
    }
    if (item.lastError) {
      const err = el("span", "chip", "⚠");
      err.style.color = "var(--red)";
      err.title = t(item.lastError);
      meta.appendChild(err);
    }
    mid.appendChild(meta);

    const right = el("div", "item-right");
    right.appendChild(el("span", "price", fmt(item.lastPrice, item.currency)));
    const d = deltaPct(item);
    const cls = d < -0.5 ? "down" : d > 0.5 ? "up" : "flat";
    const sign = d > 0 ? "+" : "\u2212";
    const txt = Math.abs(d) < 0.5 ? "0%" : sign + Math.abs(Math.round(d)) + "%";
    right.appendChild(el("span", "delta " + cls, txt));

    const sparkWrap = el("span", "spark-wrap");
    sparkWrap.replaceChildren(renderSpark(item));

    row.appendChild(mid);
    row.appendChild(right);
    row.appendChild(sparkWrap);
    row.addEventListener("click", function () {
      openDetail(item.id);
    });
    list.appendChild(row);
  }
}

function honesty(item) {
  const h = item.history || [];
  if (h.length < 5) return null;
  const cur = item.lastPrice;
  const notBelow = h.filter((x) => x.p >= cur).length / h.length;
  const pct = Math.round(notBelow * 100);
  if (notBelow >= 0.75) {
    return {
      good: true,
      title: t("honestGoodTitle"),
      text: t("honestGoodText", pct)
    };
  }
  return {
    good: false,
    title: t("honestBadTitle"),
    text: t("honestBadText", 100 - pct)
  };
}

function openDetail(id) {
  const item = items.find((x) => x.id === id);
  if (!item) return;
  currentId = id;

  $("#d-title").textContent = dispName(item);
  $("#d-store").textContent =
    item.source === "wb" ? "Wildberries" : item.source === "ozon" ? "Ozon" : storeName(item);
  $("#d-added").textContent =
    t("addedOn", new Date(item.added).toLocaleDateString(fmtLocale(), { day: "numeric", month: "short" }));
  $("#d-price").textContent = fmt(item.lastPrice, item.currency);
  $("#d-target-cur").textContent = curSymbol(item.currency);

  const d = deltaPct(item);
  const dl = $("#d-delta");
  const cls = d < -0.5 ? "down" : d > 0.5 ? "up" : "flat";
  dl.className = "delta " + cls;
  const sign = d > 0 ? "+" : "\u2212";
  const pctStr = sign + Math.abs(Math.round(d));
  dl.textContent = Math.abs(d) < 0.5 ? t("noChange") : t("deltaPeriod", pctStr);

  $("#d-target").value = item.target != null ? String(item.target) : "";
  renderTargetBar(item);

  $("#d-chart").replaceChildren(renderChart(item));
  const h = item.history || [];
  const vals = h.map((x) => x.p);
  $("#d-chart-note").textContent = t("samples", h.length);
  if (vals.length) {
    $("#d-min").textContent = fmt(Math.min.apply(null, vals), item.currency);
    $("#d-max").textContent = fmt(Math.max.apply(null, vals), item.currency);
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    $("#d-avg").textContent = fmt(Math.round(avg * 100) / 100, item.currency);
  }

  const verdict = honesty(item);
  const hv = $("#d-honest");
  if (verdict) {
    hv.hidden = false;
    hv.classList.toggle("warn", !verdict.good);
    $("#d-honest-title").textContent = verdict.title;
    $("#d-honest-text").textContent = verdict.text;
  } else {
    hv.hidden = true;
  }

  const errEl = $("#d-error");
  if (item.lastError) {
    errEl.hidden = false;
    errEl.textContent = t("checkFailedNote", t(item.lastError));
  } else {
    errEl.hidden = true;
  }

  showScreen("scr-detail");
}

function renderTargetBar(item) {
  const wrap = $("#d-bar-wrap");
  const note = $("#d-bar-note");
  if (item.target == null || !item.history || !item.history.length) {
    wrap.hidden = true;
    note.hidden = true;
    return;
  }
  const start = item.history[0].p;
  const cur = item.lastPrice;
  const target = item.target;
  wrap.hidden = false;
  note.hidden = false;
  if (cur <= target) {
    $("#d-bar").style.width = "100%";
    note.textContent = t("targetReached", fmt(cur, item.currency), fmt(target, item.currency));
    return;
  }
  let progress = 0;
  if (start > target) {
    progress = Math.max(0, Math.min(1, (start - cur) / (start - target)));
  }
  $("#d-bar").style.width = Math.round(progress * 100) + "%";
  note.textContent = t("targetLeft", fmt(Math.round((cur - target) * 100) / 100, item.currency));
}

function renderToggle(btn, on) {
  btn.classList.toggle("off", !on);
}

function renderSettings() {
  renderToggle($("#set-bnotif"), settings.browserNotif);
  renderToggle($("#set-drop"), settings.notifyOnDrop);
  $("#set-interval").value = String(settings.intervalMin);
  $("#set-pct").value = String(settings.notifyPctDrop || 0);
  $("#set-theme").value = settings.theme || "auto";
  $("#tg-token").value = settings.tgToken;
  renderTgStatus();
}

function renderTgStatus() {
  const connected = Boolean(settings.tgToken && settings.tgChatId);
  $("#tg-dot").hidden = !connected;
  $("#tg-status").textContent = connected ? t("tgConnected") : t("tgDisconnected");
  $("#tg-substatus").textContent = connected
    ? t("tgSubConnected", settings.tgName || t("tgChat", settings.tgChatId))
    : t("tgSubDisconnected");
  $("#tg-test").hidden = !connected;
}

async function saveSettings() {
  await browser.runtime.sendMessage({ type: "updateSettings", patch: settings });
}

function parseLink(text) {
  const s = String(text).trim();
  let m = s.match(/wildberries\.[a-z]+\/catalog\/(\d+)/i);
  if (m) return { source: "wb", pid: m[1] };
  m = s.match(/ozon\.[a-z]+\/product\/(?:[^\/?#\s]*-)?(\d{5,})/i);
  if (m) return { source: "ozon", pid: m[1] };
  m = s.match(/^(\d{5,12})$/);
  if (m) return { source: "wb", pid: m[1] };
  if (/^https?:\/\/\S+$/i.test(s)) return { source: "web", url: s };
  return null;
}

async function init() {
  document.documentElement.lang = uiLocale();
  applyDom();
  await load();
  const fusion = await browser.storage.local.get({ fusionUrl: "http://localhost:8080" });
  $("#fusion-url").value = fusion.fusionUrl;
  $("#fusion-url").addEventListener("change", async function () {
    await browser.storage.local.set({ fusionUrl: $("#fusion-url").value.trim() });
  });
  $("#fusion-search").addEventListener("click", async function () {
    const raw = $("#fusion-url").value.trim();
    let base;
    try {
      base = new URL(raw);
      if (!["http:", "https:"].includes(base.protocol) || base.username || base.password) throw new Error();
      if (base.protocol !== "https:" && !["localhost", "127.0.0.1"].includes(base.hostname)) throw new Error();
    } catch (_) {
      $("#fusion-url").setCustomValidity("Укажите HTTPS-адрес MarketFusion или локальный http://localhost:8080");
      $("#fusion-url").reportValidity();
      return;
    }
    $("#fusion-url").setCustomValidity("");
    await browser.storage.local.set({ fusionUrl: base.origin });
    const tabs = await browser.tabs.query({ active: true, currentWindow: true });
    const query = (tabs[0] && tabs[0].title || "").split(/[|–—]/)[0].trim();
    if (!query) { $("#fusion-search").textContent = "Откройте страницу товара"; return; }
    base.pathname = "/";
    base.search = "";
    base.hash = "";
    base.searchParams.set("q", query);
    await browser.tabs.create({ url: base.toString() });
  });
  $("#version").textContent = t("versionFootPopup", browser.runtime.getManifest().version);

  $("#btn-settings").addEventListener("click", function () {
    showScreen("scr-settings");
  });
  $("#btn-back-detail").addEventListener("click", function () {
    renderMain();
    showScreen("scr-main");
  });
  $("#btn-back-settings").addEventListener("click", function () {
    renderMain();
    showScreen("scr-main");
  });

  $("#btn-refresh").addEventListener("click", async function () {
    const b = $("#btn-refresh");
    if (b.classList.contains("spin")) return;
    b.classList.add("spin");
    try {
      await browser.runtime.sendMessage({ type: "checkNow" });
      await load();
    } finally {
      b.classList.remove("spin");
    }
  });

  $("#btn-page").addEventListener("click", function () {
    browser.tabs.create({ url: browser.runtime.getURL("page/index.html") });
    window.close();
  });

  $("#btn-pick").addEventListener("click", async function () {
    const tabs = await browser.tabs.query({ active: true, currentWindow: true }).catch(function () { return []; });
    const tab = tabs && tabs[0];
    const ok = tab
      ? await browser.tabs.sendMessage(tab.id, { type: "startPicker" }).catch(function () { return null; })
      : null;
    if (ok) {
      window.close();
    } else {
      $("#sub-text").textContent = t("pickUnavailable");
    }
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
      await load();
      if (currentId) openDetail(currentId);
    } finally {
      b.classList.remove("spin");
    }
    if (!res || !res.ok) {
      $("#d-chart-note").textContent = (res && res.error) || t("updateFailed");
    }
  });

  $("#add-btn").addEventListener("click", async function () {
    const input = $("#add-input");
    const parsed = parseLink(input.value.trim());
    if (!parsed) {
      input.value = "";
      input.placeholder = t("pasteLinkPlaceholder");
      return;
    }
    const btn = $("#add-btn");
    btn.disabled = true;
    btn.textContent = "…";
    const res = await browser.runtime
      .sendMessage({ type: "addItem", source: parsed.source, pid: parsed.pid || null, url: parsed.url || null, titleHint: null, priceHint: null })
      .catch(() => null);
    btn.disabled = false;
    btn.textContent = t("trackBtn");
    if (res && res.ok) {
      input.value = "";
      input.placeholder = t("addLinkPlaceholder");
      await load();
    } else {
      input.placeholder = (res && res.error) || t("addLinkFail");
      input.value = "";
    }
  });

  $("#add-input").addEventListener("keydown", function (e) {
    if (e.key === "Enter") $("#add-btn").click();
  });

  $("#d-target-save").addEventListener("click", async function () {
    const item = items.find((x) => x.id === currentId);
    if (!item) return;
    const v = $("#d-target").value.trim().replace(",", ".");
    const n = parseFloat(v);
    const target = v && isFinite(n) && n > 0 ? Math.round(n * 100) / 100 : null;
    await bgUpdateItem(currentId, { target: target });
    item.target = target;
    renderTargetBar(item);
    const b = $("#d-target-save");
    b.textContent = "\u2713";
    setTimeout(function () {
      b.textContent = t("save");
    }, 900);
  });

  $("#d-open").addEventListener("click", function () {
    const item = items.find((x) => x.id === currentId);
    if (item) browser.tabs.create({ url: item.url });
  });

  $("#d-remove").addEventListener("click", async function () {
    const id = currentId;
    currentId = null;
    await bgRemoveItems([id]);
    renderMain();
    showScreen("scr-main");
  });

  $("#set-bnotif").addEventListener("click", async function () {
    settings.browserNotif = !settings.browserNotif;
    renderToggle(this, settings.browserNotif);
    await saveSettings();
  });

  $("#set-drop").addEventListener("click", async function () {
    settings.notifyOnDrop = !settings.notifyOnDrop;
    renderToggle(this, settings.notifyOnDrop);
    await saveSettings();
  });

  $("#set-pct").addEventListener("change", async function () {
    settings.notifyPctDrop = parseInt(this.value, 10) || 0;
    await saveSettings();
  });

  $("#set-interval").addEventListener("change", async function () {
    settings.intervalMin = parseInt(this.value, 10) || 180;
    await saveSettings();
    await browser.runtime.sendMessage({ type: "reschedule" }).catch(() => {});
  });

  $("#set-theme").addEventListener("change", async function () {
    settings.theme = this.value;
    await saveSettings();
    applyTheme();
    renderMain();
    if (!document.getElementById("scr-detail").hidden && currentId) openDetail(currentId);
  });

  $("#tg-connect").addEventListener("click", async function () {
    const token = $("#tg-token").value.trim();
    const note = $("#tg-note");
    if (!token) {
      note.className = "tg-note err";
      note.textContent = t("tgNeedToken");
      return;
    }
    const btn = $("#tg-connect");
    btn.disabled = true;
    btn.textContent = "…";
    const res = await browser.runtime
      .sendMessage({ type: "tgDetect", token: token })
      .catch(() => ({ ok: false, error: t("errTgNetwork") }));
    btn.disabled = false;
    btn.textContent = t("tgConnect");
    if (res && res.ok) {
      settings.tgToken = token;
      settings.tgChatId = res.chatId;
      settings.tgName = res.name;
      await saveSettings();
      renderTgStatus();
      note.className = "tg-note ok";
      note.textContent = t("tgConnectOk", res.name);
    } else {
      note.className = "tg-note err";
      note.textContent = (res && res.error) || t("tgConnectFail");
    }
  });

  $("#tg-token").addEventListener("keydown", function (e) {
    if (e.key === "Enter") $("#tg-connect").click();
  });

  $("#tg-test").addEventListener("click", async function () {
    const ok = await browser.runtime.sendMessage({ type: "tgTest" }).catch(() => false);
    const note = $("#tg-note");
    note.className = ok ? "tg-note ok" : "tg-note err";
    note.textContent = ok ? t("tgTestOk") : t("tgTestFail");
  });

  $("#btn-export").addEventListener("click", function () {
    const data = JSON.stringify({ exportedAt: new Date().toISOString(), items: items }, null, 2);
    const blob = new Blob([data], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "cennik-export.json";
    a.click();
    setTimeout(function () {
      URL.revokeObjectURL(a.href);
    }, 1000);
  });

  $("#btn-import-trigger").addEventListener("click", function () {
    $("#btn-import").click();
  });

  $("#btn-import").addEventListener("change", async function (e) {
    const file = e.target.files && e.target.files[0];
    e.target.value = "";
    if (!file) return;
    const note = $("#import-note");
    try {
      const data = JSON.parse(await file.text());
      const added = await browser.runtime.sendMessage({
        type: "importItems",
        items: data.items || []
      });
      await load();
      note.className = "tg-note ok";
      note.textContent = t("importOk", added || 0);
      note.hidden = false;
    } catch (err) {
      note.className = "tg-note err";
      note.textContent = t("importFail");
      note.hidden = false;
    }
  });

  $("#btn-clear").addEventListener("click", async function () {
    const b = $("#btn-clear");
    if (b.dataset.armed !== "1") {
      b.dataset.armed = "1";
      b.textContent = t("clearConfirm");
      setTimeout(function () {
        b.dataset.armed = "";
        b.textContent = t("clearBtn");
      }, 3000);
      return;
    }
    await bgClearItems();
    b.dataset.armed = "";
    b.textContent = t("clearBtn");
    renderMain();
  });

  browser.storage.onChanged.addListener(function (changes, area) {
    if (area !== "local") return;
    if (!changes.items && !changes.settings) return;
    if (refreshTimer) clearTimeout(refreshTimer);
    refreshTimer = setTimeout(async function () {
      refreshTimer = null;
      const prevId = currentId;
      await load();
      if (prevId && !document.getElementById("scr-detail").hidden) {
        openDetail(prevId);
      }
    }, 150);
  });
}

document.addEventListener("DOMContentLoaded", init);
