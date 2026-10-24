import csv
import io
import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..database import get_db, now_iso
from ..dedupe_rules import norm_company, norm_domain, norm_email, norm_phone, norm_text
from ..errors import AppError
from ..events import publish
from ..permissions import require_perm
from ..scoring import rescore_lead

router = APIRouter(prefix="/import", tags=["Importação CSV"])

MAX_ROWS = 2000
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# entidade -> [(campo, rótulo, obrigatório, tamanho máximo)]
FIELDS = {
    "leads": [("name", "Nome", True, 120), ("email", "E-mail", False, 160), ("phone", "Telefone", False, 30),
              ("company", "Empresa", False, 120), ("source", "Origem", False, 80), ("channel", "Canal", False, 20),
              ("owner", "Responsável (e-mail ou nome)", False, 160)],
    "companies": [("name", "Nome", True, 120), ("industry", "Setor", False, 80), ("website", "Site", False, 160),
                  ("phone", "Telefone", False, 30), ("city", "Cidade", False, 80), ("type", "Tipo (Prospect ou Cliente)", False, 20),
                  ("notes", "Observações", False, 1000), ("owner", "Responsável (e-mail ou nome)", False, 160)],
    "contacts": [("name", "Nome", True, 120), ("job_title", "Cargo", False, 80), ("email", "E-mail", False, 160),
                 ("phone", "Telefone", False, 30), ("company", "Empresa (pelo nome)", False, 120),
                 ("owner", "Responsável (e-mail ou nome)", False, 160)],
}
# cabeçalhos aceitos (já normalizados: minúsculas, sem acento) -> campo
ALIASES = {
    "leads": {"name": ["nome", "name", "nome completo", "lead", "contato"], "email": ["email", "e mail", "mail"],
              "phone": ["telefone", "phone", "celular", "whatsapp", "fone", "tel"], "company": ["empresa", "company", "organizacao"],
              "source": ["origem", "source", "fonte"], "channel": ["canal", "channel"],
              "owner": ["responsavel", "owner", "vendedor", "dono"]},
    "companies": {"name": ["nome", "empresa", "razao social", "nome fantasia", "company", "name"],
                  "industry": ["setor", "segmento", "ramo", "industry"], "website": ["site", "website", "url", "pagina"],
                  "phone": ["telefone", "phone", "fone", "tel"], "city": ["cidade", "city"], "type": ["tipo", "type"],
                  "notes": ["observacoes", "obs", "notas", "notes"], "owner": ["responsavel", "owner", "vendedor", "dono"]},
    "contacts": {"name": ["nome", "name", "nome completo", "contato"], "job_title": ["cargo", "funcao", "job title", "position"],
                 "email": ["email", "e mail", "mail"], "phone": ["telefone", "phone", "celular", "whatsapp", "fone", "tel"],
                 "company": ["empresa", "company", "organizacao"], "owner": ["responsavel", "owner", "vendedor", "dono"]},
}
CHANNELS = {"email": "EMAIL", "e mail": "EMAIL", "whatsapp": "WHATSAPP", "sms": "SMS", "redes sociais": "REDES_SOCIAIS",
            "rede social": "REDES_SOCIAIS", "instagram": "REDES_SOCIAIS", "linkedin": "REDES_SOCIAIS", "facebook": "REDES_SOCIAIS",
            "site": "SITE", "evento": "EVENTO", "outros": "OUTROS", "outro": "OUTROS", "indicacao": "OUTROS"}
REASON = {"e": "mesmo e-mail", "p": "mesmo telefone", "n": "mesmo nome", "d": "mesmo site"}


# ---------- Leitura do CSV ----------
def parse_csv(text: str):
    text = text.lstrip("\ufeff")
    first = next((ln for ln in text.splitlines() if ln.strip()), "")
    if not first:
        raise AppError(400, "EMPTY_CSV", "O arquivo está vazio.")
    delimiter = max([";", ",", "\t"], key=lambda d: first.count(d))
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=delimiter) if any(c.strip() for c in r)]
    header, body = rows[0], rows[1:]
    seen, columns = {}, []
    for h in header:
        h = h.strip() or "(sem nome)"
        seen[h] = seen.get(h, 0) + 1
        columns.append(h if seen[h] == 1 else f"{h}_{seen[h]}")
    if len(body) > MAX_ROWS:
        raise AppError(400, "IMPORT_TOO_LARGE", f"O arquivo tem {len(body)} linhas. O limite é {MAX_ROWS} por importação.")
    if not body:
        raise AppError(400, "EMPTY_CSV", "O arquivo tem só o cabeçalho, sem linhas de dados.")
    return delimiter, columns, body


