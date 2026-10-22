// Abre o formulário de criar (company = null) ou editar uma empresa.
function openCompanyForm({ company = null, owners = [], onSaved }) {
  const me = getUser();
  const val = (k) => esc(company?.[k] ?? "");
  const ownerSelected = company ? company.ownerId : me.id;

  const typeOpts = Object.entries(TYPE_LABEL)
    .map(([k, l]) => `<option value="${k}" ${(company?.type || "PROSPECT") === k ? "selected" : ""}>${l}</option>`)
    .join("");
  const ownerOpts = owners
    .map((o) => `<option value="${o.id}" ${o.id === ownerSelected ? "selected" : ""}>${esc(o.name)}</option>`)
    .join("");

  const dlg = document.createElement("dialog");
  dlg.className = "modal";
  dlg.innerHTML = `
    <form id="companyForm">
      <h2>${company ? "Editar empresa" : "Nova empresa"}</h2>
      <div class="form-grid">
        <div class="full"><label>Nome *</label><input name="name" value="${val("name")}" required maxlength="120"></div>
        <div>
          <label>Segmento</label>
          <input name="industry" list="industries" value="${val("industry")}">
          <datalist id="industries">
            <option>Tecnologia</option><option>Varejo</option><option>Saúde</option>
            <option>Educação</option><option>Construção</option><option>Serviços</option>
          </datalist>
        </div>
        <div><label>Cidade</label><input name="city" value="${val("city")}"></div>
        <div><label>Site</label><input name="website" value="${val("website")}"></div>
        <div><label>Telefone</label><input name="phone" value="${val("phone")}"></div>
        <div><label>Tipo</label><select name="type">${typeOpts}</select></div>
        <div><label>Responsável</label><select name="ownerId">${company ? '<option value="">Sem responsável</option>' : ""}${ownerOpts}</select></div>
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

  dlg.querySelector("#companyForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const text = (k) => (fd.get(k) || "").toString().trim() || null;
    const body = {
      name: (fd.get("name") || "").toString().trim(),
      industry: text("industry"),
      city: text("city"),
      website: text("website"),
      phone: text("phone"),
      type: fd.get("type"),
      ownerId: fd.get("ownerId") ? Number(fd.get("ownerId")) : null,
      notes: text("notes"),
    };
    try {
      const saved = company
        ? await api(`/companies/${company.id}`, { method: "PATCH", body })
        : await api("/companies", { method: "POST", body });
      dlg.close();
      toast(company ? "Empresa atualizada" : "Empresa criada");
      if (onSaved) onSaved(saved);
    } catch (err) {
      dlg.querySelector("#formError").textContent = err.message;
    }
  });
}