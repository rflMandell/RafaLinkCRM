// Peças compartilhadas de atividades: formulário, modal de detalhe, linhas de tarefa e timeline.

const ACTIVITY_TYPES = {
  LIGACAO: { label: "Ligação", icon: "📞" },
  EMAIL: { label: "E-mail", icon: "✉️" },
  WHATSAPP: { label: "WhatsApp", icon: "💬" },
  REUNIAO: { label: "Reunião", icon: "👥" },
  TAREFA: { label: "Tarefa", icon: "✅" },
  NOTA: { label: "Nota", icon: "📝" },
  FOLLOW_UP: { label: "Follow-up", icon: "🔁" },
};

const ACT_STATUS_LABEL = { PENDENTE: "Pendente", CONCLUIDA: "Concluída", CANCELADA: "Cancelada", ATRASADA: "Atrasada" };

function actStatusBadge(a) {
  const s = a.overdue ? "ATRASADA" : a.status;
  return `<span class="badge as-${esc(s)}">${esc(ACT_STATUS_LABEL[s] || s)}</span>`;
}

// ---------- Datas (sempre no horário local do navegador) ----------
function toLocalInput(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}
function dayKey(d) { return toLocalInput(d).slice(0, 10); }
function startOfDay(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }
function addDays(d, n) { return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n); }

function relatedText(a) {
  return [a.contactName, a.companyName, a.leadName && "Lead " + a.leadName, a.opportunityTitle]
    .filter(Boolean).join(" · ");
}

// ---------- Linha de tarefa (checkbox + título) ----------
function taskRowHtml(a, showOwner = false) {
  const meta = ACTIVITY_TYPES[a.type];
  const related = relatedText(a);
  return `
    <div class="task-row ${a.overdue ? "overdue" : ""}" data-id="${a.id}">
      <input type="checkbox" title="Concluir" ${a.status !== "PENDENTE" ? "checked disabled" : ""}>
      <div class="body">
        <div class="t">${meta.icon} ${esc(a.title)}</div>
        <div class="muted">${esc(meta.label)} · ${fmtDateTime(a.dueAt)}${related ? " · " + esc(related) : ""}${showOwner && a.ownerName ? " · " + esc(a.ownerName) : ""}</div>
      </div>
      ${a.overdue ? '<span class="badge as-ATRASADA">Atrasada</span>' : ""}
    </div>`;
}

function bindTaskRows(container, items, onChanged) {
  container.querySelectorAll(".task-row").forEach((row) => {
    const a = items.find((x) => x.id === Number(row.dataset.id));
    row.querySelector(".body").addEventListener("click", () => openActivityModal(a, onChanged));
    const box = row.querySelector("input[type=checkbox]");
    box.addEventListener("change", async () => {
      try {
        await api(`/activities/${a.id}/complete`, { method: "POST" });
        toast("Atividade concluída");
        onChanged();
      } catch (err) {
        box.checked = false;
        toast(err.message, "err");
      }
    });
  });
}

// ---------- Timeline ----------
function renderTimeline(items) {
  if (!items.length) return `<div class="empty">Nenhuma interação registrada ainda.</div>`;
  return `<ul class="timeline">${items.map((it, i) => {
    const meta = ACTIVITY_TYPES[it.type];
    return `
      <li ${it.activity ? `class="clickable-li" data-idx="${i}"` : ""}>
        <strong>${meta ? meta.icon : "●"} ${esc(it.title)}</strong>
        <span class="muted">· ${fmtDateTime(it.at)}${it.userName ? " · " + esc(it.userName) : ""}</span>
        ${it.description ? `<div class="muted">${esc(it.description)}</div>` : ""}
      </li>`;
  }).join("")}</ul>`;
}

function bindTimeline(container, items, onChanged) {
  container.querySelectorAll("li[data-idx]").forEach((li) =>
    li.addEventListener("click", () => openActivityModal(items[Number(li.dataset.idx)].activity, onChanged))
  );
}