def suggest_mapping(entity: str, columns: list[str]) -> dict:
    mapping, by_norm = {}, {norm_text(c): c for c in columns}
    for field, names in ALIASES[entity].items():
        for n in names:
            if n in by_norm and by_norm[n] not in mapping.values():
                mapping[field] = by_norm[n]
                break
    return mapping


# ---------- Índice de registros existentes ----------
def _keys(entity: str, d: dict) -> list[str]:
    keys = []
    email, phone = norm_email(d.get("email")), norm_phone(d.get("phone"))
    if entity == "companies":
        if norm_company(d.get("name")):
            keys.append("n:" + norm_company(d["name"]))
        if norm_domain(d.get("website")):
            keys.append("d:" + norm_domain(d["website"]))
        if phone:
            keys.append("p:" + phone)
        return keys
    if email:
        keys.append("e:" + email)
    if phone:
        keys.append("p:" + phone)
    comp = norm_company(d.get("company"))
    if comp:
        keys.append(f"n:{norm_text(d.get('name'))}|{comp}")
    elif not email and not phone and entity == "leads":
        keys.append(f"n:{norm_text(d.get('name'))}|")
    return keys


def build_index(db, org: int, entity: str) -> dict:
    index: dict = {}
    if entity == "leads":
        sql = "SELECT id, name, email, phone, company FROM leads WHERE organization_id = ?"
    elif entity == "companies":
        sql = "SELECT id, name, website, phone FROM companies WHERE organization_id = ?"
    else:
        sql = ("SELECT c.id, c.name, c.email, c.phone, co.name AS company FROM contacts c "
               "LEFT JOIN companies co ON co.id = c.company_id WHERE c.organization_id = ?")
    for r in db.execute(sql, (org,)):
        for k in _keys(entity, dict(r)):
            index.setdefault(k, (r["id"], r["name"]))
    return index


# ---------- Análise (validação + duplicados) ----------
def analyze(db, user, entity: str, columns: list[str], body: list[list[str]], mapping: dict) -> list[dict]:
    org = user["organization_id"]
    fields = FIELDS[entity]
    for f, col in mapping.items():
        if f not in {x[0] for x in fields}:
            raise AppError(400, "INVALID_MAPPING", f"Campo desconhecido: {f}.")
        if col not in columns:
            raise AppError(400, "INVALID_MAPPING", f"A coluna “{col}” não existe no arquivo.")
    if not mapping.get("name"):
        raise AppError(400, "INVALID_MAPPING", "Associe uma coluna ao campo Nome.")
    idx = {c: i for i, c in enumerate(columns)}

    users = db.execute("SELECT id, name, email FROM users WHERE organization_id = ? AND active = 1", (org,)).fetchall()
    owner_by = {}
    for u in users:
        owner_by[u["email"].lower()] = u["id"]
        owner_by.setdefault(norm_text(u["name"]), u["id"])

    index = build_index(db, org, entity)
    seen_in_file: dict = {}
    results = []
    for n, raw in enumerate(body, start=2):          # linha 1 = cabeçalho
        data, errors, warnings = {}, [], []
        for fkey, label, required, maxlen in fields:
            col = mapping.get(fkey)
            v = (raw[idx[col]].strip() if col and idx[col] < len(raw) else "")
            data[fkey] = v or None
            if v and len(v) > maxlen and fkey != "channel":
                errors.append(f"{label}: máximo de {maxlen} caracteres")
        if not data["name"] or len(data["name"]) < 2:
            errors.append("Nome é obrigatório (mínimo 2 letras)")
        if data.get("email"):
            data["email"] = data["email"].lower()
            if not EMAIL_RE.match(data["email"]):
                errors.append("E-mail inválido")
        if entity == "leads" and data.get("channel"):
            ch = CHANNELS.get(norm_text(data["channel"]))
            if ch is None:
                errors.append("Canal inválido (use E-mail, WhatsApp, SMS, Redes sociais, Site, Evento ou Outros)")
            data["channel"] = ch
        if entity == "companies":
            t = norm_text(data.get("type") or "")
            data["type"] = "CLIENTE" if t.startswith("client") else "PROSPECT"
        owner_id = user["id"]
        if data.get("owner"):
            found = owner_by.get(data["owner"].lower()) or owner_by.get(norm_text(data["owner"]))
            if found:
                owner_id = found
            else:
                warnings.append(f"Responsável “{data['owner']}” não encontrado: ficou com você")
        data["owner_id"] = owner_id

        status, match = "OK", None
        if errors:
            status = "ERROR"
        else:
            keys = _keys(entity, data)
            hit = next((k for k in keys if k in index), None)
            if hit:
                status, match = "DUPLICATE", {"id": index[hit][0], "name": index[hit][1], "reason": REASON[hit[0]]}
            else:
                hit = next((k for k in keys if k in seen_in_file), None)
                if hit:
                    status, match = "DUP_IN_FILE", {"id": None, "name": None, "reason": f"{REASON[hit[0]]} da linha {seen_in_file[hit]}"}
            for k in keys:
                seen_in_file.setdefault(k, n)
        results.append({"row": n, "data": data, "status": status, "errors": errors, "warnings": warnings, "match": match})
    return results


