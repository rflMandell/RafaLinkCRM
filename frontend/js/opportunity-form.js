// Abre o formulário de criar (opportunity = null) ou editar uma oportunidade.
// options vem de GET /opportunities/options. defaults pré-seleciona pipeline/empresa.
function openOpportunityForm({ opportunity = null, options, defaults = {}, onSaved }) {
  if (!opportunity && options.pipelines.length === 0) {
    toast("Nenhum pipeline configurado", "err");
    return;
  }
  const me = getUser();
  const o = opportunity;
  const val = (k) => esc(o?.[k] ?? "");

  const pipelineId = o
    ? o.pipelineId
    : (defaults.pipelineId ?? (options.pipelines.find((p) => p.isDefault) || options.pipelines[0]).id);
  const ownerSelected = o ? o.ownerId : me.id;
  const companySelected = o ? o.companyId : (defaults.companyId ?? null);
  const contactSelected = o ? o.contactId : (defaults.contactId ?? null);

  const pipelineOpts = options.pipelines
    .map((p) => `<option value="${p.id}" ${p.id === pipelineId ? "selected" : ""}>${esc(p.name)}</option>`)
    .join("");
  const companyOpts = options.companies
    .map((c) => `<option value="${c.id}" ${c.id === companySelected ? "selected" : ""}>${esc(c.name)}</option>`)
    .join("");
  const ownerOpts = options.owners
    .map((u) => `<option value="${u.id}" ${u.id === ownerSelected ? "selected" : ""}>${esc(u.name)}</option>`)
    .join("");

  const dlg = document.createElement("dialog");
  dlg.className = "modal";
  dlg.innerHTML = `
    <form id="oppForm">
      <h2>${o ? "Editar oportunidade" : "Nova oportunidade"}</h2>
      <div class="form-grid">
        <div class="full"><label>Título *</label><input name="title" value="${val("title")}" required maxlength="160"></div>
        <div><label>Valor (R$)</label><input name="value" type="number" min="0" step="0.01" value="${o ? o.value : 0}"></div>
        <div><label>Fechamento previsto</label><input name="expectedCloseDate" type="date" value="${val("expectedCloseDate")}"></div>
        ${o ? "" : `
        <div><label>Pipeline</label><select name="pipelineId">${pipelineOpts}</select></div>
        <div><label>Etapa inicial</label><select name="stageId"></select></div>`}
        <div><label>Empresa</label><select name="companyId"><option value="">Sem empresa</option>${companyOpts}</select></div>
        <div><label>Contato</label><select name="contactId"></select></div>
        <div class="full"><label>Responsável</label><select name="ownerId">${o ? '<option value="">Sem responsável</option>' : ""}${ownerOpts}</select></div>
        <div class="full"><label>Observações</label><textarea name="notes" rows="3" maxlength="1000">${val("notes")}</textarea></div>
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

  const f = (name) => dlg.querySelector(`[name="${name}"]`);

  // Etapa depende do pipeline escolhido
  function fillStages() {
    const sel = f("stageId");
    if (!sel) return;
    const p = options.pipelines.find((x) => x.id === Number(f("pipelineId").value));
    sel.innerHTML = (p ? p.stages : [])
      .filter((s) => s.kind === "OPEN")
      .map((s) => `<option value="${s.id}" ${s.id === defaults.stageId ? "selected" : ""}>${esc(s.name)} (${s.probability}%)</option>`)
      .join("");
  }

  // Contato depende da empresa escolhida (mostra os dela + os sem empresa)
  function fillContacts() {
    const sel = f("contactId");
    const current = sel.value;
    const companyId = Number(f("companyId").value) || null;
    const list = options.contacts.filter((c) => !companyId || c.companyId === companyId || c.companyId === null);
    sel.innerHTML = `<option value="">Sem contato</option>` +
      list.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
    if ([...sel.options].some((op) => op.value === current)) sel.value = current;
  }

  if (f("pipelineId")) f("pipelineId").addEventListener("change", fillStages);
  f("companyId").addEventListener("change", fillContacts);
  f("contactId").addEventListener("change", () => {
    // Escolheu um contato sem ter escolhido empresa: preenche a empresa dele
    const c = options.contacts.find((x) => x.id === Number(f("contactId").value));
    if (c && c.companyId && !f("companyId").value) {
      f("companyId").value = String(c.companyId);
      fillContacts();
    }
  });

  fillStages();
  fillContacts();
  f("contactId").value = contactSelected ? String(contactSelected) : "";

  dlg.querySelector("#oppForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const text = (k) => (fd.get(k) || "").toString().trim() || null;
    const num = (k) => (fd.get(k) ? Number(fd.get(k)) : null);
    const body = {
      title: (fd.get("title") || "").toString().trim(),
      value: Number(fd.get("value") || 0),
      companyId: num("companyId"),
      contactId: num("contactId"),
      ownerId: num("ownerId"),
      expectedCloseDate: text("expectedCloseDate"),
      notes: text("notes"),
    };
    if (!o) {
      body.pipelineId = num("pipelineId");
      body.stageId = num("stageId");
    }
    try {
      const saved = o
        ? await api(`/opportunities/${o.id}`, { method: "PATCH", body })
        : await api("/opportunities", { method: "POST", body });
      dlg.close();
      toast(o ? "Oportunidade atualizada" : "Oportunidade criada");
      if (onSaved) onSaved(saved);
    } catch (err) {
      dlg.querySelector("#formError").textContent = err.message;
    }
  });
}

// Move uma oportunidade para outra etapa. Pede o motivo (Perdido) ou o valor realizado (Ganho).
// Devolve a oportunidade atualizada, ou null se o usuário cancelou / deu erro.
async function moveOpportunity(opp, stage) {
  const body = { stageId: stage.id };

  if (stage.kind === "LOST") {
    const reason = prompt("Motivo da perda (opcional):");
    if (reason === null) return null;
    body.reason = reason.trim() || null;
  } else if (stage.kind === "WON") {
    const answer = prompt("Valor realizado da venda em R$ (somente números, ex.: 80000 ou 80000,50):", String(opp.value));
    if (answer === null) return null;
    const n = Number(answer.replace(",", "."));
    if (!Number.isFinite(n) || n < 0) {
      toast("Valor inválido", "err");
      return null;
    }
    body.realizedValue = n;
  }

  try {
    const updated = await api(`/opportunities/${opp.id}/move`, { method: "POST", body });
    toast(stage.kind === "WON" ? "Venda registrada!" : `Movida para ${stage.name}`);
    return updated;
  } catch (err) {
    toast(err.message, "err");
    return null;
  }
}