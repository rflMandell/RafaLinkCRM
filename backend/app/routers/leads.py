from math import ceil
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..database import get_db, now_iso
from ..errors import AppError
from ..events import publish
from ..security import get_current_user
from ..services import check_owner as _check_owner, check_campaign, convert_lead

router = APIRouter(prefix="/leads", tags=["Leads"])

Channel = Literal["EMAIL", "WHATSAPP", "SMS", "REDES_SOCIAIS", "SITE", "EVENTO", "OUTROS"]
CHANNELS = list(Channel.__args__)

STATUSES = ["NOVO", "EM_CONTATO", "QUALIFICADO", "OPORTUNIDADE", "CONVERTIDO", "PERDIDO", "ARQUIVADO"]

# Máquina de estados do lead (RN02 e RN12)
TRANSITIONS = {
    "NOVO": {"EM_CONTATO", "PERDIDO", "ARQUIVADO"},
    "EM_CONTATO": {"QUALIFICADO", "PERDIDO", "ARQUIVADO"},
    "QUALIFICADO": {"OPORTUNIDADE", "CONVERTIDO", "PERDIDO", "ARQUIVADO"},
    "OPORTUNIDADE": {"CONVERTIDO", "PERDIDO", "ARQUIVADO"},
    "CONVERTIDO": set(),
    "PERDIDO": {"EM_CONTATO", "ARQUIVADO"},
    "ARQUIVADO": {"NOVO"},
}
EVENT_BY_STATUS = {
    "QUALIFICADO": "LeadQualified",
    "CONVERTIDO": "LeadConverted",
    "ARQUIVADO": "LeadArchived",
}
INTERACTION_STATUSES = {"EM_CONTATO", "QUALIFICADO"}

# Campos permitidos para ordenação (lista fixa evita SQL injection)
SORT_FIELDS = {
    "createdAt": "l.created_at",
    "updatedAt": "l.updated_at",
    "name": "l.name",
    "score": "l.score",
    "status": "l.status",
    "lastInteraction": "l.last_interaction_at",
}

FIELD_TO_COLUMN = {
    "name": "name",
    "email": "email",
    "phone": "phone",
    "company": "company",
    "source": "source",
    "channel": "channel",
    "ownerId": "owner_id",
    "score": "score",
    "nextAction": "next_action",
    "campaignId": "campaign_id",
}

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

SELECT_SQL = (
    "SELECT l.*, u.name AS owner_name, c.name AS contact_name, co.name AS company_name, "
    "op.title AS opportunity_title, ca.name AS campaign_name "
    "FROM leads l "
    "LEFT JOIN users u ON u.id = l.owner_id "
    "LEFT JOIN contacts c ON c.id = l.contact_id "
    "LEFT JOIN companies co ON co.id = l.company_id "
    "LEFT JOIN opportunities op ON op.id = l.opportunity_id "
    "LEFT JOIN campaigns ca ON ca.id = l.campaign_id"
)


# ---------- Schemas ----------
class LeadCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str | None = Field(default=None, pattern=EMAIL_PATTERN, max_length=160)
    phone: str | None = Field(default=None, max_length=30)
    company: str | None = Field(default=None, max_length=120)
    source: str | None = Field(default=None, max_length=80)
    channel: Channel | None = None
    ownerId: int | None = None
    score: int = Field(default=0, ge=0, le=100)
    nextAction: str | None = Field(default=None, max_length=200)
    campaignId: int | None = None


class LeadUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    email: str | None = Field(default=None, pattern=EMAIL_PATTERN, max_length=160)
    phone: str | None = Field(default=None, max_length=30)
    company: str | None = Field(default=None, max_length=120)
    source: str | None = Field(default=None, max_length=80)
    channel: Channel | None = None
    ownerId: int | None = None
    score: int | None = Field(default=None, ge=0, le=100)
    nextAction: str | None = Field(default=None, max_length=200)
    campaignId: int | None = None


class StatusChange(BaseModel):
    status: str
    reason: str | None = Field(default=None, max_length=200)


