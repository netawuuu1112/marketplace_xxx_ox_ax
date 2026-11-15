"use strict";

function t(key) {
  var subs = [];
  for (var i = 1; i < arguments.length; i++) subs.push(String(arguments[i]));
  return browser.i18n.getMessage(key, subs) || key;
}

function uiLocale() {
  var lang = browser.i18n.getUILanguage() || "en";
  return lang.split("-")[0];
}

function fmtLocale() {
  return uiLocale() === "ru" ? "ru-RU" : "en-US";
}

function applyDom(root) {
  if (typeof document === "undefined") return;
  root = root || document;
  root.querySelectorAll("[data-i18n]").forEach(function (el) {
    el.textContent = t(el.getAttribute("data-i18n"));
  });
  root.querySelectorAll("[data-i18n-placeholder]").forEach(function (el) {
    el.placeholder = t(el.getAttribute("data-i18n-placeholder"));
  });
  root.querySelectorAll("[data-i18n-title]").forEach(function (el) {
    el.title = t(el.getAttribute("data-i18n-title"));
  });
  root.querySelectorAll("[data-i18n-aria]").forEach(function (el) {
    el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria")));
  });
}
