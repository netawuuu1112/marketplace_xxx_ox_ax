"use strict";

function cennikCreateWidget(buttonLabel) {
  const NS = "http://www.w3.org/2000/svg";
  const root = document.createElement("div");
  root.id = "cennik-widget";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 26 26");
  svg.setAttribute("fill", "none");
  svg.setAttribute("aria-hidden", "true");
  const rect = document.createElementNS(NS, "rect");
  rect.setAttribute("x", "1");
  rect.setAttribute("y", "1");
  rect.setAttribute("width", "24");
  rect.setAttribute("height", "24");
  rect.setAttribute("rx", "7");
  rect.setAttribute("fill", "#2783DE");
  const path = document.createElementNS(NS, "path");
  path.setAttribute("d", "M7 15.5 11 11l3 3 5-6");
  path.setAttribute("stroke", "#fff");
  path.setAttribute("stroke-width", "2.2");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  svg.appendChild(rect);
  svg.appendChild(path);
  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = buttonLabel;
  root.appendChild(svg);
  root.appendChild(btn);
  return { root: root, btn: btn };
}