def _summary(results: list[dict]) -> dict:
    return {"total": len(results), "ok": sum(r["status"] == "OK" for r in results),
            "duplicates": sum(r["status"] == "DUPLICATE" for r in results),
            "dupInFile": sum(r["status"] == "DUP_IN_FILE" for r in results),
            "errors": sum(r["status"] == "ERROR" for r in results)}


# ---------- Endpoints ----------
class ImportRequest(BaseModel):
    entity: str
    csv: str = Field(max_length=2_000_000)
    mapping: dict[str, str] | None = None


class CommitRequest(ImportRequest):
    onDuplicate: str = "SKIP"                  # SKIP | UPDATE | CREATE
    createCompanies: bool = True


def _prepare(data: ImportRequest):
    if data.entity not in FIELDS:
        raise AppError(400, "INVALID_ENTITY", "Escolha leads, empresas ou contatos.")
    delimiter, columns, body = parse_csv(data.csv)
    return delimiter, columns, body, (data.mapping if data.mapping is not None else suggest_mapping(data.entity, columns))


@router.post("/preview")
def preview(data: ImportRequest, db=Depends(get_db), user=Depends(require_perm("data.import"))):
    delimiter, columns, body, mapping = _prepare(data)
    out = {"delimiter": delimiter, "columns": columns, "mapping": mapping,
           "fields": [{"key": k, "label": l, "required": r} for k, l, r, _ in FIELDS[data.entity]],
           "sample": [dict(zip(columns, row)) for row in body[:5]], "totalRows": len(body)}
    if not mapping.get("name"):
        return {**out, "ready": False, "summary": None, "problems": []}
    results = analyze(db, user, data.entity, columns, body, mapping)
    problems = [{"row": r["row"], "status": r["status"], "name": r["data"].get("name"),
                 "messages": r["errors"] + r["warnings"], "match": r["match"]} for r in results if r["status"] != "OK" or r["warnings"]]
    return {**out, "ready": True, "summary": _summary(results), "problems": problems[:100]}