# ---------- Helpers ----------
def to_dto(r) -> dict:
    return {
        "id": r["id"],
        "name": r["name"],
        "email": r["email"],
        "phone": r["phone"],
        "company": r["company"],
        "source": r["source"],
        "channel": r["channel"],
        "ownerId": r["owner_id"],
        "ownerName": r["owner_name"],
        "contactId": r["contact_id"],
        "contactName": r["contact_name"],
        "companyId": r["company_id"],
        "companyName": r["company_name"],
        "opportunityId": r["opportunity_id"],
        "opportunityTitle": r["opportunity_title"],
        "campaignId": r["campaign_id"],
        "campaignName": r["campaign_name"],
        "firstContactAt": r["first_contact_at"],
        "score": r["score"],
        "status": r["status"],
        "lostReason": r["lost_reason"],
        "nextAction": r["next_action"],
        "lastInteractionAt": r["last_interaction_at"],
        "createdAt": r["created_at"],
        "updatedAt": r["updated_at"],
        "allowedActions": [s for s in STATUSES if s in TRANSITIONS[r["status"]]],
    }


def _get_lead(db, user, lead_id: int):
    row = db.execute(
        SELECT_SQL + " WHERE l.id = ? AND l.organization_id = ?",
        (lead_id, user["organization_id"]),
    ).fetchone()
    if row is None:
        raise AppError(404, "LEAD_NOT_FOUND", "Lead não encontrado.")
    return row


def _change_status(db, user, lead_id: int, new_status: str, reason: str | None = None) -> dict:
    lead = _get_lead(db, user, lead_id)
    current = lead["status"]

    if current == "CONVERTIDO":
        raise AppError(422, "LEAD_ALREADY_CONVERTED", "O lead informado já foi convertido.")
    if new_status not in STATUSES:
        raise AppError(400, "INVALID_STATUS", "Status inválido.")
    if new_status not in TRANSITIONS[current]:
        raise AppError(
            422,
            "INVALID_LEAD_TRANSITION",
            f"Não é possível mover o lead de {current} para {new_status}.",
        )
    if new_status == "CONVERTIDO":
        convert_lead(db, user, lead)  # RN04: cria contato (e empresa) a partir do lead

    now = now_iso()
    touched = now if new_status in INTERACTION_STATUSES else None
    db.execute(
        "UPDATE leads SET status = ?, lost_reason = ?, "
        "last_interaction_at = COALESCE(?, last_interaction_at), "
        "first_contact_at = COALESCE(first_contact_at, ?), updated_at = ? WHERE id = ?",
        (
            new_status,
            reason if new_status == "PERDIDO" else None,
            touched,
            touched,
            now,
            lead_id,
        ),
    )
    publish(
        db, user, EVENT_BY_STATUS.get(new_status, "LeadStatusChanged"), "lead", lead_id,
        {"from": current, "to": new_status},
    )
    db.commit()
    return to_dto(_get_lead(db, user, lead_id))


# ---------- Endpoints ----------
@router.get("/options")
def options(db=Depends(get_db), user=Depends(get_current_user)):
    """Dados para preencher os filtros e formulários do front."""
    owners = db.execute(
        "SELECT id, name FROM users WHERE organization_id = ? AND active = 1 ORDER BY name",
        (user["organization_id"],),
    ).fetchall()
    campaigns = db.execute(
        "SELECT id, name, status FROM campaigns WHERE organization_id = ? ORDER BY name",
        (user["organization_id"],),
    ).fetchall()
    return {
        "statuses": STATUSES, "channels": CHANNELS,
        "owners": [dict(o) for o in owners],
        "campaigns": [dict(c) for c in campaigns],
    }


