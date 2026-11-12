"use strict";

(function () {
  let currentPid = null;
  let root = null;

  function pidFromLocation() {
    const m = location.pathname.match(/\/product\/(?:[^\/?#]*-)?(\d{5,})/);
    return m ? m[1] : null;
  }

  function fromJsonLd() {
    const out = { price: null, title: null };
    const nodes = document.querySelectorAll('script[type="application/ld+json"]');
    for (const node of nodes) {
      let data;
      try {
        data = JSON.parse(node.textContent);
      } catch (e) {
        continue;
      }
      const list = Array.isArray(data) ? data : [data];
      for (const d of list) {
        if (!d || d["@type"] !== "Product") continue;
        const offers = Array.isArray(d.offers) ? d.offers[0] : d.offers;
        if (offers && offers.price != null) {
          const p = Math.round(parseFloat(String(offers.price)));
          if (p > 0) out.price = p;
        }
        if (d.name) out.title = String(d.name);
        return out;
      }
    }
    return out;
  }

  function parseNum(raw) {
    if (raw == null) return null;
    const s = String(raw).replace(/\u00a0/g, " ").replace(/\s/g, "").replace(",", ".");
    const n = parseFloat(s);
    return isFinite(n) && n > 0 ? Math.round(n) : null;
  }

  function priceFromText(txt) {
    const s = String(txt || "").replace(/\u00a0/g, " ").trim();
    if (!s) return null;
    const m = s.match(/([\d\s]+(?:[.,]\d{1,2})?)\s*(?:₽|руб)/i);
    if (m) return parseNum(m[1]);
    const bare = s.match(/^[\d\s.,]+$/);
    if (bare) return parseNum(s);
    return null;
  }

  function priceFromElement(el) {
    if (!el) return null;
    const content = el.getAttribute && el.getAttribute("content");
    if (content != null && String(content).trim() !== "") {
      const p = parseNum(content);
      if (p != null) return { price: p, currency: "RUB" };
    }
    const p = priceFromText(el.textContent);
    if (p != null) return { price: p, currency: "RUB" };
    return null;
  }

  function microdataPrice() {
    const scopes = document.querySelectorAll('[itemtype*="schema.org/Product"]');
    for (const scope of scopes) {
      const priceEl = scope.querySelector('[itemprop="price"]');
      const found = priceFromElement(priceEl);
      if (found) return found;
    }
    const lone = document.querySelector('[itemprop="price"]');
    return priceFromElement(lone);
  }

  function domPrice() {
    const sels = [
      '[data-widget="webPrice"]',
      '[data-widget="webSale"]',
      '[data-widget="webCurrentPrice"]',
      'span[class*="price"]'
    ];
    for (const sel of sels) {
      const nodes = document.querySelectorAll(sel);
      for (const el of nodes) {
        const found = priceFromElement(el);
        if (found) return found;
        const p = priceFromText(el.textContent);
        if (p != null) return { price: p, currency: "RUB" };
      }
    }
    return null;
  }

  function findPrice() {
    const ld = fromJsonLd();
    if (ld.price != null) return { price: ld.price, currency: "RUB" };
    return microdataPrice() || domPrice() || null;
  }

  function titleFromDom() {
    const ld = fromJsonLd();
    if (ld.title) return ld.title;
    const h = document.querySelector("h1");
    return h ? h.textContent.trim() : document.title;
  }

  function removeWidget() {
    if (root) {
      root.remove();
      root = null;
    }
  }

  function mount(pid) {
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
      .sendMessage({ type: "isTracked", id: "ozon:" + pid })
      .then((tracked) => {
        if (tracked) setDone();
      })
      .catch(() => {});

    btn.addEventListener("click", () => {
      btn.disabled = true;
      btn.textContent = t("adding");
      browser.runtime
        .sendMessage({
          type: "addItem",
          source: "ozon",
          pid: pid,
          url: location.origin + location.pathname,
          titleHint: titleFromDom(),
          priceHint: fromJsonLd().price
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

  browser.runtime.onMessage.addListener(function (msg) {
    if (msg && msg.type === "readPrice") {
      return Promise.resolve(findPrice());
    }
    return undefined;
  });

  function tick() {
    const pid = pidFromLocation();
    if (pid !== currentPid) {
      currentPid = pid;
      if (pid) {
        mount(pid);
      } else {
        removeWidget();
      }
    }
  }

  tick();
  setInterval(tick, 1500);
})();
