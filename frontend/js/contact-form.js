// Abre o formulário de criar (contact = null) ou editar um contato.
// defaults.companyId pré-seleciona a empresa (usado na tela da empresa).
function openContactForm({ contact = null, owners = [], companies = [], defaults = {}, onSaved }) {
  const me = getUser();
  const val = (k) => esc(contact?.[k] ?? "");
  const ownerSelected = contact ? contact.ownerId : me.id;
  const companySelected = contact ? contact.companyId : (defaults.companyId ?? null);

  const companyOpts = companies
    .map((c) => `<option value="${c.id}" ${c.id === companySelected ? "selected" : ""}>${esc(c.name)}</option>`)
    .join("");
  const ownerOpts = owners
    .map((o) => `<option value="${o.id}" ${o.id === ownerSelected ? "selected" : ""}>${esc(o.name)}</option>`)
    .join("");
  const prefOpts = Object.entries(PREFERENCE_LABEL)
    .map(([k, l]) => `<option value="${k}" ${contact?.contactPreference === k ? "selected" : ""}>${l}</option>`)
    .join("");
  const statusOpts = Object.entries(CONTACT_STATUS_LABEL)
    .map(([k, l]) => `<option value="${k}" ${(contact?.status || "ATIVO") === k ? "selected" : ""}>${l}</option>`)
    .join("");

  const dlg = document.createElement("dialog");
  dlg.className = "modal";
  dlg.innerHTML = `
    <form id="contactForm">
      <h2>${contact ? "Editar contato" : "Novo contato"}</h2>
      <div class="form-grid">
        <div class="full"><label>Nome *</label><input name="name" value="${val("name")}" required maxlength="120"></div>
        <div><label>Cargo</label><input name="jobTitle" value="${val("jobTitle")}"></div>
        <div><label>Empresa</label><select name="companyId"><option value="">Sem empresa</option>${companyOpts}</select></div>
        <div><label>E-mail</label><input name="email" type="email" value="${val("email")}"></div>
        <div><label>Telefone</label><input name="phone" value="${val("phone")}"></div>
        <div><label>Preferência de contato</label><select name="contactPreference"><option value="">—</option>${prefOpts}</select></div>
        <div><label>Status</label><select name="status">${statusOpts}</select></div>
        <div class="full"><label>Responsável</label><select name="ownerId">${contact ? '<option value="">Sem responsável</option>' : ""}${ownerOpts}</select></div>
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

  dlg.querySelector("#contactForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const text = (k) => (fd.get(k) || "").toString().trim() || null;
    const body = {
      name: (fd.get("name") || "").toString().trim(),
      jobTitle: text("jobTitle"),
      companyId: fd.get("companyId") ? Number(fd.get("companyId")) : null,
      email: text("email"),
      phone: text("phone"),
      contactPreference: text("contactPreference"),
      status: fd.get("status"),
      ownerId: fd.get("ownerId") ? Number(fd.get("ownerId")) : null,
    };
    try {
      const saved = contact
        ? await api(`/contacts/${contact.id}`, { method: "PATCH", body })
        : await api("/contacts", { method: "POST", body });
      dlg.close();
      toast(contact ? "Contato atualizado" : "Contato criado");
      if (onSaved) onSaved(saved);
    } catch (err) {
      dlg.querySelector("#formError").textContent = err.message;
    }
  });
}