// ---------- Modal de detalhe ----------
function openActivityModal(a, onChanged) {
  const meta = ACTIVITY_TYPES[a.type];
  const me = getUser();
  const pending = a.status === "PENDENTE";
  const canDel = canDelete() || a.ownerId === me.id || a.createdBy === me.id;
  const link = (label, href, text) =>
    text ? `<div><span class="muted">${label}:</span> <a class="link" href="${href}">${esc(text)}</a></div>` : "";

  const dlg = document.createElement("dialog");
  dlg.className = "modal";
  dlg.innerHTML = `
    <h2>${meta.icon} ${esc(a.title)}</h2>
    <div class="stepper">
      ${actStatusBadge(a)}
      <span class="muted">${esc(meta.label)} · ${fmtDateTime(a.status === "CONCLUIDA" ? a.completedAt : a.dueAt)}</span>
    </div>
    ${a.description ? `<p style="margin:10px 0">${esc(a.description)}</p>` : ""}
    ${link("Lead", "lead.html?id=" + a.leadId, a.leadName)}
    ${link("Contato", "contact.html?id=" + a.contactId, a.contactName)}
    ${link("Empresa", "company.html?id=" + a.companyId, a.companyName)}
    ${link("Oportunidade", "opportunity.html?id=" + a.opportunityId, a.opportunityTitle)}
    <div class="muted" style="margin-top:8px">Responsável: ${esc(a.ownerName || "—")}</div>
    <div class="modal-actions" style="flex-wrap:wrap">
      ${canDel ? '<button class="btn btn-danger" id="delBtn">Excluir</button>' : ""}
      <button class="btn" id="closeBtn">Fechar</button>
      ${pending ? '<button class="btn" id="cancelActBtn">Cancelar atividade</button><button class="btn" id="editBtn">Editar</button><button class="btn btn-primary" id="doneBtn">Concluir</button>' : ""}
    </div>`;
  document.body.appendChild(dlg);
  dlg.showModal();
  dlg.addEventListener("close", () => dlg.remove());
  dlg.querySelector("#closeBtn").addEventListener("click", () => dlg.close());

  const run = async (path, options, message) => {
    try {
      await api(path, options);
      dlg.close();
      toast(message);
      if (onChanged) onChanged();
    } catch (err) {
      toast(err.message, "err");
    }
  };

  const done = dlg.querySelector("#doneBtn");
  if (done) done.addEventListener("click", () => run(`/activities/${a.id}/complete`, { method: "POST" }, "Atividade concluída"));

  const cancel = dlg.querySelector("#cancelActBtn");
  if (cancel) cancel.addEventListener("click", () => run(`/activities/${a.id}/cancel`, { method: "POST" }, "Atividade cancelada"));

  const del = dlg.querySelector("#delBtn");
  if (del) del.addEventListener("click", () => {
    if (confirm(`Excluir a atividade "${a.title}"?`)) run(`/activities/${a.id}`, { method: "DELETE" }, "Atividade excluída");
  });

  const edit = dlg.querySelector("#editBtn");
  if (edit) edit.addEventListener("click", async () => {
    dlg.close();
    const options = await api("/activities/options");
    openActivityForm({ activity: a, options, onSaved: onChanged });
  });
}