@router.post("/commit")
def commit(data: CommitRequest, db=Depends(get_db), user=Depends(require_perm("data.import"))):
    if data.onDuplicate not in ("SKIP", "UPDATE", "CREATE"):
        raise AppError(400, "INVALID_POLICY", "Escolha ignorar, atualizar ou criar mesmo assim.")
    _, columns, body, mapping = _prepare(data)
    results = analyze(db, user, data.entity, columns, body, mapping)
    org, now = user["organization_id"], now_iso()
    counts = {"created": 0, "updated": 0, "skipped": 0, "errors": 0, "companiesCreated": 0}
    lead_ids: list[int] = []
    company_cache = {}
    if data.entity == "contacts":
        for r in db.execute("SELECT id, name FROM companies WHERE organization_id = ?", (org,)):
            company_cache.setdefault(norm_company(r["name"]), r["id"])

    def company_id_for(name):
        if not name:
            return None
        key = norm_company(name)
        if key in company_cache:
            return company_cache[key]
        if not data.createCompanies:
            return None
        cur = db.execute(
            "INSERT INTO companies(organization_id, name, type, owner_id, created_at, updated_at) VALUES (?, ?, 'PROSPECT', ?, ?, ?)",
            (org, name, user["id"], now, now))
        company_cache[key] = cur.lastrowid
        counts["companiesCreated"] += 1
        return cur.lastrowid

    try:
        for r in results:
            d, st = r["data"], r["status"]
            if st == "ERROR":
                counts["errors"] += 1
                continue
            if st == "DUP_IN_FILE" and data.onDuplicate != "CREATE":
                counts["skipped"] += 1
                continue
            if st == "DUPLICATE" and data.onDuplicate == "SKIP":
                counts["skipped"] += 1
                continue
            if st == "DUPLICATE" and data.onDuplicate == "UPDATE":
                _update_existing(db, data.entity, r["match"]["id"], d, now, company_id_for)
                counts["updated"] += 1
                if data.entity == "leads":
                    lead_ids.append(r["match"]["id"])
                continue
            new_id = _insert(db, org, data.entity, d, now, company_id_for)
            counts["created"] += 1
            if data.entity == "leads":
                lead_ids.append(new_id)
        publish(db, user, "ImportCompleted", {"leads": "lead", "companies": "company", "contacts": "contact"}[data.entity], None,
                {"entity": data.entity, "policy": data.onDuplicate, **counts})
        db.commit()
    except Exception:
        db.rollback()
        raise
    for lid in lead_ids:                              # Etapa 8: leads novos já nascem com nota da IA
        rescore_lead(db, org, lid)
    db.commit()
    return {**counts, "total": len(results)}


def _insert(db, org, entity, d, now, company_id_for) -> int:
    if entity == "leads":
        cur = db.execute(
            "INSERT INTO leads(organization_id, name, email, phone, company, source, channel, owner_id, score, status, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'NOVO', ?, ?)",
            (org, d["name"], d["email"], d["phone"], d["company"], d["source"] or "Importação CSV", d["channel"], d["owner_id"], now, now))
    elif entity == "companies":
        cur = db.execute(
            "INSERT INTO companies(organization_id, name, industry, website, phone, city, notes, type, owner_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (org, d["name"], d["industry"], d["website"], d["phone"], d["city"], d["notes"], d["type"], d["owner_id"], now, now))
    else:
        cur = db.execute(
            "INSERT INTO contacts(organization_id, company_id, name, job_title, email, phone, owner_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'ATIVO', ?, ?)",
            (org, company_id_for(d["company"]), d["name"], d["job_title"], d["email"], d["phone"], d["owner_id"], now, now))
    return cur.lastrowid


def _update_existing(db, entity, rec_id, d, now, company_id_for) -> None:
    """Política "atualizar": só sobrescreve com o que veio preenchido no CSV (nunca apaga nada)."""
    cols = {"leads": ["email", "phone", "company", "source", "channel"],
            "companies": ["industry", "website", "phone", "city", "notes"],
            "contacts": ["job_title", "email", "phone"]}[entity]
    sets, args = [], []
    for c in cols:
        if d.get(c):
            sets.append(f"{c} = ?"); args.append(d[c])
    if entity == "companies" and d.get("type") == "CLIENTE":
        sets.append("type = 'CLIENTE'")
    if entity == "contacts" and d.get("company"):
        cid = company_id_for(d["company"])
        if cid:
            sets.append("company_id = ?"); args.append(cid)
    if sets:
        table = entity
        db.execute(f"UPDATE {table} SET {', '.join(sets)}, updated_at = ? WHERE id = ?", args + [now, rec_id])