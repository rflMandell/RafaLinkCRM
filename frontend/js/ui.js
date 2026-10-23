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
  { key: "activities", label: "Atividades", stage: 5 },
  { key: "campaigns", label: "Campanhas", stage: 6 },
  { key: "forecast", label: "Forecast", stage: 7 },
  { key: "settings", label: "Configurações", stage: 10 },
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
          <div>
            <span class="who">${esc(user.name)} · ${esc(user.role)}</span>
            <button id="logoutBtn">Sair</button>
          </div>
        </div>
        <div class="content" id="content"></div>
      </main>
    </div>
    <div id="toasts"></div>`;

  document.getElementById("logoutBtn").addEventListener("click", logout);
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