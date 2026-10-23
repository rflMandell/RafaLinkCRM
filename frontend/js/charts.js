// ---------- Gráficos em HTML/SVG puro (Etapa 6) ----------
// Regras: marcas finas, grade em hairline, valor na ponta, tooltip que só complementa
// (todo valor também está na tabela), e textos de usuário sempre via textContent.
const NF = new Intl.NumberFormat("pt-BR");
const NF_COMPACT = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });
const NF_1 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
const RAMP = ["var(--ramp-1)", "var(--ramp-2)", "var(--ramp-3)", "var(--ramp-4)", "var(--ramp-5)"];

// ----- tooltip único -----
let tipEl = null;
function showTip(x, y, value, label) {
  if (!tipEl) {
    tipEl = document.createElement("div");
    tipEl.className = "viz-tip";
    tipEl.setAttribute("role", "tooltip");
    document.body.appendChild(tipEl);
  }
  const v = document.createElement("div"); v.className = "viz-tip-value"; v.textContent = value;
  const l = document.createElement("div"); l.className = "viz-tip-label"; l.textContent = label;
  tipEl.replaceChildren(v, l);
  tipEl.hidden = false;
  const w = tipEl.offsetWidth, h = tipEl.offsetHeight;
  let left = x + 14; if (left + w > innerWidth - 8) left = x - w - 14;
  let top = y - h - 12; if (top < 8) top = y + 14;
  tipEl.style.left = left + "px"; tipEl.style.top = top + "px";
}
function hideTip() { if (tipEl) tipEl.hidden = true; }

// ----- tiles (KPIs) -----
// delta: variação % vs período anterior. upIsGood=false inverte a cor (ex.: tempo de ciclo).
function pctDelta(cur, prev) {
  if (cur == null || prev == null || prev === 0) return null;
  return ((cur - prev) / Math.abs(prev)) * 100;
}
function statTile(label, valueText, delta = null, upIsGood = true) {
  let d = `<div class="delta">sem período anterior</div>`;
  if (delta !== null) {
    const up = delta > 0, flat = Math.abs(delta) < 0.05;
    const good = flat ? "" : (up === upIsGood ? "good" : "bad");
    // seta + texto: a cor nunca carrega o significado sozinha
    d = `<div class="delta ${good}">${flat ? "■" : up ? "▲" : "▼"} ${NF_1.format(Math.abs(delta))}% vs período anterior</div>`;
  }
  return `<div class="tile"><div class="label">${esc(label)}</div><div class="value">${esc(valueText)}</div>${d}</div>`;
}

// ----- barras horizontais -----
// items: [{label, value, tip?}]. colors: lista opcional (rampa ordinal por posição).
function hbarChart(box, items, { format = (v) => NF.format(v), colors = null } = {}) {
  box.replaceChildren();
  if (!items.length) { box.innerHTML = `<div class="empty">Sem dados no período.</div>`; return; }
  const max = Math.max(...items.map((i) => i.value), 1);
  // reserva espaço para o valor na ponta da barra (o texto nunca sai do cartão)
  const reserve = Math.max(...items.map((i) => format(i.value).length)) * 8 + 20;
  const wrap = document.createElement("div"); wrap.className = "hbar"; wrap.setAttribute("role", "list");
  items.forEach((it, idx) => {
    const row = document.createElement("div"); row.className = "hbar-row"; row.tabIndex = 0; row.setAttribute("role", "listitem");
    const label = document.createElement("span"); label.className = "hbar-label"; label.textContent = it.label;
    const track = document.createElement("span"); track.className = "hbar-track";
    const bar = document.createElement("span"); bar.className = "hbar-bar";
    bar.style.width = `calc((100% - ${reserve}px) * ${it.value / max})`;
    if (colors) bar.style.background = colors[Math.min(idx, colors.length - 1)];
    const val = document.createElement("span"); val.className = "hbar-val"; val.textContent = format(it.value);
    track.append(bar, val); row.append(label, track);
    const text = it.tip || it.label;
    const show = (e) => {
      const r = row.getBoundingClientRect();
      showTip(e.clientX ?? r.left + 40, e.clientY ?? r.top, format(it.value), text);
    };
    row.addEventListener("pointermove", show);
    row.addEventListener("focus", show);
    row.addEventListener("pointerleave", hideTip);
    row.addEventListener("blur", hideTip);
    wrap.appendChild(row);
  });
  box.appendChild(wrap);
}

