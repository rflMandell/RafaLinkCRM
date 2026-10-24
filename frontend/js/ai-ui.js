// Peças compartilhadas da IA simulada (Etapa 8): usadas em ai.html e nos cards de lead/empresa/oportunidade.
// Depende de api.js e ui.js (api, esc, toast, statusBadge). Não depende de charts.js.
const AI_NF = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });

const PRIORITY_UI = {
  1: ["▲ Alta", "pri-high"],
  2: ["● Média", "pri-mid"],
  3: ["▽ Baixa", "pri-low"],
};
const LEVEL_UI = {            // temperatura do lead
  QUENTE: ["▲ Quente", "lv-hot"],
  MORNO: ["● Morno", "lv-warm"],
  FRIO: ["▽ Frio", "lv-cold"],
};
const CHURN_UI = {            // risco de perda do cliente
  ALTO: ["▲ Alto", "lv-hot"],
  MEDIO: ["● Médio", "lv-warm"],
  BAIXO: ["▽ Baixo", "lv-cold"],
};
const ENTITY_UI = {
  lead: ["Lead", (id) => `lead.html?id=${id}`],
  company: ["Cliente", (id) => `company.html?id=${id}`],
  opportunity: ["Oportunidade", (id) => `opportunity.html?id=${id}`],
};

function aiPill(map, key) {
  const [text, cls] = map[key] || [key, ""];
  return `<span class="ai-pill ${cls}">${esc(text)}</span>`;
}

function priorityPill(p) { return aiPill(PRIORITY_UI, p); }

// medidor 0-100
function aiMeter(value, cls) {
  return `<div class="ai-meter" role="img" aria-label="${value} de 100">
    <span class="${cls}" style="width:${Math.max(2, value)}%"></span></div>`;
}

function aiLink(entity, id, name) {
  const [, href] = ENTITY_UI[entity];
  return `<a href="${href(id)}">${esc(name)}</a>`;
}

// tabela "por que essa nota?" — cada fator com sinal explícito (+/−), nunca só cor
// risk=true: no churn, pontos positivos são ruins (vermelho) e negativos são bons (verde)
function factorsTable(factors, risk = false) {
  if (!factors || !factors.length) return `<p class="muted">Nenhum fator pontuou.</p>`;
  const max = Math.max(...factors.map((f) => Math.abs(f.points)), 1);
  return `<table class="grid ai-factors"><tbody>${factors.map((f) => `
    <tr>
      <td>${esc(f.label)}<div class="muted">${esc(f.detail || "")}</div></td>
      <td class="ai-fbar"><span class="${(f.points < 0) !== risk ? "neg" : "pos"}" style="width:${Math.round(Math.abs(f.points) / max * 100)}%"></span></td>
      <td class="num ${(f.points < 0) !== risk ? "bad" : "ok"}">${f.points > 0 ? "+" : "−"}${AI_NF.format(Math.abs(f.points))}</td>
    </tr>`).join("")}</tbody></table>`;
}

function actionsList(actions) {
  return `<ul class="ai-actions">${actions.map((a, i) => `
    <li class="${i === 0 ? "primary" : ""}">
      <div>${priorityPill(a.priority)} <strong>${esc(a.title)}</strong></div>
      <div class="muted">${esc(a.reason)}</div>
    </li>`).join("")}</ul>`;
}

// ---------- Cards nas páginas de detalhe ----------
async function loadLeadAI(leadId, box) {
  try {
    const d = await api(`/ai/leads/${leadId}`);
    if (!d.scored) { box.innerHTML = `<div class="card-block"><h3>IA do lead</h3><p class="muted">${esc(d.message)}</p></div>`; return; }
    const stale = d.storedScore !== d.score;
    box.innerHTML = `
      <div class="card-block">
        <div class="page-head" style="margin-bottom:8px"><h3 style="margin:0">IA do lead</h3>
          <button class="btn" id="aiRescore" ${stale ? "" : "hidden"}>Aplicar nota ${d.score}</button></div>
        <div class="ai-score"><span class="ai-big">${d.score}</span><span class="muted">/ 100</span> ${aiPill(LEVEL_UI, d.level)}</div>
        ${aiMeter(d.score, LEVEL_UI[d.level][1])}
        ${stale ? `<p class="note">A nota gravada no lead é ${d.storedScore}; a nota calculada agora é ${d.score}.</p>` : ""}
        <h4 class="ai-sub">Próxima melhor ação</h4>${actionsList(d.actions)}
        <h4 class="ai-sub">Por que essa nota?</h4>${factorsTable(d.factors)}
      </div>`;
    const btn = box.querySelector("#aiRescore");
    btn.addEventListener("click", async () => {
      try { await api(`/ai/leads/${leadId}/rescore`, { method: "POST" }); toast("Nota atualizada."); loadLeadAI(leadId, box); }
      catch (e) { toast(e.message, "err"); }
    });
  } catch (e) { box.innerHTML = ""; }
}

async function loadCompanyAI(companyId, box) {
  try {
    const d = await api(`/ai/companies/${companyId}`);
    if (!d.applicable) { box.innerHTML = `<div class="card-block"><h3>IA do cliente</h3><p class="muted">${esc(d.message)}</p></div>`; return; }
    box.innerHTML = `
      <div class="card-block"><h3>IA do cliente</h3>
        <div class="ai-score"><span class="ai-big">${d.risk}</span><span class="muted">/ 100 de risco de perda</span> ${aiPill(CHURN_UI, d.level)}</div>
        ${aiMeter(d.risk, CHURN_UI[d.level][1])}
        <h4 class="ai-sub">Próxima melhor ação</h4>${actionsList(d.actions)}
        <h4 class="ai-sub">Sinais de risco</h4>${factorsTable(d.factors, true)}
      </div>`;
  } catch (e) { box.innerHTML = ""; }
}

async function loadOppAI(oppId, box) {
  try {
    const d = await api(`/ai/opportunities/${oppId}`);
    if (!d.applicable) { box.innerHTML = ""; return; }
    box.innerHTML = `<div class="card-block"><h3>Próxima melhor ação</h3>${actionsList(d.actions)}</div>`;
  } catch (e) { box.innerHTML = ""; }
}