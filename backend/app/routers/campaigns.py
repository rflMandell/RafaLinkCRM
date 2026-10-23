from datetime import date
from math import ceil
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from ..database import get_db, now_iso
from ..errors import AppError
from ..events import publish
from ..security import get_current_user, require_roles
from ..services import check_owner, parse_sort
from .leads import CHANNELS, Channel

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])

Status = Literal["RASCUNHO", "ATIVA", "PAUSADA", "ENCERRADA"]
STATUSES = list(Status.__args__)

# Máquina de estados da campanha (RN12: transição inválida devolve 422)
TRANSITIONS = {
    "RASCUNHO": {"ATIVA", "ENCERRADA"},
    "ATIVA": {"PAUSADA", "ENCERRADA"},
    "PAUSADA": {"ATIVA", "ENCERRADA"},
    "ENCERRADA": set(),
}

SORT_FIELDS = {
    "createdAt": "c.created_at",
    "name": "c.name",
    "startDate": "c.start_date",
    "cost": "c.cost",
    "leads": "leads_count",
    "revenue": "revenue",
}

FIELD_TO_COLUMN = {
    "name": "name", "channel": "channel", "budget": "budget", "cost": "cost",
    "startDate": "start_date", "endDate": "end_date", "description": "description",
    "ownerId": "owner_id",
}

# Métricas calculadas na própria consulta: leads atribuídos (leads.campaign_id) e
# oportunidades herdadas na conversão (opportunities.campaign_id).
SELECT_SQL = (
    "SELECT c.*, u.name AS owner_name, "
    "(SELECT COUNT(*) FROM leads l WHERE l.campaign_id = c.id) AS leads_count, "
    "(SELECT COUNT(*) FROM leads l WHERE l.campaign_id = c.id AND l.status = 'CONVERTIDO') AS converted_count, "
    "(SELECT COUNT(*) FROM opportunities o WHERE o.campaign_id = c.id) AS opps_count, "
    "(SELECT COUNT(*) FROM opportunities o WHERE o.campaign_id = c.id AND o.status = 'GANHA') AS won_count, "
    "(SELECT COALESCE(SUM(COALESCE(o.realized_value, o.value)), 0) FROM opportunities o "
    "  WHERE o.campaign_id = c.id AND o.status = 'GANHA') AS revenue, "
    "(SELECT COALESCE(SUM(o.value), 0) FROM opportunities o "
    "  WHERE o.campaign_id = c.id AND o.status = 'ABERTA') AS open_value "
    "FROM campaigns c LEFT JOIN users u ON u.id = c.owner_id"
)


# ---------- Schemas ----------
class CampaignCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    channel: Channel | None = None
    budget: float = Field(default=0, ge=0)
    cost: float = Field(default=0, ge=0)
    startDate: date | None = None
    endDate: date | None = None
    description: str | None = Field(default=None, max_length=1000)
    ownerId: int | None = None


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    channel: Channel | None = None
    budget: float | None = Field(default=None, ge=0)
    cost: float | None = Field(default=None, ge=0)
    startDate: date | None = None
    endDate: date | None = None
    description: str | None = Field(default=None, max_length=1000)
    ownerId: int | None = None


class StatusChange(BaseModel):
    status: Status


# ---------- Helpers ----------
def metrics(r) -> dict:
    leads, converted = r["leads_count"], r["converted_count"]
    won, revenue, cost = r["won_count"], r["revenue"], r["cost"]
    return {
        "leads": leads,
        "converted": converted,
        "conversionRate": round(converted / leads * 100, 1) if leads else 0,
        "opportunities": r["opps_count"],
        "won": won,
        "revenue": round(revenue, 2),
        "openValue": round(r["open_value"], 2),
        "costPerLead": round(cost / leads, 2) if leads and cost else None,
        "cac": round(cost / won, 2) if won and cost else None,  # custo de aquisição por venda ganha
        "roi": round((revenue - cost) / cost * 100, 1) if cost > 0 else None,
    }


