from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..database import get_db, now_iso
from ..errors import AppError
from ..events import publish
from ..scoring import (
    CHURN_HIGH, CHURN_MID, HOT_MIN, WARM_MIN, WEIGHTS, apply_score, churn_company, company_actions,
    customer_contexts, lead_actions, lead_rows, load_weights, opportunity_actions, opportunity_rows,
    score_lead, sla_limits,
)
from ..security import get_current_user, require_roles
from ..permissions import require_perm

router = APIRouter(prefix="/ai", tags=["IA simulada"])
MANAGERS = ("ADMIN", "SALES_MANAGER")


def _scope(user, owner: int | None) -> int | None:
    """Vendedor só enxerga o que é dele; gerente/admin podem filtrar por responsável."""
    return user["id"] if user["role"] not in MANAGERS else owner


def _action_item(entity: str, row_id: int, name: str, owner_name, action: dict, extra: dict) -> dict:
    return {"entity": entity, "entityId": row_id, "name": name, "ownerName": owner_name, **action, **extra}


def _build(db, user, owner: int | None):
    """Calcula tudo de uma vez: leads pontuados, clientes com risco e a fila de ações."""
    org = user["organization_id"]
    now = datetime.now(timezone.utc)
    w, limits = load_weights(db, org), sla_limits(db, org)

    leads, worklist = [], []
    for r in lead_rows(db, org, now, owner=owner):
        sc = score_lead(r, w, now, limits)
        acts = lead_actions(r, sc, now, limits)
        leads.append({"id": r["id"], "name": r["name"], "company": r["company"], "status": r["status"],
                      "ownerName": r["owner_name"], "score": sc["score"], "storedScore": r["score"],
                      "level": sc["level"], "levelLabel": sc["levelLabel"], "action": acts[0]})
        worklist.append(_action_item("lead", r["id"], r["name"], r["owner_name"], acts[0],
                                     {"rank": sc["score"], "context": f"Lead · nota {sc['score']}"}))

    customers = []
    for ctx in customer_contexts(db, org, now, owner=owner):
        ch = churn_company(ctx, w, now)
        acts = company_actions(ctx, ch)
        c = ctx["company"]
        customers.append({"id": c["id"], "name": c["name"], "ownerName": c["owner_name"], "risk": ch["risk"],
                          "level": ch["level"], "levelLabel": ch["levelLabel"], "idleDays": ch["idleDays"],
                          "openOpportunities": ctx["open_count"], "action": acts[0],
                          "topFactor": ch["factors"][0]["detail"] if ch["factors"] else None})
        if acts[0]["code"] != "WATCH":
            worklist.append(_action_item("company", c["id"], c["name"], c["owner_name"], acts[0],
                                         {"rank": ch["risk"], "context": f"Cliente · risco {ch['risk']}"}))

    for o in opportunity_rows(db, org, now, owner=owner):
        acts = opportunity_actions(o, now, limits)
        worklist.append(_action_item("opportunity", o["id"], o["title"], o["owner_name"], acts[0],
                                     {"rank": min(o["value"] / 1000, 99), "context": f"Oportunidade · {o['probability']}%"}))

    worklist = [a for a in worklist if a["code"] != "WATCH"]
    worklist.sort(key=lambda a: (a["priority"], -a["rank"]))
    return leads, customers, worklist


@router.get("/overview")
def overview(owner: int | None = None, db=Depends(get_db), user=Depends(get_current_user)):
    owner = _scope(user, owner)
    leads, customers, worklist = _build(db, user, owner)
    org = user["organization_id"]
    team = db.execute("SELECT id, name FROM users WHERE organization_id = ? AND active = 1 ORDER BY name", (org,)).fetchall()

    def count(items, key, value):
        return sum(1 for i in items if i[key] == value)

    return {
        "summary": {
            "leads": {"total": len(leads), "QUENTE": count(leads, "level", "QUENTE"),
                      "MORNO": count(leads, "level", "MORNO"), "FRIO": count(leads, "level", "FRIO"),
                      "avgScore": round(sum(l["score"] for l in leads) / len(leads), 1) if leads else None,
                      "outdated": sum(1 for l in leads if l["score"] != l["storedScore"])},
            "churn": {"customers": len(customers), "ALTO": count(customers, "level", "ALTO"),
                      "MEDIO": count(customers, "level", "MEDIO"), "BAIXO": count(customers, "level", "BAIXO")},
            "actions": {"total": len(worklist), "ALTA": count(worklist, "priority", 1),
                        "MEDIA": count(worklist, "priority", 2), "BAIXA": count(worklist, "priority", 3)},
        },
        "hotLeads": sorted(leads, key=lambda l: -l["score"])[:8],
        "churnRisk": sorted(customers, key=lambda c: -c["risk"])[:8],
        "worklist": worklist[:30],
        "thresholds": {"hot": HOT_MIN, "warm": WARM_MIN, "churnHigh": CHURN_HIGH, "churnMid": CHURN_MID},
        "owners": [dict(t) for t in team] if user["role"] in MANAGERS else [],
        "canManage": user["role"] in MANAGERS,
    }


