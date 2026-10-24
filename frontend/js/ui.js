const STATUS_LABEL = {
  NOVO: "Novo", EM_CONTATO: "Em contato", QUALIFICADO: "Qualificado",
  OPORTUNIDADE: "Oportunidade", CONVERTIDO: "Convertido", PERDIDO: "Perdido", ARQUIVADO: "Arquivado",
};

const CHANNEL_LABEL = {
  EMAIL: "E-mail", WHATSAPP: "WhatsApp", SMS: "SMS", REDES_SOCIAIS: "Redes sociais",
  SITE: "Site", EVENTO: "Evento", OUTROS: "Outros",
};

const TYPE_LABEL = { PROSPECT: "Prospect", CLIENTE: "Cliente" };
const CONTACT_STATUS_LABEL = { ATIVO: "Ativo", INATIVO: "Inativo" };
const PREFERENCE_LABEL = { EMAIL: "E-mail", WHATSAPP: "WhatsApp", TELEFONE: "Telefone", NENHUMA: "Sem preferência" };

// Quando uma etapa for implementada, basta trocar "stage" por "href" no item do menu.
const MENU = [
  { key: "dashboard", label: "Dashboard", href: "app.html" },
  { key: "leads", label: "Leads", href: "leads.html" },
  { key: "companies", label: "Empresas", href: "companies.html" },
  { key: "contacts", label: "Contatos", href: "contacts.html" },
  { key: "pipeline", label: "Pipeline", href: "pipeline.html" },
  { key: "tasks", label: "Tarefas", href: "tasks.html" },
  { key: "agenda", label: "Agenda", href: "agenda.html" },
  { key: "activities", label: "Atividades", href: "activities.html" },
  { key: "campaigns", label: "Campanhas", href: "campaigns.html" },
  { key: "forecast", label: "Forecast", href: "forecast.html" },
  { key: "goals", label: "Metas", href: "goals.html" },
  { key: "sla", label: "SLA", href: "sla.html" },
  { key: "ai", label: "IA", href: "ai.html" },
  //{ key: "notifications", label: "Notificações", href: "notifications.html" }, //ta bugada a pag, entao mais facil deixar off por enquanto
  { key: "automations", label: "Automação", href: "automations.html" },
  { key: "audit", label: "Auditoria", href: "audit.html" },
  { key: "settings", label: "Configurações", href: "settings.html" },
];

// Sempre use esc() ao colocar dados do usuário dentro de innerHTML (evita XSS).
function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function fmtDate(iso) {
  return iso ? new Date(iso).toLocaleDateString("pt-BR") : "—";
}

function fmtDateTime(iso) {
  return iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—";
}

function statusBadge(status) {
  return `<span class="badge st-${esc(status)}">${esc(STATUS_LABEL[status] || status)}</span>`;
}