@router.get("")
def list_leads(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    owner: int | None = None,
    source: str | None = None,
    channel: str | None = None,
    q: str | None = None,
    minScore: int | None = None,
    maxScore: int | None = None,
    campaign: int | None = None,
    sort: str = "createdAt,desc",
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    field, _, direction = sort.partition(",")
    column = SORT_FIELDS.get(field)
    if column is None or direction.lower() not in ("", "asc", "desc"):
        raise AppError(400, "INVALID_SORT", "Ordenação inválida.")
    direction = "DESC" if direction.lower() == "desc" else "ASC"

    where = ["l.organization_id = ?"]
    params: list = [user["organization_id"]]
    if status:
        where.append("l.status = ?")
        params.append(status)
    if owner is not None:
        where.append("l.owner_id = ?")
        params.append(owner)
    if source:
        where.append("l.source = ?")
        params.append(source)
    if channel:
        where.append("l.channel = ?")
        params.append(channel)
    if campaign is not None:
        where.append("l.campaign_id = ?")
        params.append(campaign)
    if q and q.strip():
        like = f"%{q.strip()}%"
        where.append("(l.name LIKE ? OR l.email LIKE ? OR l.company LIKE ?)")
        params += [like, like, like]
    if minScore is not None:
        where.append("l.score >= ?")
        params.append(minScore)
    if maxScore is not None:
        where.append("l.score <= ?")
        params.append(maxScore)

    where_sql = " WHERE " + " AND ".join(where)
    total = db.execute("SELECT COUNT(*) FROM leads l" + where_sql, params).fetchone()[0]
    rows = db.execute(
        SELECT_SQL + where_sql + f" ORDER BY {column} {direction}, l.id DESC LIMIT ? OFFSET ?",
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
def create_lead(data: LeadCreate, db=Depends(get_db), user=Depends(get_current_user)):
    owner_id = data.ownerId or user["id"]
    _check_owner(db, user, owner_id)
    check_campaign(db, user, data.campaignId, must_be_open=True)
    now = now_iso()
    cur = db.execute(
        "INSERT INTO leads(organization_id, name, email, phone, company, source, channel, "
        "owner_id, score, status, next_action, campaign_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'NOVO', ?, ?, ?, ?)",
        (
            user["organization_id"], data.name, data.email, data.phone, data.company,
            data.source, data.channel, owner_id, data.score, data.nextAction,
            data.campaignId, now, now,
        ),
    )
    lead_id = cur.lastrowid
    publish(db, user, "LeadCreated", "lead", lead_id, {"name": data.name})
    db.commit()
    return to_dto(_get_lead(db, user, lead_id))


@router.get("/{lead_id}")
def get_lead(lead_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    return to_dto(_get_lead(db, user, lead_id))


@router.patch("/{lead_id}")
def update_lead(lead_id: int, data: LeadUpdate, db=Depends(get_db), user=Depends(get_current_user)):
    lead = _get_lead(db, user, lead_id)
    if lead["status"] == "CONVERTIDO":
        raise AppError(422, "LEAD_ALREADY_CONVERTED", "O lead informado já foi convertido.")

    changes = data.model_dump(exclude_unset=True)
    if "ownerId" in changes:
        _check_owner(db, user, changes["ownerId"])

    if "campaignId" in changes and changes["campaignId"] != lead["campaign_id"]:
        check_campaign(db, user, changes["campaignId"], must_be_open=True)

    sets, params = [], []
    for field, value in changes.items():
        if field in ("name", "score") and value is None:
            continue
        sets.append(f"{FIELD_TO_COLUMN[field]} = ?")
        params.append(value)

    if sets:
        sets.append("updated_at = ?")
        params += [now_iso(), lead_id]
        db.execute(f"UPDATE leads SET {', '.join(sets)} WHERE id = ?", params)
        publish(db, user, "LeadUpdated", "lead", lead_id, {"fields": list(changes.keys())})
        db.commit()
    return to_dto(_get_lead(db, user, lead_id))


@router.post("/{lead_id}/status")
def change_status(lead_id: int, data: StatusChange, db=Depends(get_db), user=Depends(get_current_user)):
    return _change_status(db, user, lead_id, data.status, data.reason)


@router.post("/{lead_id}/qualify")
def qualify(lead_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    return _change_status(db, user, lead_id, "QUALIFICADO")


@router.post("/{lead_id}/convert")
def convert(lead_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    return _change_status(db, user, lead_id, "CONVERTIDO")


@router.post("/{lead_id}/archive")
def archive(lead_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    return _change_status(db, user, lead_id, "ARQUIVADO")