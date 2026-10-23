const CAMPAIGN_STATUS_LABEL = { RASCUNHO: "Rascunho", ATIVA: "Ativa", PAUSADA: "Pausada", ENCERRADA: "Encerrada" };
const CAMPAIGN_ACTION = {
  ATIVA: { label: "Ativar", cls: "btn-primary" },
  PAUSADA: { label: "Pausar", cls: "" },
  ENCERRADA: { label: "Encerrar", cls: "btn-danger" },
};

function campaignBadge(status) {
  return `<span class="badge cs-${esc(status)}">${esc(CAMPAIGN_STATUS_LABEL[status] || status)}</span>`;
}

// ROI com sinal e seta (não depende só da cor). null = sem investimento informado.
function roiHtml(roi) {
  if (roi === null || roi === undefined) return `<span class="muted">—</span>`;
  const cls = roi >= 0 ? "roi-pos" : "roi-neg";
  return `<span class="${cls}">${roi >= 0 ? "▲" : "▼"} ${NF_1.format(roi)}%</span>`;
}

// Abre o formulário de criar (campaign = null) ou editar uma campanha.
function openCampaignForm({ campaign = null, owners = [], onSaved }) {
  const me = getUser();
  const val = (k) => esc(campaign?.[k] ?? "");
  const ownerSelected = campaign ? campaign.ownerId : me.id;
  const channelOpts = Object.entries(CHANNEL_LABEL)
    .map(([k, l]) => `<option value="${k}" ${campaign?.channel === k ? "selected" : ""}>${l}</option>`).join("");
  const ownerOpts = owners
    .map((o) => `<option value="${o.id}" ${o.id === ownerSelected ? "selected" : ""}>${esc(o.name)}</option>`).join("");

  const dlg = document.createElement("dialog");
  dlg.className = "modal";
  dlg.innerHTML = `
    <form id="campForm">
      <h2>${campaign ? "Editar campanha" : "Nova campanha"}</h2>
      <div class="form-grid">
        <div class="full"><label>Nome *</label><input name="name" value="${val("name")}" required maxlength="120"></div>
        <div><label>Canal</label><select name="channel"><option value="">—</option>${channelOpts}</select></div>
        <div><label>Responsável</label><select name="ownerId">${ownerOpts}</select></div>
        <div><label>Orçamento (R$)</label><input name="budget" type="number" min="0" step="0.01" value="${campaign ? campaign.budget : 0}"></div>
        <div><label>Investido até agora (R$)</label><input name="cost" type="number" min="0" step="0.01" value="${campaign ? campaign.cost : 0}"></div>
        <div><label>Início</label><input name="startDate" type="date" value="${val("startDate")}"></div>
        <div><label>Fim</label><input name="endDate" type="date" value="${val("endDate")}"></div>
        <div class="full"><label>Descrição</label><input name="description" value="${val("description")}" maxlength="1000"></div>
      </div>
      <div class="error" id="formError"></div>
      <div class="modal-actions">
        <button type="button" class="btn" id="cancelBtn">Cancelar</button>
        <button type="submit" class="btn btn-primary">Salvar</button>
      </div>
    </form>`;
  document.body.appendChild(dlg);
  dlg.showModal();
  dlg.addEventListener("close", () => dlg.remove());
  dlg.querySelector("#cancelBtn").addEventListener("click", () => dlg.close());

  dlg.querySelector("#campForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const text = (k) => (fd.get(k) || "").toString().trim() || null;
    const body = {
      name: (fd.get("name") || "").toString().trim(),
      channel: text("channel"),
      ownerId: fd.get("ownerId") ? Number(fd.get("ownerId")) : null,
      budget: Number(fd.get("budget") || 0),
      cost: Number(fd.get("cost") || 0),
      startDate: text("startDate"),
      endDate: text("endDate"),
      description: text("description"),
    };
    try {
      const saved = campaign
        ? await api(`/campaigns/${campaign.id}`, { method: "PATCH", body })
        : await api("/campaigns", { method: "POST", body });
      dlg.close();
      toast(campaign ? "Campanha atualizada" : "Campanha criada");
      if (onSaved) onSaved(saved);
    } catch (err) {
      dlg.querySelector("#formError").textContent = err.message;
    }
  });
}