function toast(message, type = "ok") {
  const el = document.createElement("div");
  el.className = "toast " + (type === "err" ? "err" : "");
  el.textContent = message;
  document.getElementById("toasts").appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// Monta menu lateral + topo dentro de <div id="app"></div> e devolve a área de conteúdo.
function renderLayout(activeKey, title) {
  requireAuth();
  const user = getUser() || {};
  const links = MENU.map((m) =>
    m.href
      ? `<a href="${m.href}" class="${m.key === activeKey ? "active" : ""}">${m.label}</a>`
      : `<a class="soon">${m.label} <span class="tag">Etapa ${m.stage}</span></a>`
  ).join("");

  document.getElementById("app").innerHTML = `
    <div class="layout">
      <aside class="sidebar">
        <div class="brand">RafaLink CRM</div>
        ${links}
      </aside>
      <main>
        <div class="topbar">
          <strong>${esc(title)}</strong>
          <div class="gsearch" id="gsearch">
            <input id="gsInput" type="search" placeholder="Buscar em tudo…  ( / )" aria-label="Busca global" autocomplete="off" />
            <div class="gs-menu" id="gsMenu" hidden></div>
          </div>
          <div class="topbar-right">
            <div class="bell-wrap">
              <button id="bellBtn" class="bell" aria-label="Notificações" aria-haspopup="true"><span aria-hidden="true">🔔</span><span class="bell-count" id="bellCount" hidden>0</span></button>
              <div class="bell-menu" id="bellMenu" hidden></div>
            </div>
            <span class="who">${esc(user.name)} · ${esc(user.role)}</span>
            <button id="logoutBtn">Sair</button>
          </div>
        </div>
        <div class="content" id="content"></div>
      </main>
    </div>
    <div id="toasts"></div>`;

  document.getElementById("logoutBtn").addEventListener("click", logout);
  initBell();
  initGlobalSearch();
  return document.getElementById("content");
}

function typeBadge(type) {
  return `<span class="badge ty-${esc(type)}">${esc(TYPE_LABEL[type] || type)}</span>`;
}

function contactStatusBadge(status) {
  return `<span class="badge ct-${esc(status)}">${esc(CONTACT_STATUS_LABEL[status] || status)}</span>`;
}

// Só ADMIN e SALES_MANAGER veem o botão de excluir (o backend também bloqueia).
function canDelete() {
  return ["ADMIN", "SALES_MANAGER"].includes((getUser() || {}).role);
}

function infoCard(label, value) {
  return `<div class="card"><div class="label">${esc(label)}</div><div class="value sm">${esc(value || "—")}</div></div>`;
}

function linkCard(label, href, text) {
  return `<div class="card"><div class="label">${esc(label)}</div>
    <div class="value sm"><a class="link" href="${esc(href)}">${esc(text)}</a></div></div>`;
}

function fillSelect(id, pairs) {
  document.getElementById(id).insertAdjacentHTML(
    "beforeend",
    pairs.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join("")
  );
}

function debounce(fn, ms = 300) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

// Paginação padrão: go(-1) = página anterior, go(1) = próxima.
function renderPager(el, data, noun, go) {
  const pages = Math.max(data.totalPages, 1);
  el.innerHTML = `
    <span>Página ${data.page + 1} de ${pages} · ${data.totalElements} ${noun}</span>
    <div>
      <button class="btn" data-dir="-1" ${data.page === 0 ? "disabled" : ""}>Anterior</button>
      <button class="btn" data-dir="1" ${data.page + 1 >= pages ? "disabled" : ""}>Próxima</button>
    </div>`;
  el.querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => go(Number(b.dataset.dir)))
  );
}

const OPP_STATUS_LABEL = { ABERTA: "Aberta", GANHA: "Ganha", PERDIDA: "Perdida" };

function oppStatusBadge(status) {
  return `<span class="badge os-${esc(status)}">${esc(OPP_STATUS_LABEL[status] || status)}</span>`;
}

const BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

function fmtMoney(v) {
  return BRL.format(Number(v || 0));
}

// Datas sem horário ("2026-11-30") não podem passar por new Date(): o fuso mudaria o dia.
function fmtDay(s) {
  if (!s) return "—";
  const [y, m, d] = s.split("-");
  return `${d}/${m}/${y}`;
}

function daysSince(iso) {
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
}

// ---------- Etapa 9: sino de notificações ----------
const NOTIF_PAGE = {
  lead: (id) => `lead.html?id=${id}`,
  opportunity: (id) => `opportunity.html?id=${id}`,
  company: (id) => `company.html?id=${id}`,
  activity: () => "tasks.html",
};
function notifLink(n) { const f = NOTIF_PAGE[n.entity]; return f ? f(n.entityId) : null; }

function timeAgo(iso) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "agora";
  if (s < 3600) return `há ${Math.floor(s / 60)} min`;
  if (s < 86400) return `há ${Math.floor(s / 3600)} h`;
  return `há ${Math.floor(s / 86400)} d`;
}

