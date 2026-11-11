"use strict";

const DEFAULTS = {
  intervalMin: 180,
  browserNotif: true,
  notifyOnDrop: true,
  notifyPctDrop: 0,
  tgToken: "",
  tgChatId: "",
  tgName: "",
  wbDest: "-1257786"
};

const ALARM = "cennik-check";
const CHECK_TIMEOUT_MS = 20000;
let checkPromise = null;

var sessionMem = { pending: [], openTabs: [], notifUrls: {} };
var sessionApi = (function () {
  try {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.session) {
      return chrome.storage.session;
    }
  } catch (e) {
    /* not in extension context */
  }
  if (browser.storage && browser.storage.session) return browser.storage.session;
  return null;
})();
var hasSessionStorage = Boolean(sessionApi);

async function sessionGet(defaults) {
  const out = Object.assign({}, defaults);
  if (hasSessionStorage) {
    try {
      const raw = await sessionApi.get(Object.keys(defaults));
      if (raw && typeof raw === "object") {
        for (const k of Object.keys(defaults)) {
          if (Object.prototype.hasOwnProperty.call(raw, k)) out[k] = raw[k];
        }
      }
    } catch (e) {
      /* use defaults */
    }
  } else {
    for (const k of Object.keys(defaults)) {
      if (sessionMem[k] !== undefined) out[k] = sessionMem[k];
    }
  }
  return out;
}

async function sessionSet(obj) {
  if (hasSessionStorage) {
    try {
      await sessionApi.set(obj);
    } catch (e) {
      /* ignore */
    }
    return;
  }
  for (const k of Object.keys(obj)) {
    if (Object.prototype.hasOwnProperty.call(obj, k)) sessionMem[k] = obj[k];
  }
}

async function pendingAdd(id) {
  const raw = await sessionGet({ pending: [] });
  const pending = (raw.pending || []).slice();
  if (pending.indexOf(id) === -1) pending.push(id);
  await sessionSet({ pending: pending });
}

async function pendingRemove(id) {
  const raw = await sessionGet({ pending: [] });
  await sessionSet({
    pending: (raw.pending || []).filter(function (x) {
      return x !== id;
    })
  });
}

async function openTabAdd(tabId) {
  const raw = await sessionGet({ openTabs: [] });
  const tabs = (raw.openTabs || []).slice();
  if (tabs.indexOf(tabId) === -1) tabs.push(tabId);
  await sessionSet({ openTabs: tabs });
}

async function openTabRemove(tabId) {
  const raw = await sessionGet({ openTabs: [] });
  await sessionSet({
    openTabs: (raw.openTabs || []).filter(function (x) {
      return x !== tabId;
    })
  });
}

async function closeOrphanTabs() {
  const raw = await sessionGet({ openTabs: [] });
  for (const tabId of raw.openTabs || []) {
    try {
      await browser.tabs.remove(tabId);
    } catch (e) {
      /* tab may already be gone */
    }
  }
  await sessionSet({ openTabs: [] });
}

async function notifUrlSet(id, url) {
  const raw = await sessionGet({ notifUrls: {} });
  const map = Object.assign({}, raw.notifUrls || {});
  map[id] = url;
  await sessionSet({ notifUrls: map });
}

async function notifUrlGet(id) {
  const raw = await sessionGet({ notifUrls: {} });
  return (raw.notifUrls || {})[id];
}

async function notifUrlDelete(id) {
  const raw = await sessionGet({ notifUrls: {} });
  const map = Object.assign({}, raw.notifUrls || {});
  delete map[id];
  await sessionSet({ notifUrls: map });
}

async function getAll() {
  const raw = await browser.storage.local.get({ items: [], settings: {} });
  return {
    items: raw.items,
    settings: Object.assign({}, DEFAULTS, raw.settings)
  };
}

