import json

from fastapi import APIRouter, Depends, Query

from ..database import get_db, now_iso
from ..errors import AppError
from ..security import get_current_user
from .activities import INTERACTION_TYPES, SELECT_SQL as ACTIVITY_SQL, to_dto as activity_dto

router = APIRouter(tags=["Customer 360"])

KINDS = ("lead", "contact", "company")

LEAD_LABEL = {
    "NOVO": "Novo", "EM_CONTATO": "Em contato", "QUALIFICADO": "Qualificado",
    "OPORTUNIDADE": "Oportunidade", "CONVERTIDO": "Convertido", "PERDIDO": "Perdido",
    "ARQUIVADO": "Arquivado",
}

# Eventos de domínio que aparecem na timeline
EVENT_TYPES = (
    "LeadQualified", "LeadConverted", "LeadArchived", "LeadStatusChanged",
    "OpportunityStageChanged", "OpportunityReopened",
)


def _marks(ids) -> str:
    return ",".join("?" * len(ids)) or "NULL"


def _ids(rows) -> set:
    return {r["id"] for r in rows}


def build_scope(db, org: int, kind: str, entity_id: int):
    """Descobre tudo que está ligado ao registro: leads, contatos, empresas e oportunidades."""
    scope = {"lead": set(), "contact": set(), "company": set(), "opportunity": set()}

    if kind == "lead":
        subject = db.execute(
            "SELECT * FROM leads WHERE id = ? AND organization_id = ?", (entity_id, org)
        ).fetchone()
        if subject is None:
            raise AppError(404, "LEAD_NOT_FOUND", "Lead não encontrado.")
        scope["lead"].add(entity_id)
        if subject["contact_id"]:
            scope["contact"].add(subject["contact_id"])
        scope["opportunity"] = _ids(db.execute(
            "SELECT id FROM opportunities WHERE organization_id = ? AND (lead_id = ? OR contact_id = ?)",
            (org, entity_id, subject["contact_id"]),
        ).fetchall())

    elif kind == "contact":
        subject = db.execute(
            "SELECT * FROM contacts WHERE id = ? AND organization_id = ?", (entity_id, org)
        ).fetchone()
        if subject is None:
            raise AppError(404, "CONTACT_NOT_FOUND", "Contato não encontrado.")
        scope["contact"].add(entity_id)
        scope["lead"] = _ids(db.execute(
            "SELECT id FROM leads WHERE organization_id = ? AND (contact_id = ? OR id = ?)",
            (org, entity_id, subject["source_lead_id"]),
        ).fetchall())
        leads = list(scope["lead"])
        scope["opportunity"] = _ids(db.execute(
            f"SELECT id FROM opportunities WHERE organization_id = ? AND (contact_id = ? OR lead_id IN ({_marks(leads)}))",
            [org, entity_id, *leads],
        ).fetchall())

    else:
        subject = db.execute(
            "SELECT * FROM companies WHERE id = ? AND organization_id = ?", (entity_id, org)
        ).fetchone()
        if subject is None:
            raise AppError(404, "COMPANY_NOT_FOUND", "Empresa não encontrada.")
        scope["company"].add(entity_id)
        scope["contact"] = _ids(db.execute(
            "SELECT id FROM contacts WHERE organization_id = ? AND company_id = ?", (org, entity_id)
        ).fetchall())
        contacts = list(scope["contact"])
        scope["lead"] = _ids(db.execute(
            f"SELECT id FROM leads WHERE organization_id = ? AND (company_id = ? OR contact_id IN ({_marks(contacts)}))",
            [org, entity_id, *contacts],
        ).fetchall())
        scope["opportunity"] = _ids(db.execute(
            "SELECT id FROM opportunities WHERE organization_id = ? AND company_id = ?", (org, entity_id)
        ).fetchall())

    return scope, subject


def _activity_conditions(scope):
    conds, params = [], []
    for col, key in (("lead_id", "lead"), ("contact_id", "contact"),
                     ("company_id", "company"), ("opportunity_id", "opportunity")):
        ids = list(scope[key])
        if ids:
            conds.append(f"a.{col} IN ({_marks(ids)})")
            params += ids
    return conds, params


