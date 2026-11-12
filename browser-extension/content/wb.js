"use strict";

(function () {
  let currentNm = null;
  let root = null;

  function nmFromLocation() {
    const m = location.pathname.match(/\/catalog\/(\d+)/);
    return m ? m[1] : null;
  }

  function priceFromDom() {
    const el = document.querySelector(
      'ins.price-block__final-price, [class*="price-block__final-price"]'
    );
    if (!el) return null;
    const digits = el.textContent.replace(/[^\d]/g, "");
    return digits ? parseInt(digits, 10) : null;
  }

  function titleFromDom() {
    const h = document.querySelector("h1");
    return h ? h.textContent.trim() : document.title;
  }

  function removeWidget() {
    if (root) {
      root.remove();
      root = null;
    }
  }

  function mount(nmId) {
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
      .sendMessage({ type: "isTracked", id: "wb:" + nmId })
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
          source: "wb",
          nmId: nmId,
          url: location.origin + location.pathname,
          titleHint: titleFromDom(),
          priceHint: priceFromDom()
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
    const nm = nmFromLocation();
    if (nm !== currentNm) {
      currentNm = nm;
      if (nm) {
        mount(nm);
      } else {
        removeWidget();
      }
    }
  }

  tick();
  setInterval(tick, 1500);
})();