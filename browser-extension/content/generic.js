"use strict";

(function () {
  if (window.top !== window) return;

  let currentUrl = null;
  let attempts = 0;
  let root = null;

  function normUrl() {
    let out = location.origin + location.pathname;
    if (location.pathname !== "/") out = out.replace(/\/+$/, "");
    const params = new URLSearchParams(location.search);
    const drop = [];
    params.forEach(function (v, k) {
      if (/^(utm_|aff_)/i.test(k) || /^(fbclid|gclid|yclid|ysclid|_openstat|spm|scm|pdp_npi|algo_pvid|algo_exp_id|gatewayAdapt|srcSns|terminal_id)$/i.test(k)) drop.push(k);
    });
    for (const k of drop) params.delete(k);
    const q = params.toString();
    return q ? out + "?" + q : out;
  }

  function parseNum(v) {
    if (v == null) return null;
    const n = parseFloat(String(v).replace(/[\s\u00a0]/g, "").replace(",", "."));
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

  function fromJsonLd() {
    const candidates = [];
    const collect = function (x) {
      if (Array.isArray(x)) x.forEach(collect);
      else if (x && typeof x === "object") {
        candidates.push(x);
        if (x["@graph"]) collect(x["@graph"]);
      }
    };
    const nodes = document.querySelectorAll('script[type="application/ld+json"]');
    for (const node of nodes) {
      try {
        collect(JSON.parse(node.textContent));
      } catch (e) {
        /* invalid JSON */
      }
    }
    const pagePaths = [cleanPath(location.pathname)];
    const canonical = document.querySelector('link[rel="canonical"]');
    if (canonical && canonical.href) {
      try {
        pagePaths.push(cleanPath(new URL(canonical.href, location.href).pathname));
      } catch (e) {
        /* invalid canonical */
      }
    }
    const og = document.querySelector('meta[property="og:title"]');
    const h1 = document.querySelector("h1");
    const titleHint = (h1 && h1.textContent) || (og && og.getAttribute("content")) || "";
    const picked = pickProduct(candidates, location.href, pagePaths, titleHint);
    if (!picked) return null;
    const title = picked.d.name ? String(picked.d.name) : (document.title || "").trim();
    return { price: picked.offer.price, currency: picked.offer.currency, title: title };
  }

  function normCur(cur) {
    if (!cur) return null;
    let c = String(cur).trim().toUpperCase();
    if (c === "RUR") c = "RUB";
    return /^[A-Z]{3}$/.test(c) ? c : null;
  }

  function metaContent(names) {
    for (const n of names) {
      const el = document.querySelector('meta[property="' + n + '"], meta[name="' + n + '"], meta[itemprop="' + n + '"]');
      if (el && el.getAttribute("content")) return el.getAttribute("content");
    }
    return null;
  }

  function pageTitle() {
    const h1 = document.querySelector("h1");
    if (h1 && h1.textContent.trim()) return h1.textContent.trim();
    const og = metaContent(["og:title"]);
    if (og && og.trim()) return og.trim();
    return (document.title || "").trim();
  }

  function microdataProduct() {
    const scopes = document.querySelectorAll('[itemtype*="schema.org/Product"]');
    const hint = normTitle(pageTitle());
    let fallback = null;
    let withPrice = 0;
    for (const scope of scopes) {
      if (badSection(scope)) continue;
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
        title: (nameEl && nameEl.textContent.trim()) || pageTitle()
      };
      const name = normTitle(nameEl && nameEl.textContent);
      if (name && hint && (hint.indexOf(name) !== -1 || name.indexOf(hint) !== -1)) return cand;
      if (!fallback) fallback = cand;
    }
    return withPrice === 1 ? fallback : null;
  }

  function metaProduct() {
    const price = parseNum(metaContent(["product:price:amount", "og:price:amount", "price"]));
    if (price == null) return null;
    const og = normTitle(metaContent(["og:title"]));
    const h1el = document.querySelector("h1");
    const h1 = normTitle(h1el && h1el.textContent);
    if (og && h1 && og.indexOf(h1) === -1 && h1.indexOf(og) === -1) return null;
    return {
      price: price,
      currency: normCur(metaContent(["product:price:currency", "og:price:currency", "priceCurrency"])),
      title: pageTitle()
    };
  }

  function hardShop() {
    return /aliexpress\.|temu\./i.test(location.hostname);
  }

  function deepAllowed() {
    if (hardShop()) return true;
    const t = metaContent(["og:type"]);
    return Boolean(t && /product/i.test(t));
  }

  function scanState(rootObj) {
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
    return { price: best.value, currency: best.currency, title: title || pageTitle() };
  }

  function stateProduct() {
    if (!deepAllowed()) return null;
    const names = ["runParams", "__AER_DATA__", "rawData", "__INITIAL_STATE__", "__NUXT__"];
    const w = window.wrappedJSObject;
    for (const name of names) {
      let rootObj = null;
      try {
        if (w && w[name]) rootObj = JSON.parse(JSON.stringify(w[name]));
      } catch (e) {
        rootObj = null;
      }
      if (!rootObj) continue;
      const found = scanState(rootObj);
      if (found) return found;
    }
    const nd = document.getElementById("__NEXT_DATA__");
    if (nd) {
      try {
        const found = scanState(JSON.parse(nd.textContent));
        if (found) return found;
      } catch (e) {
        /* invalid JSON */
      }
    }
    return null;
  }

  function badSection(el) {
    let node = el;
    for (let i = 0; node && node.nodeType === 1 && i < 12; i++) {
      const tag = node.localName;
      if (tag === "nav" || tag === "footer" || tag === "header" || tag === "aside") return true;
      const cls = ((node.getAttribute("class") || "") + " " + (node.id || "")).toLowerCase();
      if (/related|similar|recommend|also-|alsobuy|upsell|cross-sell|carousel|slider|footer|header|menu|basket|cart|review|comment|history|product-block|products-week|week|discount-catalog|catalog__item|listing|grid-item|quick-view|__hover/.test(cls)) return true;
      node = node.parentElement;
    }
    return false;
  }

  function mainProductRoot() {
    const h1 = document.querySelector("h1");
    const selectors = [
      ".full-product",
      "[class*='full-product__content']",
      "[class*='product-page']",
      "[class*='product-detail']",
      "[class*='pdp']"
    ];
    if (h1) {
      for (let i = 0; i < selectors.length; i++) {
        const r = h1.closest(selectors[i]);
        if (r) return r;
      }
      let node = h1.parentElement;
      for (let i = 0; node && i < 10; i++) {
        const cls = ((node.getAttribute("class") || "") + " " + (node.id || "")).toLowerCase();
        if (/full-product|product-page|product-detail|pdp|product-info|product-card-main/.test(cls)) return node;
        node = node.parentElement;
      }
    }
    for (let i = 0; i < selectors.length; i++) {
      const el = document.querySelector(selectors[i]);
      if (el) return el;
    }
    return null;
  }

  function mainAreaProduct() {
    const root = mainProductRoot();
    if (!root) return null;
    const blocks = root.querySelectorAll(
      '[itemprop="price"], [class*="price" i], [class*="cost" i], [class*="descr" i], [class*="amount" i]'
    );
    let best = null;
    for (const el of blocks) {
      if (badSection(el)) continue;
      const found = priceFromText(textWithSiblings(el));
      if (!found || !found.currency) continue;
      let score = 24;
      try {
        score += parseFloat(getComputedStyle(el).fontSize) || 0;
      } catch (e) {
        /* getComputedStyle unavailable */
      }
      if (/old|origin|was|strike|prev|cross/i.test(el.getAttribute("class") || "")) score -= 15;
      if (el.closest("s, del, strike")) score -= 15;
      if (!best || score > best.score) best = { score: score, found: found };
    }
    if (best) {
      return { price: best.found.price, currency: best.found.currency, title: pageTitle() };
    }
    const fromRoot = priceFromText(root.textContent);
    if (fromRoot && fromRoot.currency) {
      return { price: fromRoot.price, currency: fromRoot.currency, title: pageTitle() };
    }
    return null;
  }

  function domProduct() {
    const h1 = document.querySelector("h1");
    if (!h1 && !hardShop()) return null;
    const h1Top = h1 ? h1.getBoundingClientRect().top + window.scrollY : 0;
    const mainRoot = mainProductRoot();
    const els = document.querySelectorAll('[itemprop="price"], [class*="rice"], [class*="cost" i], [class*="amount" i]');
    let best = null;
    for (const el of els) {
      if (el.childElementCount > 5) continue;
      const rect = el.getBoundingClientRect();
      if (!rect.width || !rect.height) continue;
      const found = priceFromElement(el);
      if (!found || !found.currency) continue;
      if (badSection(el)) continue;
      let score = 12;
      if (mainRoot && mainRoot.contains(el)) score += 20;
      try {
        score = parseFloat(getComputedStyle(el).fontSize) || 12;
      } catch (e) {
        /* getComputedStyle unavailable */
      }
      const top = rect.top + window.scrollY;
      if (Math.abs(top - h1Top) < 900) score += 8;
      if (/old|origin|cross|was-|strike|prev/i.test(el.getAttribute("class") || "")) score -= 12;
      if (el.closest("s, del, strike")) score -= 12;
      if (!best || score > best.score) best = { score: score, found: found };
    }
    if (!best) return null;
    return { price: best.found.price, currency: best.found.currency, title: pageTitle() };
  }

  let pickBox = null;
  let pickTarget = null;
  let pickTries = 0;
  let pickSent = false;

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

    // "2, 19 €" — integer and fraction in separate spans
    const splitEu = new RegExp("(\\d+)\\s*[,\\.]\\s*(\\d{2})\\s*(" + symRe + ")", "gi");
    let sm;
    while ((sm = splitEu.exec(s)) !== null) {
      const before = s.slice(Math.max(0, sm.index - 14), sm.index).toLowerCase();
      let score = 10;
      if (/\b(1\s*kg|kg|100\s*g|pro)\s*$/.test(before)) score -= 20;
      consider(parseNum(sm[1] + "." + sm[2]), symToCur(sm[3]), score, sm.index);
    }

    // "2 299 Kč" — space as thousands separator
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

  // Kaufland etc.: merge "2" and "299,- Kč" from sibling spans.
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

  function cssPath(el) {
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && node !== document.body && parts.length < 10) {
      if (node.id) {
        parts.unshift("#" + CSS.escape(node.id));
        return parts.join(" > ");
      }
      let i = 1;
      let sib = node;
      while ((sib = sib.previousElementSibling)) {
        if (sib.localName === node.localName) i++;
      }
      parts.unshift(node.localName + ":nth-of-type(" + i + ")");
      node = node.parentElement;
    }
    parts.unshift("body");
    return parts.join(" > ");
  }

  function toast(text) {
    const t = document.createElement("div");
    t.textContent = text;
    t.style.cssText = "position:fixed;left:50%;top:14px;transform:translateX(-50%);z-index:2147483647;background:#1f1f1f;color:#fff;font:13px/1.4 sans-serif;padding:9px 14px;border-radius:8px;box-shadow:0 4px 14px rgba(0,0,0,.3);max-width:80vw;";
    document.documentElement.appendChild(t);
    setTimeout(function () { t.remove(); }, 4000);
  }

  function pickMove(e) {
    if (!pickBox) return;
    const el = document.elementFromPoint(e.clientX, e.clientY);
    if (!el || pickBox.contains(el)) return;
    pickTarget = el;
    const r = el.getBoundingClientRect();
    const hl = pickBox.children[0];
    hl.style.display = "block";
    hl.style.top = r.top + "px";
    hl.style.left = r.left + "px";
    hl.style.width = r.width + "px";
    hl.style.height = r.height + "px";
    const found = priceFromElement(el);
    pickBox.children[1].textContent = found
      ? t("pickHoverPrice", found.price, found.currency || "")
      : t("pickHoverHint");
  }

  function pickClick(e) {
    if (!pickBox) return;
    e.preventDefault();
    e.stopPropagation();
    const el = pickTarget;
    if (!el) return;
    const found = priceFromElement(el);
    if (!found) {
      pickBox.children[1].textContent = t("pickNoNumber");
      return;
    }
    const sel = cssPath(el);
    stopPicker();
    browser.runtime
      .sendMessage({
        type: "addItem",
        source: "web",
        url: normUrl(),
        titleHint: pageTitle(),
        priceHint: found.price,
        currencyHint: found.currency || null,
        pickSel: sel
      })
      .then(function (res) {
        toast(res && res.ok ? t("trackOkPrice", found.price) : t("trackAddFailed"));
      })
      .catch(function () {
        toast(t("trackAddFailed"));
      });
  }

  function pickKey(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      stopPicker();
    }
  }

  function stopPicker() {
    if (pickBox) {
      pickBox.remove();
      pickBox = null;
    }
    pickTarget = null;
    document.removeEventListener("mousemove", pickMove, true);
    document.removeEventListener("click", pickClick, true);
    document.removeEventListener("keydown", pickKey, true);
  }

  function startPicker() {
    stopPicker();
    pickBox = document.createElement("div");
    pickBox.style.cssText = "position:fixed;inset:0;z-index:2147483647;pointer-events:none;";
    const hl = document.createElement("div");
    hl.style.cssText = "position:fixed;display:none;border:2px solid #2783DE;background:rgba(39,131,222,.12);border-radius:4px;";
    const label = document.createElement("div");
    label.style.cssText = "position:fixed;left:50%;top:14px;transform:translateX(-50%);background:#1f1f1f;color:#fff;font:13px/1.4 sans-serif;padding:9px 14px;border-radius:8px;box-shadow:0 4px 14px rgba(0,0,0,.3);max-width:80vw;";
    label.textContent = t("pickClickPrice");
    pickBox.appendChild(hl);
    pickBox.appendChild(label);
    document.documentElement.appendChild(pickBox);
    document.addEventListener("mousemove", pickMove, true);
    document.addEventListener("click", pickClick, true);
    document.addEventListener("keydown", pickKey, true);
  }

  browser.runtime.onMessage.addListener(function (msg) {
    if (msg && msg.type === "startPicker") {
      startPicker();
      return Promise.resolve(true);
    }
    if (msg && msg.type === "readPrice") {
      let found = null;
      if (msg.pickSel) {
        try {
          const el = document.querySelector(msg.pickSel);
          found = el ? priceFromElement(el) : null;
        } catch (e) {
          found = null;
        }
      }
      if (!found) {
        const p = findProduct();
        if (p) found = { price: p.price, currency: p.currency || null };
      }
      return Promise.resolve(found || null);
    }
    return undefined;
  });

  function tryPickSeen(u) {
    const id = "web:" + u;
    browser.runtime
      .sendMessage({ type: "getItem", id: id })
      .then(function (item) {
        if (pickSent) return;
        if (!item || !item.pickSel) {
          pickSent = true;
          return;
        }
        let el = null;
        try {
          el = document.querySelector(item.pickSel);
        } catch (e) {
          el = null;
        }
        const found = el && priceFromElement(el);
        if (!found) return;
        pickSent = true;
        browser.runtime
          .sendMessage({
            type: "priceSeen",
            id: id,
            price: found.price,
            currency: found.currency || item.currency || null
          })
          .catch(function () {});
      })
      .catch(function () {});
  }

  function findProduct() {
    return (
      fromJsonLd() ||
      microdataProduct() ||
      metaProduct() ||
      mainAreaProduct() ||
      domProduct() ||
      stateProduct()
    );
  }

  function removeWidget() {
    if (root) {
      root.remove();
      root = null;
    }
  }

  function mount(product) {
    removeWidget();
    const widget = cennikCreateWidget(t("trackPriceBtn"));
    root = widget.root;
    const btn = widget.btn;
    document.documentElement.appendChild(root);

    function setDone(text) {
      btn.disabled = true;
      btn.classList.add("cennik-done");
      btn.textContent = text || t("tracking");
    }

    browser.runtime
      .sendMessage({ type: "isTracked", id: "web:" + normUrl() })
      .then((tracked) => {
        if (!tracked) return;
        setDone();
        browser.runtime
          .sendMessage({
            type: "priceSeen",
            id: "web:" + normUrl(),
            price: product.price,
            currency: product.currency || null
          })
          .catch(() => {});
      })
      .catch(() => {});

    btn.addEventListener("click", () => {
      btn.disabled = true;
      btn.textContent = t("adding");
      browser.runtime
        .sendMessage({
          type: "addItem",
          source: "web",
          url: normUrl(),
          titleHint: product.title,
          priceHint: product.price,
          currencyHint: product.currency || null
        })
        .then((res) => {
          if (res && res.ok) {
            setDone(t("trackDonePopup"));
          } else {
            btn.disabled = false;
            btn.textContent = t("trackError");
          }
        })
        .catch(() => {
          btn.disabled = false;
          btn.textContent = t("trackError");
        });
    });
  }

  function tick() {
    const u = normUrl();
    if (u !== currentUrl) {
      currentUrl = u;
      attempts = 0;
      pickTries = 0;
      pickSent = false;
      removeWidget();
    }
    if (!pickSent && pickTries < 15) {
      pickTries++;
      tryPickSeen(u);
    }
    if (root || attempts >= 15) return;
    attempts++;
    const product = findProduct();
    if (product) mount(product);
  }

  tick();
  setInterval(tick, 1500);
})();