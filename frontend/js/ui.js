const STATUS_LABEL = {
  NOVO: "Novo", EM_CONTATO: "Em contato", QUALIFICADO: "Qualificado",
  OPORTUNIDADE: "Oportunidade", CONVERTIDO: "Convertido", PERDIDO: "Perdido", ARQUIVADO: "Arquivado",
};

const CHANNEL_LABEL = {
  EMAIL: "E-mail", WHATSAPP: "WhatsApp", SMS: "SMS", REDES_SOCIAIS: "Redes sociais",
  SITE: "Site", EVENTO: "Evento", OUTROS: "Outros",
};

// Quando uma etapa for implementada, basta trocar "stage" por "href" no item do menu.
const MENU = [
  { key: "dashboard", label: "Dashboard", href: "app.html" },
  { key: "leads", label: "Leads", href: "leads.html" },
  { key: "companies", label: "Empresas", stage: 3 },
  { key: "contacts", label: "Contatos", stage: 3 },
  { key: "pipeline", label: "Pipeline", stage: 4 },
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