def _event_title(r, payload: dict, opp_titles: dict) -> str:
    t = r["type"]
    frm, to = payload.get("from"), payload.get("to")
    if t == "LeadQualified":
        return "Lead qualificado"
    if t == "LeadConverted":
        return "Lead convertido em contato"
    if t == "LeadArchived":
        return "Lead arquivado"
    if t == "LeadStatusChanged":
        return f"Status do lead: {LEAD_LABEL.get(frm, frm)} → {LEAD_LABEL.get(to, to)}"
    name = opp_titles.get(r["entity_id"])
    suffix = f" ({name})" if name else ""
    if t == "OpportunityStageChanged":
        return f"Oportunidade movida: {frm} → {to}{suffix}"
    return f"Oportunidade reaberta{suffix}"


def build_timeline(db, org: int, scope: dict, limit: int) -> list[dict]:
    items: list[dict] = []

    def entry(kind, at, type_, title, description=None, status=None, user_name=None, activity=None):
        items.append({
            "kind": kind, "at": at, "type": type_, "title": title, "description": description,
            "status": status, "userName": user_name, "activity": activity,
        })

    # 1) Criação dos registros ("Lead criado", "Contato criado"...)
    for table, key, label, col in (
        ("leads", "lead", "Lead criado", "name"),
        ("contacts", "contact", "Contato criado", "name"),
        ("companies", "company", "Empresa criada", "name"),
        ("opportunities", "opportunity", "Oportunidade criada", "title"),
    ):
        ids = list(scope[key])
        if ids:
            rows = db.execute(
                f"SELECT {col} AS name, created_at FROM {table} WHERE id IN ({_marks(ids)})", ids
            ).fetchall()
            for r in rows:
                entry("EVENT", r["created_at"], key.upper() + "_CREATED", f"{label}: {r['name']}")

    # 2) Atividades concluídas
    conds, cparams = _activity_conditions(scope)
    if conds:
        rows = db.execute(
            ACTIVITY_SQL + " WHERE a.organization_id = ? AND a.status = 'CONCLUIDA' AND ("
            + " OR ".join(conds) + ") ORDER BY a.completed_at DESC LIMIT ?",
            [org, *cparams, limit],
        ).fetchall()
        now = now_iso()
        for r in rows:
            entry("ACTIVITY", r["completed_at"], r["type"], r["title"], r["description"],
                  r["status"], r["owner_name"], activity_dto(r, now))

    # 3) Mudanças de status (lead e oportunidade)
    opp_ids = list(scope["opportunity"])
    opp_titles = {}
    if opp_ids:
        opp_titles = {
            r["id"]: r["title"]
            for r in db.execute(
                f"SELECT id, title FROM opportunities WHERE id IN ({_marks(opp_ids)})", opp_ids
            ).fetchall()
        }
    clauses, clause_params = [], []
    for entity in ("lead", "opportunity"):
        ids = list(scope[entity])
        if ids:
            clauses.append(f"(e.entity = '{entity}' AND e.entity_id IN ({_marks(ids)}))")
            clause_params += ids
    if clauses:
        types = ",".join("?" * len(EVENT_TYPES))
        rows = db.execute(
            "SELECT e.*, u.name AS user_name FROM domain_events e "
            "LEFT JOIN users u ON u.id = e.user_id "
            f"WHERE e.organization_id = ? AND e.type IN ({types}) AND ({' OR '.join(clauses)}) "
            "ORDER BY e.created_at DESC LIMIT ?",
            [org, *EVENT_TYPES, *clause_params, limit],
        ).fetchall()
        for r in rows:
            payload = json.loads(r["payload"] or "{}")
            entry("EVENT", r["created_at"], r["type"], _event_title(r, payload, opp_titles),
                  user_name=r["user_name"])

    items.sort(key=lambda i: i["at"] or "", reverse=True)
    return items[:limit]