// ---------- Formulário ----------
// options vem de GET /activities/options. defaults: { type, dueAt (Date), leadId, contactId, companyId, opportunityId }
function openActivityForm({ activity = null, options, defaults = {}, onSaved }) {
  const me = getUser();
  const a = activity;
  const type0 = a ? a.type : (defaults.type || "TAREFA");
  const owner0 = a ? a.ownerId : me.id;

  let due0;
  if (a) {
    due0 = toLocalInput(new Date(a.dueAt));
  } else if (defaults.dueAt) {
    due0 = toLocalInput(defaults.dueAt);
  } else {
    const d = new Date();
    d.setMinutes(0, 0, 0);
    d.setHours(d.getHours() + 1);
    due0 = toLocalInput(d);
  }

  const opts = (items, selected, label) =>
    items.map((i) => `<option value="${i.id}" ${i.id === selected ? "selected" : ""}>${esc(label(i))}</option>`).join("");
  const typeOpts = Object.entries(ACTIVITY_TYPES)
    .map(([k, v]) => `<option value="${k}" ${k === type0 ? "selected" : ""}>${v.icon} ${v.label}</option>`)
    .join("");

  const dlg = document.createElement("dialog");
  dlg.className = "modal";
  dlg.innerHTML = `
    <form id="actForm">
      <h2>${a ? "Editar atividade" : "Nova atividade"}</h2>
      <div class="form-grid">
        <div><label>Tipo</label><select name="type" ${a ? "disabled" : ""}>${typeOpts}</select></div>
        <div><label id="dueLabel">Quando *</label><input name="dueAt" type="datetime-local" value="${due0}"></div>
        <div class="full"><label>Título *</label><input name="title" value="${esc(a?.title ?? "")}" required maxlength="160"></div>
        <div class="full"><label>Descrição</label><textarea name="description" rows="3" maxlength="1000">${esc(a?.description ?? "")}</textarea></div>
        ${a ? "" : `<div class="full"><label class="check" id="doneWrap"><input type="checkbox" name="completed"> Já realizada (registrar no histórico)</label></div>`}
        <div class="full"><label>Responsável</label><select name="ownerId">${opts(options.owners, owner0, (o) => o.name)}</select></div>
        ${a ? "" : `
        <div><label>Lead</label><select name="leadId"><option value="">—</option>${opts(options.leads, defaults.leadId ?? null, (l) => l.name)}</select></div>
        <div><label>Contato</label><select name="contactId"><option value="">—</option>${opts(options.contacts, defaults.contactId ?? null, (c) => c.name)}</select></div>
        <div><label>Empresa</label><select name="companyId"><option value="">—</option>${opts(options.companies, defaults.companyId ?? null, (c) => c.name)}</select></div>
        <div><label>Oportunidade</label><select name="opportunityId"><option value="">—</option>${opts(options.opportunities, defaults.opportunityId ?? null, (o) => o.title)}</select></div>`}
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

  // Nota é sempre "realizada"; atividade realizada pergunta "quando ocorreu"
  function syncType() {
    const isNote = f("type").value === "NOTA";
    const wrap = dlg.querySelector("#doneWrap");
    if (wrap) wrap.style.display = isNote ? "none" : "flex";
    const done = f("completed") ? f("completed").checked : false;
    f("dueAt").required = !isNote && !done;
    dlg.querySelector("#dueLabel").textContent = isNote || done ? "Quando ocorreu" : "Quando *";
  }
  if (!a) {
    f("type").addEventListener("change", syncType);
    f("completed").addEventListener("change", syncType);

    // Escolheu um contato sem empresa: preenche a empresa dele
    f("contactId").addEventListener("change", () => {
      const c = options.contacts.find((x) => x.id === Number(f("contactId").value));
      if (c && c.companyId && !f("companyId").value) f("companyId").value = String(c.companyId);
    });
  }
  syncType();

  dlg.querySelector("#actForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const text = (k) => (fd.get(k) || "").toString().trim() || null;
    const num = (k) => (fd.get(k) ? Number(fd.get(k)) : null);
    const body = {
      title: (fd.get("title") || "").toString().trim(),
      description: text("description"),
      dueAt: fd.get("dueAt") ? new Date(fd.get("dueAt")).toISOString() : null,
      ownerId: num("ownerId"),
    };
    if (!a) {
      body.type = fd.get("type");
      body.completed = fd.get("completed") === "on";
      body.leadId = num("leadId");
      body.contactId = num("contactId");
      body.companyId = num("companyId");
      body.opportunityId = num("opportunityId");
    }
    try {
      const saved = a
        ? await api(`/activities/${a.id}`, { method: "PATCH", body })
        : await api("/activities", { method: "POST", body });
      dlg.close();
      toast(a ? "Atividade atualizada" : "Atividade criada");
      if (onSaved) onSaved(saved);
    } catch (err) {
      dlg.querySelector("#formError").textContent = err.message;
    }
  });
}