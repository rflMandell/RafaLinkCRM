from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..database import get_db, now_iso
from ..errors import AppError
from ..events import publish
from ..security import get_current_user, require_roles
from ..permissions import has_perm, require_perm

router = APIRouter(prefix="/sla", tags=["SLA"])

MANAGERS = ("ADMIN", "SALES_MANAGER")
WARN_AT = 0.75  # a partir de 75% do prazo vira "atenção"

# tipo -> (nome, unidade, prazo padrão, entidade monitorada)
POLICIES = {
    "FIRST_CONTACT": ("Primeiro contato do lead", "h", 24, "lead"),
    "LEAD_IDLE": ("Lead sem interação", "dias", 5, "lead"),
    "OPP_STALE": ("Oportunidade parada na etapa", "dias", 14, "opportunity"),
}


class PolicyUpdate(BaseModel):
    threshold: float = Field(gt=0, le=100000)
    active: bool = True


def ensure_policies(db, org: int) -> None:
    """Cria as políticas padrão da organização na primeira vez que são pedidas."""
    have = {r["kind"] for r in db.execute("SELECT kind FROM sla_policies WHERE organization_id = ?", (org,))}
    for kind, (_, _, default, _) in POLICIES.items():
        if kind not in have:
            db.execute(
                "INSERT INTO sla_policies(organization_id, kind, threshold, active, updated_at) "
                "VALUES (?, ?, ?, 1, ?)", (org, kind, default, now_iso()),
            )
    db.commit()


def _hours_since(ts: str, now: datetime) -> float:
    return (now - datetime.fromisoformat(ts)).total_seconds() / 3600


def _severity(age: float, limit: float) -> str | None:
    if age > limit:
        return "BREACH"
    if age >= limit * WARN_AT:
        return "WARNING"
    return None