function initBell() {
  const btn = document.getElementById("bellBtn");
  const menu = document.getElementById("bellMenu");
  const badge = document.getElementById("bellCount");
  if (!btn) return;

  async function refresh() {
    try {
      const { count } = await api("/notifications/unread-count");
      badge.textContent = count > 99 ? "99+" : count;
      badge.hidden = count === 0;
      btn.setAttribute("aria-label", `Notificações (${count} não lidas)`);
    } catch { /* sem rede: mantém o último valor */ }
  }

  async function openMenu() {
    try {
      const r = await api("/notifications?size=6");
      menu.innerHTML = (r.content.length ? r.content.map((n) => `
        <a class="bell-item ${n.read ? "" : "unread"}" href="${notifLink(n) || "notifications.html"}" data-id="${n.id}">
          <strong>${esc(n.title)}</strong><span>${esc(n.message || "")}</span><em>${timeAgo(n.createdAt)}</em>
        </a>`).join("") : `<div class="bell-empty">Nenhuma notificação.</div>`) + `
        <div class="bell-foot"><button type="button" id="bellReadAll">Marcar todas como lidas</button>
        <a href="notifications.html">Ver todas</a></div>`;
      menu.querySelectorAll(".bell-item").forEach((a) => a.addEventListener("click", () => {
        api(`/notifications/${a.dataset.id}/read`, { method: "POST" }).catch(() => {});
      }));
      menu.querySelector("#bellReadAll").addEventListener("click", async () => {
        await api("/notifications/read-all", { method: "POST" }); refresh(); openMenu();
      });
    } catch (e) { menu.innerHTML = `<div class="bell-empty">${esc(e.message)}</div>`; }
  }

  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    menu.hidden = !menu.hidden;
    if (!menu.hidden) openMenu();
  });
  document.addEventListener("click", (e) => { if (!menu.contains(e.target)) menu.hidden = true; });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") menu.hidden = true; });
  btn.addEventListener("refresh", refresh);   // outras páginas pedem atualização com btn.dispatchEvent(new Event("refresh"))
  refresh();
  setInterval(refresh, 30000);
}

// ---------- Etapa 10: busca global + navegação de Configurações ----------
function initGlobalSearch() {
  const input = document.getElementById("gsInput");
  const menu = document.getElementById("gsMenu");
  if (!input) return;
  let timer, seq = 0;

  async function run() {
    const q = input.value.trim();
    if (q.length < 2) { menu.hidden = true; return; }
    const mine = ++seq;
    try {
      const r = await api(`/search?q=${encodeURIComponent(q)}&limit=5`);
      if (mine !== seq) return;           // ignora resposta antiga
      menu.innerHTML = r.groups.length ? r.groups.map((g) => `
        <div class="gs-group">${esc(g.label)}</div>
        ${g.items.map((i) => `<a class="gs-item" href="${esc(i.href)}"><strong>${esc(i.title)}</strong><span>${esc(i.subtitle || "")}</span></a>`).join("")}`).join("")
        : `<div class="gs-empty">Nada encontrado para “${esc(q)}”.</div>`;
      menu.hidden = false;
    } catch (e) { menu.innerHTML = `<div class="gs-empty">${esc(e.message)}</div>`; menu.hidden = false; }
  }
  input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(run, 250); });
  input.addEventListener("focus", () => { if (input.value.trim().length >= 2) run(); });
  document.addEventListener("click", (e) => { if (!document.getElementById("gsearch").contains(e.target)) menu.hidden = true; });
  document.addEventListener("keydown", (e) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName) || document.activeElement?.isContentEditable;
    if (e.key === "/" && !typing) { e.preventDefault(); input.focus(); }
    if (e.key === "Escape") { menu.hidden = true; if (document.activeElement === input) input.blur(); }
    if (e.key === "Enter" && document.activeElement === input) {
      const first = menu.querySelector(".gs-item"); if (first) location.href = first.getAttribute("href");
    }
  });
}

function settingsNav(active) {
  const tabs = [["settings.html", "Organização, usuários e permissões", "settings"], ["import.html", "Importar CSV", "import"], ["dedupe.html", "Duplicados", "dedupe"]];
  return `<nav class="subnav">${tabs.map(([h, l, k]) => `<a href="${h}" class="${k === active ? "active" : ""}">${l}</a>`).join("")}</nav>`;
}

// ---------- Etapa 11: rede de segurança ----------
// Se alguma chamada à API falhar sem que a página trate o erro, mostra um aviso em vez de ficar muda.
window.addEventListener("unhandledrejection", (e) => {
  const msg = e.reason && e.reason.message;
  if (msg && document.getElementById("toasts")) toast(msg, "err");
});