// ----- linha (série única) -----
function axisTicks(max) {
  if (max <= 4) { const top = Math.max(1, Math.ceil(max)); return Array.from({ length: top + 1 }, (_, i) => i); }
  const raw = max / 4, p = Math.pow(10, Math.floor(Math.log10(raw))), n = raw / p;
  const step = (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
  return [0, 1, 2, 3, 4].map((i) => i * step);
}
function lineChart(box, points, { unit = "leads", bucketDays = 1 } = {}) {
  box.replaceChildren();
  if (!points.length) { box.innerHTML = `<div class="empty">Sem dados no período.</div>`; return; }
  const W = 720, H = 240, L = 40, R = 18, T = 14, B = 28;
  const ticks = axisTicks(Math.max(...points.map((p) => p.value), 0));
  const top = ticks[ticks.length - 1];
  const x = (i) => L + (points.length === 1 ? (W - L - R) / 2 : (i * (W - L - R)) / (points.length - 1));
  const y = (v) => T + (H - T - B) * (1 - v / top);
  const NS = "http://www.w3.org/2000/svg";
  const el = (name, attrs = {}, text) => {
    const n = document.createElementNS(NS, name);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (text !== undefined) n.textContent = text;
    return n;
  };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "line-svg", role: "img", tabindex: 0,
    "aria-label": `Linha de ${unit} por ${bucketDays === 1 ? "dia" : "semana"}. Use as setas para navegar.` });

  ticks.forEach((t) => {
    svg.appendChild(el("line", { class: "grid-line", x1: L, x2: W - R, y1: y(t), y2: y(t) }));
    svg.appendChild(el("text", { x: L - 8, y: y(t) + 4, "text-anchor": "end" }, NF_COMPACT.format(t)));
  });
  // 5 rótulos de data, espaçados
  const labelIdx = [...new Set([0, 1, 2, 3, 4].map((k) => Math.round((k * (points.length - 1)) / 4)))];
  labelIdx.forEach((i) => {
    const [, m, d] = points[i].date.split("-");
    svg.appendChild(el("text", { x: x(i), y: H - 8, "text-anchor": i === 0 ? "start" : i === points.length - 1 ? "end" : "middle" }, `${d}/${m}`));
  });

  const line = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join("");
  svg.appendChild(el("path", { class: "area", d: `${line}L${x(points.length - 1)},${y(0)}L${x(0)},${y(0)}Z` }));
  svg.appendChild(el("path", { class: "series", d: line }));

  const last = points.length - 1;
  svg.appendChild(el("circle", { class: "dot", cx: x(last), cy: y(points[last].value), r: 4 }));
  svg.appendChild(el("text", { class: "end-label", x: x(last), y: y(points[last].value) - 10, "text-anchor": "end" }, NF.format(points[last].value)));

  const cross = el("line", { class: "cross", y1: T, y2: H - B, visibility: "hidden" });
  const hot = el("circle", { class: "dot", r: 4, visibility: "hidden" });
  svg.append(cross, hot);

  const fmtPoint = (p) => {
    const [yy, m, d] = p.date.split("-");
    return bucketDays === 1 ? `${d}/${m}/${yy}` : `Semana de ${d}/${m}/${yy}`;
  };
  const focusAt = (i, clientX, clientY) => {
    i = Math.max(0, Math.min(points.length - 1, i));
    cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
    hot.setAttribute("cx", x(i)); hot.setAttribute("cy", y(points[i].value)); hot.setAttribute("visibility", "visible");
    const r = svg.getBoundingClientRect(), k = r.width / W;
    showTip(clientX ?? r.left + x(i) * k, clientY ?? r.top + y(points[i].value) * k, `${NF.format(points[i].value)} ${unit}`, fmtPoint(points[i]));
    return i;
  };
  const clear = () => { cross.setAttribute("visibility", "hidden"); hot.setAttribute("visibility", "hidden"); hideTip(); };
  const nearest = (e) => {
    const r = svg.getBoundingClientRect(), px = ((e.clientX - r.left) / r.width) * W;
    return Math.round(((px - L) / (W - L - R)) * (points.length - 1));
  };
  svg.addEventListener("pointermove", (e) => focusAt(nearest(e), e.clientX, e.clientY));
  svg.addEventListener("pointerleave", clear);
  let cur = last;
  svg.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") { cur = focusAt(cur - 1); e.preventDefault(); }
    if (e.key === "ArrowRight") { cur = focusAt(cur + 1); e.preventDefault(); }
  });
  svg.addEventListener("focus", () => { cur = focusAt(cur); });
  svg.addEventListener("blur", clear);
  box.appendChild(svg);
}

// ----- cartão com alternância Gráfico/Tabela (a tabela é o gêmeo acessível) -----
const viewPref = {};
// spec: {id, title, subtitle, wide, render(box), columns:[...], rows:[[...]]}  (rows em texto puro)
function mountChartCard(slot, spec) {
  const pref = viewPref[spec.id] || "chart";
  slot.className = "viz-card" + (spec.wide ? " wide" : "");
  slot.innerHTML = `
    <div class="viz-head">
      <div><h3>${esc(spec.title)}</h3><div class="muted">${esc(spec.subtitle || "")}</div></div>
      <div class="viz-toggle" role="group" aria-label="Modo de exibição">
        <button type="button" data-v="chart" aria-pressed="${pref === "chart"}">Gráfico</button>
        <button type="button" data-v="table" aria-pressed="${pref === "table"}">Tabela</button>
      </div>
    </div>
    <div class="viz-chart" ${pref === "table" ? "hidden" : ""}></div>
    <div class="viz-table" ${pref === "chart" ? "hidden" : ""}></div>`;
  spec.render(slot.querySelector(".viz-chart"));
  slot.querySelector(".viz-table").innerHTML = `
    <table class="grid"><thead><tr>${spec.columns.map((c, i) => `<th class="${i ? "num" : ""}">${esc(c)}</th>`).join("")}</tr></thead>
    <tbody>${spec.rows.map((r) => `<tr>${r.map((c, i) => `<td class="${i ? "num" : ""}">${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  slot.querySelectorAll(".viz-toggle button").forEach((b) =>
    b.addEventListener("click", () => {
      viewPref[spec.id] = b.dataset.v;
      hideTip();
      slot.querySelectorAll(".viz-toggle button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      slot.querySelector(".viz-chart").hidden = b.dataset.v !== "chart";
      slot.querySelector(".viz-table").hidden = b.dataset.v !== "table";
    })
  );
}