function saveItems(items) {
  return browser.storage.local.set({ items });
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

async function fetchWithTimeout(url, opts, ms) {
  const ctrl = new AbortController();
  const timer = setTimeout(function () {
    ctrl.abort();
  }, ms);
  try {
    return await fetch(url, Object.assign({}, opts || {}, { signal: ctrl.signal }));
  } catch (e) {
    if (e && e.name === "AbortError") throw new Error("errTimeout");
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

function wbCardUrl(nmId, settings) {
  const dest = (settings && settings.wbDest) || "-1257786";
  return (
    "https://card.wb.ru/cards/v4/detail?appType=1&curr=rub&dest=" +
    encodeURIComponent(dest) +
    "&spp=30&nm=" +
    encodeURIComponent(nmId)
  );
}

async function fetchWb(nmId, settings) {
  const res = await fetchWithTimeout(wbCardUrl(nmId, settings), {}, CHECK_TIMEOUT_MS);
  if (!res.ok) throw new Error("WB API HTTP " + res.status);
  const data = await res.json();
  const products =
    (data && data.products) || (data && data.data && data.data.products) || [];
  const p = products[0];
  if (!p) return null;
  let kop = null;
  if (Array.isArray(p.sizes)) {
    for (const s of p.sizes) {
      if (s && s.price && s.price.product) {
        kop = s.price.product;
        break;
      }
    }
  }
  if (kop == null && p.salePriceU) kop = p.salePriceU;
  if (kop == null && p.priceU) kop = p.priceU;
  return {
    price: kop != null ? Math.round(kop / 100) : null,
    title: [p.brand, p.name].filter(Boolean).join(" · ")
  };
}

function ozonApiUrl(pid) {
  return (
    "https://www.ozon.ru/api/composer-api.bx/page/json/v2?url=" +
    encodeURIComponent("/product/" + pid + "/")
  );
}

function parseRubles(v) {
  if (v == null) return null;
  const digits = String(v).replace(/[^\d]/g, "");
  return digits ? parseInt(digits, 10) : null;
}

// Ozon: fetch from the browser with user cookies.
async function fetchOzon(pid) {
  const res = await fetchWithTimeout(ozonApiUrl(pid), {
    credentials: "include",
    headers: { Accept: "application/json" }
  }, CHECK_TIMEOUT_MS);
  if (!res.ok) throw new Error("Ozon API HTTP " + res.status);
  const data = await res.json();
  const widgets = (data && data.widgetStates) || {};
  let price = null;
  let title = null;
  for (const key of Object.keys(widgets)) {
    let w;
    try {
      w = JSON.parse(widgets[key]);
    } catch (e) {
      continue;
    }
    if (!w) continue;
    if (price == null && key.indexOf("webPrice") === 0) {
      price = parseRubles(w.price) || parseRubles(w.cardPrice);
    }
    if (w.cellTrackingInfo && w.cellTrackingInfo.product) {
      const p = w.cellTrackingInfo.product;
      if (price == null && p.finalPrice != null) price = parseRubles(p.finalPrice);
      if (!title && p.title) title = String(p.title);
    }
    if (!title && key.indexOf("webStickyProducts") === 0 && w.name) {
      title = String(w.name);
    }
  }
  if (!title && data && data.seo && data.seo.title) {
    title = String(data.seo.title).split(" купить ")[0];
  }
  return { price: price, title: title };
}

function parseNum(v) {
  if (v == null) return null;
  const n = parseFloat(String(v).replace(/[\s ]/g, "").replace(",", "."));
  return isFinite(n) && n > 0 ? Math.round(n * 100) / 100 : null;
}

function offerInfo(offers) {
  const list = Array.isArray(offers) ? offers : [offers];
  for (const o of list) {
    if (!o || typeof o !== "object") continue;
    const ps = Array.isArray(o.priceSpecification) ? o.priceSpecification[0] : o.priceSpecification;
    let p = parseNum(o.price);
    if (p == null) p = parseNum(o.lowPrice);
    if (p == null && ps) p = parseNum(ps.price);
    if (p != null) {
      let cur = o.priceCurrency || (ps && ps.priceCurrency) || null;
      if (cur) cur = String(cur).toUpperCase();
      if (cur === "RUR") cur = "RUB";
      return { price: p, currency: cur };
    }
  }
  return null;
}

function isProductNode(d) {
  const t = d && d["@type"];
  return t === "Product" || (Array.isArray(t) && t.indexOf("Product") !== -1);
}

function normTitle(s) {
  return String(s || "").toLowerCase().replace(/\s+/g, " ").trim();
}

function cleanPath(p) {
  return p !== "/" ? p.replace(/\/+$/, "") : p;
}

function productUrls(d) {
  const out = [];
  const push = function (u) {
    if (typeof u === "string" && u) out.push(u);
  };
  push(d.url);
  push(d["@id"]);
  const offers = Array.isArray(d.offers) ? d.offers : [d.offers];
  for (const o of offers) {
    if (o && typeof o === "object") push(o.url);
  }
  return out;
}

function pageProductId(baseUrl) {
  try {
    const m = cleanPath(new URL(baseUrl).pathname).match(/\/products?\/(\d+)/i);
    return m ? m[1] : null;
  } catch (e) {
    return null;
  }
}

function productIdFromNode(d) {
  const ids = [];
  if (d.sku != null) ids.push(String(d.sku));
  if (d.productID != null) ids.push(String(d.productID));
  for (const u of productUrls(d)) {
    const m = String(u).match(/\/products?\/(\d+)/i);
    if (m) ids.push(m[1]);
  }
  return ids;
}

// Pick the Product node for this page (SPAs may embed unrelated products).
function pickProduct(candidates, baseUrl, pagePaths, titleHint) {
  const prods = [];
  for (const d of candidates) {
    if (!isProductNode(d) || d.offers == null) continue;
    const offer = offerInfo(d.offers);
    if (!offer) continue;
    prods.push({ d: d, offer: offer });
  }
  if (!prods.length) return null;
  const matchesPage = function (u) {
    try {
      return pagePaths.indexOf(cleanPath(new URL(u, baseUrl).pathname)) !== -1;
    } catch (e) {
      return false;
    }
  };
  const pid = pageProductId(baseUrl);
  if (pid) {
    for (const p of prods) {
      if (productIdFromNode(p.d).indexOf(pid) !== -1) return p;
    }
  }
  for (const p of prods) {
    if (productUrls(p.d).some(matchesPage)) return p;
  }
  const hint = normTitle(titleHint);
  if (hint) {
    for (const p of prods) {
      const name = normTitle(p.d.name);
      if (name && (hint.indexOf(name) !== -1 || name.indexOf(hint) !== -1)) return p;
    }
  }
  const noUrl = prods.filter(function (p) {
    return productUrls(p.d).length === 0;
  });
  if (noUrl.length === 1) return noUrl[0];
  return null;
}

function normCur(cur) {
  if (!cur) return null;
  let c = String(cur).trim().toUpperCase();
  if (c === "RUR") c = "RUB";
  return /^[A-Z]{3}$/.test(c) ? c : null;
}

function microdataProduct(doc, titleHint) {
  const scopes = doc.querySelectorAll('[itemtype*="schema.org/Product"]');
  const hint = normTitle(titleHint);
  let fallback = null;
  let withPrice = 0;
  for (const scope of scopes) {
    const priceEl = scope.querySelector('[itemprop="price"]');
    if (!priceEl) continue;
    const found = priceFromElement(priceEl);
    if (!found || found.price == null) continue;
    withPrice++;
    const curEl = scope.querySelector('[itemprop="priceCurrency"]');
    const nameEl = scope.querySelector('[itemprop="name"]');
    const cand = {
      price: found.price,
      currency: found.currency || normCur(curEl && (curEl.getAttribute("content") || curEl.textContent)),
      title: nameEl ? nameEl.textContent.trim() : null
    };
    const name = normTitle(nameEl && nameEl.textContent);
    if (name && hint && (hint.indexOf(name) !== -1 || name.indexOf(hint) !== -1)) return cand;
    if (!fallback) fallback = cand;
  }
  return withPrice === 1 ? fallback : null;
}

function metaContent(doc, names) {
  for (const n of names) {
    const el = doc.querySelector('meta[property="' + n + '"], meta[name="' + n + '"], meta[itemprop="' + n + '"]');
    if (el && el.getAttribute("content")) return el.getAttribute("content");
  }
  return null;
}

function metaProduct(doc, titleHint) {
  const price = parseNum(metaContent(doc, ["product:price:amount", "og:price:amount", "price"]));
  if (price == null) return null;
  return {
    price: price,
    currency: normCur(metaContent(doc, ["product:price:currency", "og:price:currency", "priceCurrency"])),
    title: titleHint || null
  };
}

function scanState(rootObj, fallbackTitle) {
  let best = null;
  let title = null;
  const consider = function (path, value, currency) {
    let score = 0;
    if (/sale|activity|discount|actual|final|current/.test(path)) score += 2;
    if (/min/.test(path)) score += 1;
    if (/old|origin|market|list|cross|max|full/.test(path)) score -= 2;
    if (/week|catalog|carousel|listing|block|related|similar|recommend|upsell|hover|grid/.test(path)) score -= 6;
    if (!best || score > best.score || (score === best.score && value < best.value)) {
      best = { score: score, value: value, currency: currency };
    }
  };
  const seen = new Set();
  const stack = [{ v: rootObj, path: "", d: 0 }];
  let n = 0;
  while (stack.length && n < 30000) {
    const cur = stack.pop();
    const v = cur.v;
    n++;
    if (!v || typeof v !== "object" || cur.d > 14 || seen.has(v)) continue;
    seen.add(v);
    for (const k of Object.keys(v)) {
      const val = v[k];
      const path = cur.path + "." + k.toLowerCase();
      if (val && typeof val === "object") {
        if (/price|amount/i.test(k)) {
          const num = parseNum(val.value != null ? val.value : val.amount);
          if (num != null) {
            consider(path, num, normCur(val.currency));
            continue;
          }
        }
        stack.push({ v: val, path: path, d: cur.d + 1 });
      } else {
        if (!title && typeof val === "string" && val.trim().length > 8 && /^(subject|productTitle|itemTitle|goodsName|goods_name)$/i.test(k)) {
          title = val.trim();
        }
        if (/price/i.test(k) && !/id|text|str|unit|per|old|origin|max|full/i.test(k)) {
          const num = parseNum(val);
          if (num != null && num < 100000000) consider(path, num, null);
        }
      }
    }
  }
  if (!best) return null;
  return { price: best.value, currency: best.currency, title: title || fallbackTitle || null };
}

function nextDataProduct(doc, titleHint) {
  const el = doc.getElementById("__NEXT_DATA__");
  if (!el) return null;
  try {
    return scanState(JSON.parse(el.textContent), titleHint);
  } catch (e) {
    return null;
  }
}

function fallbackFromDoc(doc, titleHint) {
  const found = microdataProduct(doc, titleHint) || metaProduct(doc, titleHint) || nextDataProduct(doc, titleHint);
  if (!found) return null;
  if (!found.title) found.title = titleHint || (doc.title || "").trim() || null;
  return found;
}

function productFromDoc(doc, pageUrl) {
  const candidates = [];
  const collect = function (x) {
    if (Array.isArray(x)) x.forEach(collect);
    else if (x && typeof x === "object") {
      candidates.push(x);
      if (x["@graph"]) collect(x["@graph"]);
    }
  };
  const nodes = doc.querySelectorAll('script[type="application/ld+json"]');
  for (const node of nodes) {
    try {
      collect(JSON.parse(node.textContent));
    } catch (e) {
      /* invalid JSON */
    }
  }
  const pagePaths = [];
  try {
    pagePaths.push(cleanPath(new URL(pageUrl).pathname));
  } catch (e) {
    /* invalid page URL */
  }
  const canonical = doc.querySelector('link[rel="canonical"]');
  if (canonical) {
    const href = canonical.getAttribute("href");
    if (href) {
      try {
        pagePaths.push(cleanPath(new URL(href, pageUrl).pathname));
      } catch (e) {
        /* invalid canonical */
      }
    }
  }
  const og = doc.querySelector('meta[property="og:title"]');
  const h1 = doc.querySelector("h1");
  const titleHint = (og && og.getAttribute("content")) || (h1 && h1.textContent) || "";
  const picked = pickProduct(candidates, pageUrl, pagePaths, titleHint);
  if (!picked) return fallbackFromDoc(doc, titleHint);
  let title = picked.d.name ? String(picked.d.name) : null;
  if (!title) {
    title = (og && og.getAttribute("content")) || (doc.title || "").trim() || null;
  }
  return { price: picked.offer.price, currency: picked.offer.currency, title: title };
}

function normalizeWebUrl(raw) {
  const u = new URL(raw);
  let out = u.origin + u.pathname;
  if (u.pathname !== "/") out = out.replace(/\/+$/, "");
  const params = new URLSearchParams(u.search);
  const drop = [];
  params.forEach(function (v, k) {
    if (/^(utm_|aff_)/i.test(k) || /^(fbclid|gclid|yclid|ysclid|_openstat|spm|scm|pdp_npi|algo_pvid|algo_exp_id|gatewayAdapt|srcSns|terminal_id)$/i.test(k)) drop.push(k);
  });
  for (const k of drop) params.delete(k);
  const q = params.toString();
  return q ? out + "?" + q : out;
}

async function fetchGeneric(url, pickSel) {
  if (typeof DOMParser === "undefined") {
    throw new Error("errNoPricePage");
  }
  const res = await fetchWithTimeout(url, {
    credentials: "include",
    headers: { Accept: "text/html" }
  }, CHECK_TIMEOUT_MS);
  if (!res.ok) throw new Error("HTTP " + res.status);
  const html = await res.text();
  const doc = new DOMParser().parseFromString(html, "text/html");
  if (pickSel) {
    const found = pickedFromDoc(doc, pickSel);
    if (found) return found;
  }
  return productFromDoc(doc, url);
}

// SPA fallback: open the product in a background tab (one at a time).
const TAB_FETCH_MS = 45000;
let tabQueue = Promise.resolve();

function sleep(ms) {
  return new Promise(function (r) { setTimeout(r, ms); });
}

function fetchViaTab(url, pickSel) {
  const run = tabQueue.then(function () {
    return tabFetchNow(url, pickSel);
  });
  tabQueue = run.catch(function () {});
  return run;
}

async function tabFetchNow(url, pickSel) {
  if (navigator.onLine === false) throw new Error("errNoNetwork");
  const tab = await browser.tabs.create({ url: url, active: false });
  try {
    try {
      await openTabAdd(tab.id);
    } catch (e) {
      /* session bookkeeping must not block tab cleanup */
    }
    const started = Date.now();
    while (Date.now() - started < TAB_FETCH_MS) {
      await sleep(2000);
      try {
        await browser.tabs.get(tab.id);
      } catch (e) {
        throw new Error("errNoPricePage");
      }
      let found = null;
      try {
        found = await browser.tabs.sendMessage(tab.id, { type: "readPrice", pickSel: pickSel || null });
      } catch (e) {
        found = null;
      }
      if (found && found.price != null) {
        return { price: found.price, currency: found.currency || null, title: null };
      }
    }
    throw new Error("errNoPricePage");
  } finally {
    try {
      await browser.tabs.remove(tab.id);
    } catch (e) {
      /* tab may already be gone */
    }
    try {
      await openTabRemove(tab.id);
    } catch (e) {
      /* ignore */
    }
  }
}

async function fetchWeb(url, pickSel, needsTab) {
  if (!needsTab) {
    try {
      const info = await fetchGeneric(url, pickSel);
      if (info && info.price != null) return info;
    } catch (e) {
      /* network/HTTP/timeout — fall through to tab */
    }
  }
  const found = await fetchViaTab(url, pickSel);
  if (found) found.viaTab = true;
  return found;
}

function symToCur(sym) {
  if (!sym) return null;
  if (sym === "₽" || sym.indexOf("руб") === 0) return "RUB";
  if (sym.indexOf("$") !== -1) return "USD";
  if (sym === "€") return "EUR";
  if (sym === "₸" || /^тг/i.test(sym) || /^tenge/i.test(sym)) return "KZT";
  if (sym === "₴") return "UAH";
  if (sym === "¥") return "CNY";
  if (sym === "Kč") return "CZK";
  if (sym === "zł") return "PLN";
  return null;
}

function normalizePriceText(txt) {
  return String(txt || "")
    .replace(/\u00a0/g, " ")
    .replace(/,-/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function rawToPrice(raw) {
  let r = raw.replace(/ /g, "");
  const lastDot = r.lastIndexOf(".");
  const lastCom = r.lastIndexOf(",");
  if (lastDot !== -1 && lastCom !== -1) {
    r = lastCom > lastDot ? r.replace(/\./g, "") : r.replace(/,/g, "");
  } else if (/^\d{1,3}([.,]\d{3})+$/.test(r)) {
    r = r.replace(/[.,]/g, "");
  }
  return parseNum(r);
}

function currencyNear(el) {
  const scope = el.closest && el.closest('[itemtype*="schema.org/Product"], [itemtype*="Product"]');
  if (!scope) return null;
  const c = scope.querySelector('[itemprop="priceCurrency"]');
  return normCur(c && (c.getAttribute("content") || c.textContent));
}

// "1 234,56 ₽", "US $12.30", "2, 19 €", "2 299,- Kč"
function priceFromText(txt) {
  const s = normalizePriceText(txt);
  if (!s) return null;
  const symRe = "(?:₽|руб\\.?|US ?\\$|\\$|€|₸|тг\\.?|tenge|₴|¥|Kč|zł)";
  const best = { score: -999, price: null, currency: null };
  const curInText = (function () {
    const cm = s.match(new RegExp(symRe));
    return cm ? symToCur(cm[0]) : null;
  })();

  function consider(price, currency, score, index) {
    if (price == null || price <= 0) return;
    const before = s.slice(Math.max(0, index - 10), index).toLowerCase();
    if (/old|was|strike|del|cross|origin|prev/.test(before)) score -= 15;
    const total = score + index / 25 - index / 400;
    if (total > best.score) {
      best.score = total;
      best.price = price;
      best.currency = currency;
    }
  }

  const splitEu = new RegExp("(\\d+)\\s*[,\\.]\\s*(\\d{2})\\s*(" + symRe + ")", "gi");
  let sm;
  while ((sm = splitEu.exec(s)) !== null) {
    const before = s.slice(Math.max(0, sm.index - 14), sm.index).toLowerCase();
    let score = 10;
    if (/\b(1\s*kg|kg|100\s*g|pro)\s*$/.test(before)) score -= 20;
    consider(parseNum(sm[1] + "." + sm[2]), symToCur(sm[3]), score, sm.index);
  }

  const spaced = /(\d{1,3}(?:\s\d{3})+(?:[.,]\d{1,2})?)/g;
  let sp;
  while ((sp = spaced.exec(s)) !== null) {
    const after = s.slice(sp.index + sp[0].length, sp.index + sp[0].length + 12);
    const cur =
      curInText ||
      (after.match(new RegExp(symRe)) ? symToCur(after.match(new RegExp(symRe))[0]) : null);
    if (!cur) continue;
    let score = 12;
    const before = s.slice(Math.max(0, sp.index - 14), sp.index).toLowerCase();
    if (/\b(1\s*kg|kg|100\s*g|pro)\s*$/.test(before)) score -= 20;
    consider(rawToPrice(sp[1]), cur, score, sp.index);
  }

  const re = new RegExp(
    "(" + symRe + ")?\\s?(\\d{1,3}(?:[ .]\\d{3})+(?:[.,]\\d{1,2})?|\\d+(?:[.,]\\d{1,2})?)\\s?(" + symRe + ")?",
    "gi"
  );
  let m;
  while ((m = re.exec(s)) !== null) {
    const cur = symToCur(m[1] || m[3]) || curInText;
    if (!m[1] && !m[3] && !curInText) continue;
    const raw = m[2].replace(/ /g, "");
    const price = rawToPrice(m[2]);
    let score = 0;
    if (cur) score += 3;
    if (/[.,]\d{2}$/.test(raw)) score += 6;
    if (/\s\d{3}/.test(m[2])) score += 8;
    const before = s.slice(Math.max(0, m.index - 14), m.index).toLowerCase();
    if (/\b(1\s*kg|kg|100\s*g|pro)\s*$/.test(before)) score -= 20;
    if (cur && price < 100 && !/[.,]\d{2}$/.test(raw) && !/\s\d{3}/.test(m[2])) score -= 8;
    consider(price, cur, score, m.index);
  }

  return best.price != null ? { price: best.price, currency: best.currency } : null;
}

function textWithSiblings(el) {
  let txt = normalizePriceText(el.textContent);
  let prev = el.previousElementSibling;
  for (let i = 0; i < 4 && prev; i++) {
    const pt = normalizePriceText(prev.textContent);
    if (!pt) {
      prev = prev.previousElementSibling;
      continue;
    }
    if (/^\d{1,3}$/.test(pt) || (/^[\d\s,.-]+$/.test(pt) && pt.length <= 10 && !/(?:Kč|€|₽|руб|\$|тг|₸)/i.test(pt))) {
      txt = pt + " " + txt;
      prev = prev.previousElementSibling;
    } else {
      break;
    }
  }
  return txt;
}

function priceFromElement(el) {
  if (!el) return null;
  let node = el;
  let fallback = null;
  for (let i = 0; node && node.nodeType === 1 && i < 6; i++) {
    const attr = node.getAttribute && node.getAttribute("content");
    if (attr != null && String(attr).trim() !== "") {
      const p = parseNum(attr);
      if (p != null) return { price: p, currency: currencyNear(node) };
    }
    const txt = textWithSiblings(node);
    if (txt.length > 0 && txt.length <= 120) {
      const found = priceFromText(txt);
      if (found) {
        if (found.currency) return found;
        const cur = currencyNear(node);
        if (cur) return { price: found.price, currency: cur };
        if (!fallback) fallback = found;
      }
    }
    node = node.parentElement;
  }
  return fallback;
}

function pickedFromDoc(doc, pickSel) {
  let el = null;
  try {
    el = doc.querySelector(pickSel);
  } catch (e) {
    return null;
  }
  if (!el) return null;
  const found = priceFromElement(el);
  if (!found) return null;
  return { price: found.price, currency: found.currency, title: null };
}

function fetchInfo(item, settings) {
  if (item.source === "ozon") {
    return fetchOzon(item.pid).catch(function () {
      return fetchViaTab(item.url, null);
    });
  }
  if (item.source === "web") return fetchWeb(item.url, item.pickSel, item.needsTab);
  return fetchWb(item.nmId, settings);
}

async function notifyAll(settings, title, message, url) {
  if (settings.browserNotif) {
    try {
      const id = await browser.notifications.create({
        type: "basic",
        iconUrl: browser.runtime.getURL("icons/icon128.png"),
        title: title,
        message: message
      });
      if (url) await notifUrlSet(id, url);
    } catch (e) {
      /* notifications may be disabled by the OS */
    }
  }
  await tgSend(settings, title + "\n" + message + (url ? "\n" + url : ""));
}

browser.notifications.onClicked.addListener(function (id) {
  (async function () {
    const url = await notifUrlGet(id);
    if (url) {
      browser.tabs.create({ url: url });
      await notifUrlDelete(id);
    }
    browser.notifications.clear(id);
  })();
});

browser.notifications.onClosed.addListener(function (id) {
  notifUrlDelete(id);
});

async function tgSend(settings, text) {
  if (!settings.tgToken || !settings.tgChatId) return false;
  try {
    const res = await fetch(
      "https://api.telegram.org/bot" + settings.tgToken + "/sendMessage",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: settings.tgChatId,
          text: text,
          disable_web_page_preview: true
        })
      }
    );
    return res.ok;
  } catch (e) {
    return false;
  }
}

async function tgDetect(token) {
  const res = await fetch("https://api.telegram.org/bot" + token + "/getUpdates");
  if (!res.ok) return { ok: false, error: t("errTgTokenHttp", res.status) };
  const data = await res.json();
  if (!data.ok) {
    return {
      ok: false,
      error: data.error_code === 409
        ? t("tgWebhookBusy")
        : (data.description || t("errTgToken"))
    };
  }
  const updates = (data.result || []).slice().reverse();
  for (const u of updates) {
    const chat = u.message && u.message.chat;
    if (chat && chat.id) {
      return {
        ok: true,
        chatId: String(chat.id),
        name: chat.username ? "@" + chat.username : chat.first_name || t("tgChat", chat.id)
      };
    }
  }
  return {
    ok: false,
    error: t("errTgNoStart")
  };
}

function withTimeout(promise, ms) {
  return new Promise(function (resolve, reject) {
    const t = setTimeout(function () {
      reject(new Error("errTimeout"));
    }, ms);
    promise.then(
      function (v) { clearTimeout(t); resolve(v); },
      function (e) { clearTimeout(t); reject(e); }
    );
  });
}

function pctDropHit(settings, prev, price) {
  const pct = Number(settings.notifyPctDrop) || 0;
  if (pct <= 0 || prev == null || !prev) return false;
  return ((prev - price) / prev) * 100 >= pct;
}

function applyPrice(item, settings, info, notes) {
  const currencyChanged =
    Boolean(info.currency && item.currency && info.currency !== item.currency);
  if (currencyChanged) {
    item.history = [];
    item.notifiedPrice = null;
  }
  const prev = currencyChanged ? null : item.lastPrice;
  if (info.currency && info.currency !== item.currency) item.currency = info.currency;
  if (info.viaTab) item.needsTab = true;
  item.lastChecked = Date.now();
  item.lastError = null;
  if (info.price === prev) return "same";
  if (prev != null && info.price > prev) item.notifiedPrice = null;
  item.lastPrice = info.price;
  item.history.push({ t: Date.now(), p: info.price });
  if (item.history.length > 500) item.history = item.history.slice(-500);
  const dropped = prev != null && info.price < prev;
  const targetHit =
    item.target != null &&
    info.price <= item.target &&
    (prev == null || prev > item.target);
  const alreadyNotified = item.notifiedPrice != null && item.notifiedPrice === info.price;
  if (targetHit && !alreadyNotified) {
    item.notifiedPrice = info.price;
    notes.push({
      title: t("notifTargetHit", fmt(info.price, item.currency)),
      message: item.title + "\n" + t("notifTargetWas", fmt(item.target, item.currency)),
      url: item.url
    });
  } else if (dropped && !alreadyNotified && pctDropHit(settings, prev, info.price)) {
    item.notifiedPrice = info.price;
    notes.push({
      title: t("notifDropPct", Math.round(((prev - info.price) / prev) * 100), fmt(prev, item.currency), fmt(info.price, item.currency)),
      message: item.title,
      url: item.url
    });
  } else if (dropped && settings.notifyOnDrop && !(Number(settings.notifyPctDrop) > 0) && !alreadyNotified) {
    item.notifiedPrice = info.price;
    notes.push({
      title: t("notifDrop", fmt(prev, item.currency), fmt(info.price, item.currency)),
      message: item.title,
      url: item.url
    });
  }
  return "changed";
}

// ===== Update engine =====
const HOST_DELAY_MS = 2500;
const inFlight = new Map();
const hostQueues = new Map();
let writeLock = Promise.resolve();
let settingsLock = Promise.resolve();

function mutateSettings(fn) {
  const run = settingsLock.then(async function () {
    const raw = await browser.storage.local.get({ settings: {} });
    const settings = Object.assign({}, DEFAULTS, raw.settings);
    const out = await fn(settings);
    await browser.storage.local.set({ settings: settings });
    return out;
  });
  settingsLock = run.catch(function () {});
  return run;
}

function itemHost(item) {
  if (item.source === "wb") return "wb.ru";
  if (item.source === "ozon") return "ozon.ru";
  try {
    return new URL(item.url).hostname;
  } catch (e) {
    return "web";
  }
}

function mutateItems(fn) {
  const run = writeLock.then(async function () {
    const raw = await browser.storage.local.get({ items: [] });
    const out = await fn(raw.items);
    await browser.storage.local.set({ items: raw.items });
    return out;
  });
  writeLock = run.catch(function () {});
  return run;
}

function applyResult(id, settings, info) {
  return mutateItems(function (items) {
    const item = items.find(function (x) {
      return x.id === id;
    });
    if (!item) return { res: "gone", notes: [] };
    const notes = [];
    const res = applyPrice(item, settings, info, notes);
    return { res: res, notes: notes };
  }).then(async function (out) {
    for (const n of out.notes || []) {
      await notifyAll(settings, n.title, n.message, n.url);
    }
    return out.res;
  });
}

function applyError(id, err) {
  return mutateItems(async function (items) {
    const item = items.find(function (x) {
      return x.id === id;
    });
    if (item) item.lastError = String((err && err.message) || err);
    return "error";
  });
}

function queueCheck(item, settings, force) {
  if (inFlight.has(item.id)) return inFlight.get(item.id);
  const host = itemHost(item);
  const id = item.id;
  pendingAdd(id);
  const prev = hostQueues.get(host) || Promise.resolve();
  const run = prev.then(async function () {
    try {
      const { items: allItems } = await getAll();
      const fresh = allItems.find(function (x) {
        return x.id === id;
      });
      if (!fresh || (fresh.paused && !force)) return false;
      const info = await fetchInfo(fresh, settings);
      if (!info || info.price == null) throw new Error("errNoPrice");
      return (await applyResult(id, settings, info)) === "changed";
    } catch (e) {
      await applyError(id, e);
      throw e;
    } finally {
      await sleep(HOST_DELAY_MS);
      await pendingRemove(id);
    }
  });
  hostQueues.set(host, run.catch(function () {}));
  const tracked = run.finally(function () {
    inFlight.delete(id);
  });
  inFlight.set(id, tracked);
  return tracked;
}

function checkAll() {
  if (checkPromise) return checkPromise;
  checkPromise = (async function () {
    const { items, settings } = await getAll();
    let changed = 0;
    let errors = 0;
    await Promise.all(
      items.filter(function (x) {
        return !x.paused;
      }).map(function (item) {
        return queueCheck(item, settings).then(
          function (ch) {
            if (ch) changed++;
          },
          function () {
            errors++;
          }
        );
      })
    );
    return { checked: items.length, changed: changed, errors: errors };
  })();
  return checkPromise.finally(async function () {
    await closeOrphanTabs();
    checkPromise = null;
  });
}

async function checkOne(id) {
  const { items, settings } = await getAll();
  const item = items.find(function (x) {
    return x.id === id;
  });
  if (!item) return { ok: false, error: t("errNotFound") };
  try {
    await queueCheck(item, settings, true);
    const fresh = await getAll();
    return {
      ok: true,
      item: fresh.items.find(function (x) {
        return x.id === id;
      }) || null
    };
  } catch (e) {
    return { ok: false, error: t("errCheckFailed") };
  }
}

async function addItem(msg) {
  const source = msg.source === "ozon" ? "ozon" : msg.source === "web" ? "web" : "wb";
  let pid = null;
  let id = null;
  let url = null;

  if (source === "web") {
    try {
      url = normalizeWebUrl(msg.url);
    } catch (e) {
      return { ok: false, error: t("errBadLink") };
    }
    id = "web:" + url;
  } else {
    pid = String(msg.pid || msg.nmId);
    id = source + ":" + pid;
    url =
      msg.url ||
      (source === "ozon"
        ? "https://www.ozon.ru/product/" + pid + "/"
        : "https://www.wildberries.ru/catalog/" + pid + "/detail.aspx");
  }

  const { settings } = await getAll();
  let price = msg.priceHint != null ? msg.priceHint : null;
  let title = msg.titleHint || (source === "web" ? url : t("productDefault", pid));
  let currency = msg.currencyHint || null;
  let needsTab = false;
  const draft = {
    source: source,
    url: url,
    pickSel: msg.pickSel || null,
    needsTab: false
  };
  if (source === "ozon") draft.pid = pid;
  if (source === "wb") draft.nmId = pid;
  const info = await fetchInfo(draft, settings).catch(function () {
    return null;
  });
  if (info) {
    if (info.price != null) price = info.price;
    if (info.title) title = info.title;
    if (info.currency) currency = info.currency;
    if (info.viaTab) needsTab = true;
  }
  if (price == null) {
    const errors = {
      wb: t("errWbNoPrice"),
      ozon: t("errOzonNoPrice"),
      web: t("errWebNoPrice")
    };
    return { ok: false, error: errors[source] };
  }

  const item = {
    id: id,
    source: source,
    url: url,
    title: title,
    currency: currency || "RUB",
    target: null,
    added: Date.now(),
    lastChecked: Date.now(),
    lastPrice: price,
    history: [{ t: Date.now(), p: price }]
  };
  if (source === "ozon") item.pid = pid;
  if (source === "wb") item.nmId = pid;
  if (source === "web" && msg.pickSel) item.pickSel = String(msg.pickSel);
  if (needsTab) item.needsTab = true;
  return mutateItems(function (items) {
    if (items.some(function (x) {
      return x.id === id;
    })) return { ok: true, existed: true };
    items.push(item);
    return { ok: true, item: item };
  });
}

async function setupAlarm(opts) {
  const { settings } = await getAll();
  await browser.alarms.clear(ALARM);
  const alarm = { periodInMinutes: settings.intervalMin };
  if (opts && opts.delayFirst) alarm.delayInMinutes = 1;
  browser.alarms.create(ALARM, alarm);
}

browser.alarms.onAlarm.addListener((a) => {
  if (a.name === ALARM) checkAll();
});
browser.runtime.onInstalled.addListener((details) => {
  setupAlarm({ delayFirst: details.reason === "install" });
});
browser.runtime.onStartup.addListener(() => setupAlarm());

(async function resumePendingChecks() {
  await closeOrphanTabs();
  const raw = await sessionGet({ pending: [] });
  const pending = raw.pending || [];
  if (!pending.length) return;
  const { items, settings } = await getAll();
  for (const id of pending) {
    const item = items.find(function (x) {
      return x.id === id;
    });
    if (item) queueCheck(item, settings);
    else pendingRemove(id);
  }
})();

browser.runtime.onMessage.addListener((msg) => {
  switch (msg && msg.type) {
    case "isTracked":
      return getAll().then(({ items }) => items.some((x) => x.id === msg.id));
    case "getItem":
      return getAll().then(
        ({ items }) => items.find((x) => x.id === msg.id) || null
      );
    case "addItem":
      return addItem(msg);
    case "checkNow":
      return checkAll();
    case "checkOne":
      return checkOne(msg.id);
    case "priceSeen":
      return (async function () {
        if (!msg.id || msg.price == null) return false;
        if (inFlight.has(msg.id)) return false;
        const { settings } = await getAll();
        const res = await applyResult(msg.id, settings, {
          price: msg.price,
          currency: msg.currency || null
        }).catch(function () {
          return null;
        });
        return res != null && res !== "gone";
      })();
    case "updateItem":
      return mutateItems(function (items) {
        const it = items.find(function (x) {
          return x.id === msg.id;
        });
        if (!it) return false;
        Object.assign(it, msg.patch || {});
        return true;
      });
    case "removeItems":
      return mutateItems(function (items) {
        const drop = new Set(msg.ids || []);
        const keep = items.filter(function (x) {
          return !drop.has(x.id);
        });
        if (keep.length === items.length) return false;
        items.length = 0;
        items.push.apply(items, keep);
        return true;
      });
    case "clearItems":
      return mutateItems(function (items) {
        if (!items.length) return false;
        items.length = 0;
        return true;
      });
    case "importItems":
      return mutateItems(function (items) {
        let added = 0;
        for (const it of msg.items || []) {
          if (!it || !it.id || !Array.isArray(it.history)) continue;
          if (items.some(function (x) {
            return x.id === it.id;
          })) continue;
          items.push(it);
          added++;
        }
        return added;
      });
    case "updateSettings":
      return mutateSettings(function (settings) {
        Object.assign(settings, msg.patch || {});
        if (msg.patch && msg.patch.folders && !Array.isArray(settings.folders)) {
          settings.folders = [];
        }
        return true;
      });
    case "reschedule":
      return setupAlarm();
    case "tgDetect":
      return tgDetect(msg.token);
    case "tgTest":
      return getAll().then(({ settings }) =>
        tgSend(settings, t("tgTestMsg"))
      );
    default:
      return undefined;
  }
});