@router.get("/timeline")
def timeline(
    entity: str = Query(...),
    entity_id: int = Query(..., alias="id"),
    limit: int = Query(100, ge=1, le=300),
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    if entity not in KINDS:
        raise AppError(400, "INVALID_ENTITY", "Tipo de registro inválido.")
    org = user["organization_id"]
    scope, _ = build_scope(db, org, entity, entity_id)
    return {"content": build_timeline(db, org, scope, limit)}


@router.get("/customers/{kind}/{entity_id}")
def customer_360(kind: str, entity_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    if kind not in KINDS:
        raise AppError(404, "UNKNOWN_KIND", "Tipo de registro inválido.")
    org = user["organization_id"]
    scope, subject = build_scope(db, org, kind, entity_id)

    company_id = None
    if kind == "lead":
        title, email, phone = subject["name"], subject["email"], subject["phone"]
        status, status_kind, owner_id = subject["status"], "LEAD", subject["owner_id"]
        company_id = subject["company_id"]
        subtitle = subject["company"]
    elif kind == "contact":
        title, email, phone = subject["name"], subject["email"], subject["phone"]
        status, status_kind, owner_id = subject["status"], "CONTACT", subject["owner_id"]
        company_id = subject["company_id"]
        subtitle = subject["job_title"]
    else:
        title, email, phone = subject["name"], None, subject["phone"]
        status, status_kind, owner_id = subject["type"], "COMPANY", subject["owner_id"]
        subtitle = subject["industry"]

    company_name = None
    if company_id:
        row = db.execute("SELECT name FROM companies WHERE id = ?", (company_id,)).fetchone()
        company_name = row["name"] if row else None
        if kind == "contact":
            subtitle = " · ".join(p for p in (subject["job_title"], company_name) if p)

    owner_name = None
    if owner_id:
        row = db.execute("SELECT name FROM users WHERE id = ?", (owner_id,)).fetchone()
        owner_name = row["name"] if row else None

    # Score (leads) e última interação
    lead_ids = list(scope["lead"])
    score = None
    lead_last = None
    if lead_ids:
        r = db.execute(
            f"SELECT MAX(score) AS s, MAX(last_interaction_at) AS m FROM leads WHERE id IN ({_marks(lead_ids)})",
            lead_ids,
        ).fetchone()
        score, lead_last = r["s"], r["m"]

    # Oportunidades
    opp_ids = list(scope["opportunity"])
    opps = db.execute(
        "SELECT o.id, o.title, o.value, o.probability, o.status, o.realized_value, s.name AS stage_name "
        "FROM opportunities o JOIN pipeline_stages s ON s.id = o.stage_id "
        f"WHERE o.id IN ({_marks(opp_ids)}) ORDER BY o.created_at DESC",
        opp_ids,
    ).fetchall()
    open_opps = [o for o in opps if o["status"] == "ABERTA"]
    pipeline_value = sum(o["value"] for o in open_opps)
    weighted = sum(o["value"] * o["probability"] / 100 for o in open_opps)
    won_value = sum(
        o["realized_value"] if o["realized_value"] is not None else o["value"]
        for o in opps if o["status"] == "GANHA"
    )

    # Atividades
    conds, cparams = _activity_conditions(scope)
    now = now_iso()
    upcoming, activity_last = [], None
    if conds:
        scope_sql = " AND (" + " OR ".join(conds) + ")"
        rows = db.execute(
            ACTIVITY_SQL + " WHERE a.organization_id = ? AND a.status = 'PENDENTE'" + scope_sql
            + " ORDER BY a.due_at LIMIT 8",
            [org, *cparams],
        ).fetchall()
        upcoming = [activity_dto(r, now) for r in rows]

        interaction = sorted(INTERACTION_TYPES)
        activity_last = db.execute(
            "SELECT MAX(a.completed_at) AS m FROM activities a WHERE a.organization_id = ? "
            f"AND a.status = 'CONCLUIDA' AND a.type IN ({','.join('?' * len(interaction))})" + scope_sql,
            [org, *interaction, *cparams],
        ).fetchone()["m"]

    last_interaction = max((d for d in (lead_last, activity_last) if d), default=None)

    contacts = []
    if kind == "company":
        contacts = [
            {"id": c["id"], "name": c["name"], "jobTitle": c["job_title"], "email": c["email"]}
            for c in db.execute(
                "SELECT id, name, job_title, email FROM contacts WHERE organization_id = ? AND company_id = ? ORDER BY name",
                (org, entity_id),
            ).fetchall()
        ]

    return {
        "kind": kind,
        "id": entity_id,
        "title": title,
        "subtitle": subtitle,
        "email": email,
        "phone": phone,
        "status": status,
        "statusKind": status_kind,
        "ownerName": owner_name,
        "score": score,
        "companyId": company_id if kind != "company" else None,
        "companyName": company_name if kind != "company" else None,
        "openOpportunities": len(open_opps),
        "pipelineValue": round(pipeline_value, 2),
        "weightedValue": round(weighted, 2),
        "wonValue": round(won_value, 2),
        "lastInteractionAt": last_interaction,
        "opportunities": [
            {
                "id": o["id"], "title": o["title"], "stageName": o["stage_name"], "value": o["value"],
                "probability": o["probability"], "status": o["status"], "realizedValue": o["realized_value"],
            }
            for o in opps
        ],
        "contacts": contacts,
        "upcoming": upcoming,
        "timeline": build_timeline(db, org, scope, 50),
    }