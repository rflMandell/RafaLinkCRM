// Abre o formulário de criar (lead = null) ou editar (lead = objeto) um lead.
function openLeadForm({ lead = null, owners = [], onSaved }) {
  const me = getUser();
  const val = (k) => esc(lead?.[k] ?? "");
  const ownerSelected = lead ? lead.ownerId : me.id;

  const channelOpts = Object.entries(CHANNEL_LABEL)
    .map(([k, l]) => `<option value="${k}" ${lead?.channel === k ? "selected" : ""}>${l}</option>`)
    .join("");
  const ownerOpts = owners
    .map((o) => `<option value="${o.id}" ${o.id === ownerSelected ? "selected" : ""}>${esc(o.name)}</option>`)
    .join("");

  const dlg = document.createElement("dialog");
  dlg.className = "modal";
  dlg.innerHTML = `
    <form id="leadForm">
      <h2>${lead ? "Editar lead" : "Novo lead"}</h2>
      <div class="form-grid">
        <div class="full"><label>Nome *</label><input name="name" value="${val("name")}" required maxlength="120"></div>
        <div><label>E-mail</label><input name="email" type="email" value="${val("email")}"></div>
        <div><label>Telefone</label><input name="phone" value="${val("phone")}"></div>
        <div><label>Empresa</label><input name="company" value="${val("company")}"></div>
        <div>
          <label>Origem</label>
          <input name="source" list="sources" value="${val("source")}">
          <datalist id="sources">
            <option>Indicação</option><option>Site</option><option>LinkedIn</option>
            <option>Evento</option><option>Anúncio</option>
          </datalist>
        </div>
        <div><label>Canal</label><select name="channel"><option value="">—</option>${channelOpts}</select></div>
        <div>
          <label>Responsável</label>
          <select name="ownerId">${lead ? '<option value="">Sem responsável</option>' : ""}${ownerOpts}</select>
        </div>
        <div><label>Score (0-100)</label><input name="score" type="number" min="0" max="100" value="${lead ? lead.score : 0}"></div>
        <div class="full"><label>Próxima ação</label><input name="nextAction" value="${val("nextAction")}"></div>
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

  dlg.querySelector("#leadForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const text = (k) => (fd.get(k) || "").toString().trim() || null;
    const body = {
      name: (fd.get("name") || "").toString().trim(),
      email: text("email"),
      phone: text("phone"),
      company: text("company"),
      source: text("source"),
      channel: text("channel"),
      ownerId: fd.get("ownerId") ? Number(fd.get("ownerId")) : null,
      score: Number(fd.get("score") || 0),
      nextAction: text("nextAction"),
    };
    try {
      const saved = lead
        ? await api(`/leads/${lead.id}`, { method: "PATCH", body })
        : await api("/leads", { method: "POST", body });
      dlg.close();
      toast(lead ? "Lead atualizado" : "Lead criado");
      if (onSaved) onSaved(saved);
    } catch (err) {
      dlg.querySelector("#formError").textContent = err.message;
    }
  });
}