def to_dto(r) -> dict:
    return {
        "id": r["id"],
        "name": r["name"],
        "channel": r["channel"],
        "status": r["status"],
        "budget": r["budget"],
        "cost": r["cost"],
        "startDate": r["start_date"],
        "endDate": r["end_date"],
        "description": r["description"],
        "ownerId": r["owner_id"],
        "ownerName": r["owner_name"],
        "createdAt": r["created_at"],
        "updatedAt": r["updated_at"],
        "allowedActions": [s for s in STATUSES if s in TRANSITIONS[r["status"]]],
        "metrics": metrics(r),
    }


def _get(db, user, campaign_id: int):
    row = db.execute(
        SELECT_SQL + " WHERE c.id = ? AND c.organization_id = ?",
        (campaign_id, user["organization_id"]),
    ).fetchone()
    if row is None:
        raise AppError(404, "CAMPAIGN_NOT_FOUND", "Campanha não encontrada.")
    return row


def _check_period(start, end) -> None:
    if start and end and end < start:
        raise AppError(422, "INVALID_PERIOD", "A data final não pode ser anterior à data inicial.")


def _detail(db, user, campaign_id: int) -> dict:
    row = _get(db, user, campaign_id)
    dto = to_dto(row)

    by_status = db.execute(
        "SELECT status, COUNT(*) AS n FROM leads WHERE campaign_id = ? GROUP BY status", (campaign_id,)
    ).fetchall()
    dto["leadsByStatus"] = {r["status"]: r["n"] for r in by_status}

    leads = db.execute(
        "SELECT id, name, company, status, score, created_at FROM leads "
        "WHERE campaign_id = ? ORDER BY created_at DESC, id DESC LIMIT 10",
        (campaign_id,),
    ).fetchall()
    dto["leads"] = [
        {"id": l["id"], "name": l["name"], "company": l["company"], "status": l["status"],
         "score": l["score"], "createdAt": l["created_at"]}
        for l in leads
    ]

    opps = db.execute(
        "SELECT o.id, o.title, o.value, o.status, s.name AS stage_name FROM opportunities o "
        "JOIN pipeline_stages s ON s.id = o.stage_id "
        "WHERE o.campaign_id = ? ORDER BY o.created_at DESC, o.id DESC LIMIT 10",
        (campaign_id,),
    ).fetchall()
    dto["opportunities"] = [
        {"id": o["id"], "title": o["title"], "value": o["value"], "status": o["status"],
         "stageName": o["stage_name"]}
        for o in opps
    ]
    return dto


# ---------- Endpoints ----------
@router.get("/options")
def options(db=Depends(get_db), user=Depends(get_current_user)):
    owners = db.execute(
        "SELECT id, name FROM users WHERE organization_id = ? AND active = 1 ORDER BY name",
        (user["organization_id"],),
    ).fetchall()
    return {"statuses": STATUSES, "channels": CHANNELS, "owners": [dict(o) for o in owners]}


@router.get("")
def list_campaigns(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    status: str | None = None,
    channel: str | None = None,
    sort: str = "createdAt,desc",
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    column, direction = parse_sort(sort, SORT_FIELDS)

    where = ["c.organization_id = ?"]
    params: list = [user["organization_id"]]
    if q and q.strip():
        where.append("c.name LIKE ?")
        params.append(f"%{q.strip()}%")
    if status:
        where.append("c.status = ?")
        params.append(status)
    if channel:
        where.append("c.channel = ?")
        params.append(channel)

    where_sql = " WHERE " + " AND ".join(where)
    total = db.execute("SELECT COUNT(*) FROM campaigns c" + where_sql, params).fetchone()[0]
    rows = db.execute(
        SELECT_SQL + where_sql + f" ORDER BY {column} {direction}, c.id DESC LIMIT ? OFFSET ?",
        params + [size, page * size],
    ).fetchall()
    return {
        "content": [to_dto(r) for r in rows],
        "page": page,
        "size": size,
        "totalElements": total,
        "totalPages": ceil(total / size),
    }


@router.post("", status_code=201)
def create_campaign(data: CampaignCreate, db=Depends(get_db), user=Depends(get_current_user)):
    owner_id = data.ownerId or user["id"]
    check_owner(db, user, owner_id)
    _check_period(data.startDate, data.endDate)

    now = now_iso()
    cur = db.execute(
        "INSERT INTO campaigns(organization_id, name, channel, status, budget, cost, start_date, "
        "end_date, description, owner_id, created_at, updated_at) "
        "VALUES (?, ?, ?, 'RASCUNHO', ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user["organization_id"], data.name.strip(), data.channel, data.budget, data.cost,
            data.startDate.isoformat() if data.startDate else None,
            data.endDate.isoformat() if data.endDate else None,
            data.description, owner_id, now, now,
        ),
    )
    campaign_id = cur.lastrowid
    publish(db, user, "CampaignCreated", "campaign", campaign_id, {"name": data.name})
    db.commit()
    return _detail(db, user, campaign_id)