@router.get("")
def overview(owner: int | None = None, db=Depends(get_db), user=Depends(get_current_user)):
    org = user["organization_id"]
    ensure_policies(db, org)
    now = datetime.now(timezone.utc)
    policies = {r["kind"]: r for r in db.execute("SELECT * FROM sla_policies WHERE organization_id = ?", (org,))}

    items: list[dict] = []
    summary: dict = {}
    own = " AND l.owner_id = ?" if owner is not None else ""
    own_args = [owner] if owner is not None else []

    def add(kind, entity, row, ref, age, limit, unit):
        sev = _severity(age, limit)
        if sev:
            items.append({
                "kind": kind, "entity": entity, "entityId": row["id"], "name": row["name"],
                "ownerName": row["owner_name"], "age": round(age, 1), "threshold": limit,
                "unit": unit, "severity": sev, "since": ref,
            })
        return sev

    # 1) Primeiro contato: leads NOVO ainda sem contato (acionável) + coorte dos últimos 30 dias (histórico)
    p = policies["FIRST_CONTACT"]
    summary["FIRST_CONTACT"] = {"monitored": 0, "breached": 0, "warning": 0, "compliance": None}
    if p["active"]:
        limit = p["threshold"]
        rows = db.execute(
            "SELECT l.id, l.name, l.status, l.created_at, l.first_contact_at, u.name AS owner_name "
            "FROM leads l LEFT JOIN users u ON u.id = l.owner_id "
            "WHERE l.organization_id = ? AND l.status != 'ARQUIVADO'" + own, [org] + own_args,
        ).fetchall()
        met = late = 0
        for r in rows:
            age_now = _hours_since(r["created_at"], now)
            if r["first_contact_at"]:
                if age_now <= 24 * 30:  # coorte recente
                    delay = (datetime.fromisoformat(r["first_contact_at"]) - datetime.fromisoformat(r["created_at"])).total_seconds() / 3600
                    if delay <= limit:
                        met += 1
                    else:
                        late += 1
            elif r["status"] == "NOVO":
                sev = add("FIRST_CONTACT", "lead", r, r["created_at"], age_now, limit, "h")
                if sev == "BREACH":
                    summary["FIRST_CONTACT"]["breached"] += 1
                    if age_now <= 24 * 30:
                        late += 1
                elif sev == "WARNING":
                    summary["FIRST_CONTACT"]["warning"] += 1
        denom = met + late
        summary["FIRST_CONTACT"]["monitored"] = denom
        summary["FIRST_CONTACT"]["compliance"] = round(met / denom * 100, 1) if denom else None

    # 2) Lead parado: sem interação há mais que o prazo
    p = policies["LEAD_IDLE"]
    summary["LEAD_IDLE"] = {"monitored": 0, "breached": 0, "warning": 0, "compliance": None}
    if p["active"]:
        limit = p["threshold"]
        rows = db.execute(
            "SELECT l.id, l.name, l.created_at, l.last_interaction_at, u.name AS owner_name "
            "FROM leads l LEFT JOIN users u ON u.id = l.owner_id "
            "WHERE l.organization_id = ? AND l.status IN ('EM_CONTATO', 'QUALIFICADO', 'OPORTUNIDADE')" + own,
            [org] + own_args,
        ).fetchall()
        s = summary["LEAD_IDLE"]
        for r in rows:
            ref = r["last_interaction_at"] or r["created_at"]
            sev = add("LEAD_IDLE", "lead", r, ref, _hours_since(ref, now) / 24, limit, "dias")
            s["monitored"] += 1
            s["breached"] += sev == "BREACH"
            s["warning"] += sev == "WARNING"
        s["compliance"] = round((s["monitored"] - s["breached"]) / s["monitored"] * 100, 1) if s["monitored"] else None

    # 3) Oportunidade parada na mesma etapa
    p = policies["OPP_STALE"]
    summary["OPP_STALE"] = {"monitored": 0, "breached": 0, "warning": 0, "compliance": None}
    if p["active"]:
        limit = p["threshold"]
        rows = db.execute(
            "SELECT o.id, o.title AS name, o.stage_changed_at, u.name AS owner_name "
            "FROM opportunities o LEFT JOIN users u ON u.id = o.owner_id "
            "WHERE o.organization_id = ? AND o.status = 'ABERTA'"
            + (" AND o.owner_id = ?" if owner is not None else ""),
            [org] + own_args,
        ).fetchall()
        s = summary["OPP_STALE"]
        for r in rows:
            sev = add("OPP_STALE", "opportunity", r, r["stage_changed_at"],
                      _hours_since(r["stage_changed_at"], now) / 24, limit, "dias")
            s["monitored"] += 1
            s["breached"] += sev == "BREACH"
            s["warning"] += sev == "WARNING"
        s["compliance"] = round((s["monitored"] - s["breached"]) / s["monitored"] * 100, 1) if s["monitored"] else None

    items.sort(key=lambda i: (i["severity"] != "BREACH", -i["age"] / i["threshold"]))
    team = db.execute(
        "SELECT id, name FROM users WHERE organization_id = ? AND active = 1 ORDER BY name", (org,)
    ).fetchall()
    return {
        "policies": [
            {"kind": k, "label": POLICIES[k][0], "unit": POLICIES[k][1], "entity": POLICIES[k][3],
             "threshold": policies[k]["threshold"], "active": bool(policies[k]["active"])}
            for k in POLICIES
        ],
        "summary": summary,
        "totalBreached": sum(s["breached"] for s in summary.values()),
        "totalWarning": sum(s["warning"] for s in summary.values()),
        "items": items[:200],
        "owners": [dict(t) for t in team],
        "canManage": has_perm(db, user, "goals.manage"),
    }


@router.put("/policies/{kind}")
def update_policy(
    kind: str, data: PolicyUpdate, db=Depends(get_db), user=Depends(require_perm("goals.manage"))
):
    if kind not in POLICIES:
        raise AppError(404, "SLA_POLICY_NOT_FOUND", "Política de SLA não encontrada.")
    ensure_policies(db, user["organization_id"])
    db.execute(
        "UPDATE sla_policies SET threshold = ?, active = ?, updated_at = ? WHERE organization_id = ? AND kind = ?",
        (data.threshold, 1 if data.active else 0, now_iso(), user["organization_id"], kind),
    )
    publish(db, user, "SlaPolicyUpdated", "sla_policy", None, {"kind": kind, "threshold": data.threshold, "active": data.active})
    db.commit()
    return {"kind": kind, "threshold": data.threshold, "active": data.active}