@router.get("/leads")
def list_leads(level: str | None = Query(None, pattern="^(QUENTE|MORNO|FRIO)$"), owner: int | None = None,
               db=Depends(get_db), user=Depends(get_current_user)):
    leads, _, _ = _build(db, user, _scope(user, owner))
    if level:
        leads = [l for l in leads if l["level"] == level]
    return {"content": sorted(leads, key=lambda l: -l["score"])}


@router.get("/churn")
def list_churn(level: str | None = Query(None, pattern="^(ALTO|MEDIO|BAIXO)$"), owner: int | None = None,
               db=Depends(get_db), user=Depends(get_current_user)):
    _, customers, _ = _build(db, user, _scope(user, owner))
    if level:
        customers = [c for c in customers if c["level"] == level]
    return {"content": sorted(customers, key=lambda c: -c["risk"])}


@router.get("/next-actions")
def next_actions(entity: str | None = Query(None, pattern="^(lead|company|opportunity)$"), owner: int | None = None,
                 db=Depends(get_db), user=Depends(get_current_user)):
    _, _, worklist = _build(db, user, _scope(user, owner))
    if entity:
        worklist = [a for a in worklist if a["entity"] == entity]
    return {"content": worklist[:100]}


# ---------- Detalhe por entidade (cards nas páginas) ----------
@router.get("/leads/{lead_id}")
def lead_detail(lead_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    org, now = user["organization_id"], datetime.now(timezone.utc)
    rows = lead_rows(db, org, now, lead_id=lead_id)
    if not rows:
        raise AppError(404, "LEAD_NOT_FOUND", "Lead não encontrado.")
    r = rows[0]
    limits = sla_limits(db, org)
    scored = r["status"] in ("NOVO", "EM_CONTATO", "QUALIFICADO", "OPORTUNIDADE")
    if not scored:
        return {"id": r["id"], "name": r["name"], "scored": False, "storedScore": r["score"],
                "message": "Leads convertidos, perdidos ou arquivados não são pontuados.", "actions": []}
    sc = score_lead(r, load_weights(db, org), now, limits)
    return {"id": r["id"], "name": r["name"], "scored": True, "storedScore": r["score"], "scoredAt": r["scored_at"],
            **sc, "actions": lead_actions(r, sc, now, limits)}


@router.post("/leads/{lead_id}/rescore")
def rescore_one(lead_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    detail = lead_detail(lead_id, db, user)
    if not detail["scored"]:
        raise AppError(409, "LEAD_NOT_SCORABLE", detail["message"])
    old = detail["storedScore"]
    apply_score(db, lead_id, detail)
    publish(db, user, "LeadScored", "lead", lead_id, {"from": old, "to": detail["score"], "level": detail["level"]})
    db.commit()
    return {**detail, "storedScore": detail["score"]}


@router.post("/leads/rescore")
def rescore_all(db=Depends(get_db), user=Depends(get_current_user)):
    org, now = user["organization_id"], datetime.now(timezone.utc)
    w, limits = load_weights(db, org), sla_limits(db, org)
    updated = changed = 0
    for r in lead_rows(db, org, now, owner=_scope(user, None)):
        sc = score_lead(r, w, now, limits)
        if sc["score"] != r["score"]:
            changed += 1
        apply_score(db, r["id"], sc)
        updated += 1
    publish(db, user, "LeadScoresRecalculated", "lead", None, {"updated": updated, "changed": changed})
    db.commit()
    return {"updated": updated, "changed": changed}


@router.get("/companies/{company_id}")
def company_detail(company_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    org, now = user["organization_id"], datetime.now(timezone.utc)
    ctxs = customer_contexts(db, org, now, company_id=company_id)
    if not ctxs:
        exists = db.execute("SELECT 1 FROM companies WHERE id = ? AND organization_id = ?", (company_id, org)).fetchone()
        if not exists:
            raise AppError(404, "COMPANY_NOT_FOUND", "Empresa não encontrada.")
        return {"id": company_id, "applicable": False,
                "message": "O risco de churn só é calculado para clientes (empresas com venda ganha).", "actions": []}
    ctx = ctxs[0]
    ch = churn_company(ctx, load_weights(db, org), now)
    return {"id": company_id, "name": ctx["company"]["name"], "applicable": True, **ch,
            "openOpportunities": ctx["open_count"], "overdueTasks": ctx["overdue"],
            "actions": company_actions(ctx, ch)}


@router.get("/opportunities/{opp_id}")
def opportunity_detail(opp_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    org, now = user["organization_id"], datetime.now(timezone.utc)
    rows = opportunity_rows(db, org, now, opp_id=opp_id)
    if not rows:
        exists = db.execute("SELECT 1 FROM opportunities WHERE id = ? AND organization_id = ?", (opp_id, org)).fetchone()
        if not exists:
            raise AppError(404, "OPPORTUNITY_NOT_FOUND", "Oportunidade não encontrada.")
        return {"id": opp_id, "applicable": False, "message": "Oportunidade já encerrada.", "actions": []}
    return {"id": opp_id, "applicable": True, "actions": opportunity_actions(rows[0], now, sla_limits(db, org))}


# ---------- Pesos ----------
class WeightsUpdate(BaseModel):
    weights: dict[str, float]


def _weights_dto(db, org: int, can_manage: bool) -> dict:
    current = load_weights(db, org)
    return {
        "canManage": can_manage,
        "weights": [
            {"key": k, "label": lbl, "group": grp, "default": d, "value": current[k], "min": lo, "max": hi,
             "custom": current[k] != d}
            for k, (d, lbl, grp, lo, hi) in WEIGHTS.items()
        ],
        "thresholds": {"hot": HOT_MIN, "warm": WARM_MIN, "churnHigh": CHURN_HIGH, "churnMid": CHURN_MID},
    }


@router.get("/weights")
def get_weights(db=Depends(get_db), user=Depends(get_current_user)):
    return _weights_dto(db, user["organization_id"], user["role"] in MANAGERS)


@router.put("/weights")
def put_weights(data: WeightsUpdate, db=Depends(get_db), user=Depends(require_perm("ai.weights"))):
    for key, value in data.weights.items():
        if key not in WEIGHTS:
            raise AppError(400, "UNKNOWN_WEIGHT", f"Peso desconhecido: {key}.")
        lo, hi = WEIGHTS[key][3], WEIGHTS[key][4]
        if not lo <= value <= hi:
            raise AppError(400, "WEIGHT_OUT_OF_RANGE", f"{WEIGHTS[key][1]}: use um valor entre {lo:g} e {hi:g}.")
    org = user["organization_id"]
    for key, value in data.weights.items():
        if value == WEIGHTS[key][0]:
            db.execute("DELETE FROM ai_weights WHERE organization_id = ? AND key = ?", (org, key))
        else:
            db.execute(
                "INSERT INTO ai_weights(organization_id, key, value, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(organization_id, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (org, key, value, now_iso()),
            )
    publish(db, user, "AiWeightsUpdated", "ai_weights", None, {"keys": sorted(data.weights)})
    db.commit()
    return _weights_dto(db, org, True)


@router.delete("/weights")
def reset_weights(db=Depends(get_db), user=Depends(require_perm("ai.weights"))):
    db.execute("DELETE FROM ai_weights WHERE organization_id = ?", (user["organization_id"],))
    publish(db, user, "AiWeightsReset", "ai_weights", None, {})
    db.commit()
    return _weights_dto(db, user["organization_id"], True)