@router.get("/{campaign_id}")
def get_campaign(campaign_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    return _detail(db, user, campaign_id)


@router.patch("/{campaign_id}")
def update_campaign(
    campaign_id: int, data: CampaignUpdate, db=Depends(get_db), user=Depends(get_current_user)
):
    campaign = _get(db, user, campaign_id)
    changes = data.model_dump(exclude_unset=True)
    if "ownerId" in changes:
        check_owner(db, user, changes["ownerId"])

    start = changes["startDate"].isoformat() if changes.get("startDate") else (
        None if "startDate" in changes else campaign["start_date"])
    end = changes["endDate"].isoformat() if changes.get("endDate") else (
        None if "endDate" in changes else campaign["end_date"])
    _check_period(start, end)  # ISO "AAAA-MM-DD" compara certo como texto

    sets, params = [], []
    for field, value in changes.items():
        if field in ("name", "budget", "cost") and value is None:
            continue
        if field in ("startDate", "endDate") and value is not None:
            value = value.isoformat()
        if field == "name":
            value = value.strip()
        sets.append(f"{FIELD_TO_COLUMN[field]} = ?")
        params.append(value)

    if sets:
        sets.append("updated_at = ?")
        params += [now_iso(), campaign_id]
        db.execute(f"UPDATE campaigns SET {', '.join(sets)} WHERE id = ?", params)
        publish(db, user, "CampaignUpdated", "campaign", campaign_id, {"fields": list(changes.keys())})
        db.commit()
    return _detail(db, user, campaign_id)


@router.post("/{campaign_id}/status")
def change_status(
    campaign_id: int, data: StatusChange, db=Depends(get_db), user=Depends(get_current_user)
):
    campaign = _get(db, user, campaign_id)
    current = campaign["status"]
    if data.status not in TRANSITIONS[current]:
        raise AppError(
            422, "INVALID_CAMPAIGN_TRANSITION",
            f"Não é possível mover a campanha de {current} para {data.status}.",
        )
    db.execute(
        "UPDATE campaigns SET status = ?, updated_at = ? WHERE id = ?",
        (data.status, now_iso(), campaign_id),
    )
    publish(db, user, "CampaignStatusChanged", "campaign", campaign_id,
            {"from": current, "to": data.status})
    db.commit()
    return _detail(db, user, campaign_id)


@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(
    campaign_id: int,
    db=Depends(get_db),
    user=Depends(require_roles("ADMIN", "SALES_MANAGER")),
):
    campaign = _get(db, user, campaign_id)
    # Leads e oportunidades continuam existindo, só perdem a atribuição.
    db.execute("UPDATE leads SET campaign_id = NULL WHERE campaign_id = ?", (campaign_id,))
    db.execute("UPDATE opportunities SET campaign_id = NULL WHERE campaign_id = ?", (campaign_id,))
    db.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
    publish(db, user, "CampaignDeleted", "campaign", campaign_id, {"name": campaign["name"]})
    db.commit()
    return Response(status_code=204)