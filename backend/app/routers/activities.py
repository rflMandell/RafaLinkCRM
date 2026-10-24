from datetime import datetime
from math import ceil
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from ..database import get_db, now_iso
from ..errors import AppError
from ..events import publish
from ..security import get_current_user
from ..services import check_owner, parse_sort, to_utc_iso
from ..scoring import rescore_lead

router = APIRouter(prefix="/activities", tags=["Activities"])
agenda_router = APIRouter(prefix="/agenda", tags=["Agenda"])
tasks_router = APIRouter(prefix="/tasks", tags=["Tasks"])

ActivityType = Literal["LIGACAO", "EMAIL", "WHATSAPP", "REUNIAO", "TAREFA", "NOTA", "FOLLOW_UP"]
TYPES = list(ActivityType.__args__)

# Tipos que contam como "interação com o cliente" (atualizam a última interação do lead)
INTERACTION_TYPES = {"LIGACAO", "EMAIL", "WHATSAPP", "REUNIAO", "FOLLOW_UP"}
MANAGER_ROLES = {"ADMIN", "SALES_MANAGER"}
MAX_AGENDA_DAYS = 62

SORT_FIELDS = {
    "dueAt": "a.due_at",
    "createdAt": "a.created_at",
    "title": "a.title",
    "type": "a.type",
}

FIELD_TO_COLUMN = {
    "title": "title", "description": "description", "dueAt": "due_at", "ownerId": "owner_id",
}

SELECT_SQL = (
    "SELECT a.*, u.name AS owner_name, l.name AS lead_name, c.name AS contact_name, "
    "co.name AS company_name, o.title AS opportunity_title "
    "FROM activities a "
    "LEFT JOIN users u ON u.id = a.owner_id "
    "LEFT JOIN leads l ON l.id = a.lead_id "
    "LEFT JOIN contacts c ON c.id = a.contact_id "
    "LEFT JOIN companies co ON co.id = a.company_id "
    "LEFT JOIN opportunities o ON o.id = a.opportunity_id"
)


# ---------- Schemas ----------
class ActivityCreate(BaseModel):
    type: ActivityType
    title: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    dueAt: datetime | None = None
    completed: bool = False
    ownerId: int | None = None
    leadId: int | None = None
    contactId: int | None = None
    companyId: int | None = None
    opportunityId: int | None = None


class ActivityUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    dueAt: datetime | None = None
    ownerId: int | None = None


# ---------- Helpers ----------
def to_dto(r, now: str | None = None) -> dict:
    now = now or now_iso()
    return {
        "id": r["id"],
        "type": r["type"],
        "title": r["title"],
        "description": r["description"],
        "status": r["status"],
        "dueAt": r["due_at"],
        "completedAt": r["completed_at"],
        "overdue": r["status"] == "PENDENTE" and r["due_at"] < now,
        "ownerId": r["owner_id"],
        "ownerName": r["owner_name"],
        "createdBy": r["created_by"],
        "leadId": r["lead_id"],
        "leadName": r["lead_name"],
        "contactId": r["contact_id"],
        "contactName": r["contact_name"],
        "companyId": r["company_id"],
        "companyName": r["company_name"],
        "opportunityId": r["opportunity_id"],
        "opportunityTitle": r["opportunity_title"],
        "createdAt": r["created_at"],
        "updatedAt": r["updated_at"],
    }


def _get(db, user, activity_id: int):
    row = db.execute(
        SELECT_SQL + " WHERE a.id = ? AND a.organization_id = ?",
        (activity_id, user["organization_id"]),
    ).fetchone()
    if row is None:
        raise AppError(404, "ACTIVITY_NOT_FOUND", "Atividade não encontrada.")
    return row


def _owner_id(owner: str | None, user) -> int | None:
    """Sem parâmetro = usuário logado; "all" = sem filtro; número = esse usuário."""
    if owner is None or owner == "":
        return user["id"]
    if owner == "all":
        return None
    try:
        return int(owner)
    except ValueError:
        raise AppError(400, "INVALID_OWNER", "Responsável inválido.")


def _where(user, *, q=None, type_=None, status=None, owner=None, overdue=False,
           lead_id=None, contact_id=None, company_id=None, opportunity_id=None,
           frm=None, until=None):
    where = ["a.organization_id = ?"]
    params: list = [user["organization_id"]]

    def add(sql, value):
        where.append(sql)
        params.append(value)

    if type_:
        add("a.type = ?", type_)
    if status:
        add("a.status = ?", status)
    if owner is not None:
        add("a.owner_id = ?", owner)
    if lead_id is not None:
        add("a.lead_id = ?", lead_id)
    if contact_id is not None:
        add("a.contact_id = ?", contact_id)
    if company_id is not None:
        add("a.company_id = ?", company_id)
    if opportunity_id is not None:
        add("a.opportunity_id = ?", opportunity_id)
    if frm is not None:
        add("a.due_at >= ?", to_utc_iso(frm))
    if until is not None:
        add("a.due_at < ?", to_utc_iso(until))
    if overdue:
        add("a.status = 'PENDENTE' AND a.due_at < ?", now_iso())
    if q and q.strip():
        like = f"%{q.strip()}%"
        where.append("(a.title LIKE ? OR a.description LIKE ?)")
        params += [like, like]
    return " WHERE " + " AND ".join(where), params


def _resolve_links(db, user, lead_id, contact_id, company_id, opportunity_id):
    """RN14: valida os vínculos e completa o que dá para deduzir (empresa pelo contato, etc.)."""
    org = user["organization_id"]
    if lead_id is not None:
        ok = db.execute("SELECT 1 FROM leads WHERE id = ? AND organization_id = ?", (lead_id, org)).fetchone()
        if ok is None:
            raise AppError(422, "LEAD_NOT_FOUND", "Lead inválido.")
    if opportunity_id is not None:
        opp = db.execute(
            "SELECT company_id, contact_id FROM opportunities WHERE id = ? AND organization_id = ?",
            (opportunity_id, org),
        ).fetchone()
        if opp is None:
            raise AppError(422, "OPPORTUNITY_NOT_FOUND", "Oportunidade inválida.")
        if company_id is None:
            company_id = opp["company_id"]
        if contact_id is None:
            contact_id = opp["contact_id"]
    if contact_id is not None:
        c = db.execute(
            "SELECT company_id FROM contacts WHERE id = ? AND organization_id = ?", (contact_id, org)
        ).fetchone()
        if c is None:
            raise AppError(422, "CONTACT_NOT_FOUND", "Contato inválido.")
        if company_id is None:
            company_id = c["company_id"]
    if company_id is not None:
        ok = db.execute("SELECT 1 FROM companies WHERE id = ? AND organization_id = ?", (company_id, org)).fetchone()
        if ok is None:
            raise AppError(422, "COMPANY_NOT_FOUND", "Empresa inválida.")
    return lead_id, contact_id, company_id, opportunity_id


def _touch_lead(db, activity_type: str, lead_id: int | None, when: str) -> None:
    if lead_id and activity_type in INTERACTION_TYPES:
        db.execute(
            "UPDATE leads SET last_interaction_at = ?, "
            "first_contact_at = COALESCE(first_contact_at, ?) "
            "WHERE id = ? AND (last_interaction_at IS NULL OR last_interaction_at < ?)",
            (when, when, lead_id, when),
        )


# ---------- Atividades ----------
@router.get("/options")
def options(db=Depends(get_db), user=Depends(get_current_user)):
    org = user["organization_id"]
    owners = db.execute(
        "SELECT id, name FROM users WHERE organization_id = ? AND active = 1 ORDER BY name", (org,)
    ).fetchall()
    leads = db.execute("SELECT id, name FROM leads WHERE organization_id = ? ORDER BY name", (org,)).fetchall()
    contacts = db.execute(
        "SELECT id, name, company_id FROM contacts WHERE organization_id = ? ORDER BY name", (org,)
    ).fetchall()
    companies = db.execute("SELECT id, name FROM companies WHERE organization_id = ? ORDER BY name", (org,)).fetchall()
    opportunities = db.execute(
        "SELECT id, title FROM opportunities WHERE organization_id = ? ORDER BY title", (org,)
    ).fetchall()
    return {
        "types": TYPES,
        "owners": [dict(o) for o in owners],
        "leads": [dict(r) for r in leads],
        "contacts": [{"id": c["id"], "name": c["name"], "companyId": c["company_id"]} for c in contacts],
        "companies": [dict(r) for r in companies],
        "opportunities": [dict(r) for r in opportunities],
    }


@router.get("/summary")
def summary(owner: str | None = None, db=Depends(get_db), user=Depends(get_current_user)):
    owner_id = _owner_id(owner, user)
    sql = (
        "SELECT "
        "COALESCE(SUM(CASE WHEN status = 'PENDENTE' THEN 1 ELSE 0 END), 0) AS pending, "
        "COALESCE(SUM(CASE WHEN status = 'PENDENTE' AND due_at < ? THEN 1 ELSE 0 END), 0) AS overdue "
        "FROM activities WHERE organization_id = ?"
    )
    params: list = [now_iso(), user["organization_id"]]
    if owner_id is not None:
        sql += " AND owner_id = ?"
        params.append(owner_id)
    r = db.execute(sql, params).fetchone()
    return {"pending": r["pending"], "overdue": r["overdue"]}


@router.get("")
def list_activities(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    type: str | None = None,
    status: str | None = None,
    owner: int | None = None,
    overdue: bool = False,
    leadId: int | None = None,
    contactId: int | None = None,
    companyId: int | None = None,
    opportunityId: int | None = None,
    sort: str = "dueAt,desc",
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    column, direction = parse_sort(sort, SORT_FIELDS)
    where_sql, params = _where(
        user, q=q, type_=type, status=status, owner=owner, overdue=overdue,
        lead_id=leadId, contact_id=contactId, company_id=companyId, opportunity_id=opportunityId,
    )
    total = db.execute("SELECT COUNT(*) FROM activities a" + where_sql, params).fetchone()[0]
    rows = db.execute(
        SELECT_SQL + where_sql + f" ORDER BY {column} {direction}, a.id DESC LIMIT ? OFFSET ?",
        params + [size, page * size],
    ).fetchall()
    now = now_iso()
    return {
        "content": [to_dto(r, now) for r in rows],
        "page": page,
        "size": size,
        "totalElements": total,
        "totalPages": ceil(total / size),
    }


@router.post("", status_code=201)
def create_activity(data: ActivityCreate, db=Depends(get_db), user=Depends(get_current_user)):
    owner_id = data.ownerId or user["id"]
    check_owner(db, user, owner_id)
    lead_id, contact_id, company_id, opportunity_id = _resolve_links(
        db, user, data.leadId, data.contactId, data.companyId, data.opportunityId
    )

    now = now_iso()
    completed = data.completed or data.type == "NOTA"
    if completed:
        when = to_utc_iso(data.dueAt) if data.dueAt else now
        if when > now:
            raise AppError(422, "FUTURE_COMPLETION", "Uma atividade realizada não pode estar no futuro.")
        status, due_at, completed_at = "CONCLUIDA", when, when
    else:
        if data.dueAt is None:
            raise AppError(422, "DUE_DATE_REQUIRED", "Informe a data e a hora da atividade agendada.")
        status, due_at, completed_at = "PENDENTE", to_utc_iso(data.dueAt), None

    cur = db.execute(
        "INSERT INTO activities(organization_id, type, title, description, status, due_at, completed_at, "
        "owner_id, created_by, lead_id, contact_id, company_id, opportunity_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user["organization_id"], data.type, data.title.strip(), data.description, status, due_at,
            completed_at, owner_id, user["id"], lead_id, contact_id, company_id, opportunity_id, now, now,
        ),
    )
    if completed_at:
        _touch_lead(db, data.type, lead_id, completed_at)
    publish(db, user, "ActivityCreated", "activity", cur.lastrowid, {"type": data.type, "title": data.title})
    db.commit()
    return to_dto(_get(db, user, cur.lastrowid))


@router.get("/{activity_id}")
def get_activity(activity_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    return to_dto(_get(db, user, activity_id))


@router.patch("/{activity_id}")
def update_activity(activity_id: int, data: ActivityUpdate, db=Depends(get_db), user=Depends(get_current_user)):
    a = _get(db, user, activity_id)
    if a["status"] != "PENDENTE":
        raise AppError(422, "ACTIVITY_NOT_PENDING", "Só atividades pendentes podem ser editadas.")

    changes = data.model_dump(exclude_unset=True)
    if "ownerId" in changes:
        check_owner(db, user, changes["ownerId"])

    sets, params = [], []
    for field, value in changes.items():
        if field in ("title", "dueAt") and value is None:
            continue
        if field == "title":
            value = value.strip()
        elif field == "dueAt":
            value = to_utc_iso(value)
        sets.append(f"{FIELD_TO_COLUMN[field]} = ?")
        params.append(value)

    if sets:
        sets.append("updated_at = ?")
        params += [now_iso(), activity_id]
        db.execute(f"UPDATE activities SET {', '.join(sets)} WHERE id = ?", params)
        publish(db, user, "ActivityUpdated", "activity", activity_id, {"fields": list(changes.keys())})
        db.commit()
    return to_dto(_get(db, user, activity_id))


@router.post("/{activity_id}/complete")
def complete_activity(activity_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    a = _get(db, user, activity_id)
    if a["status"] != "PENDENTE":
        raise AppError(422, "ACTIVITY_NOT_PENDING", "A atividade não está pendente.")
    now = now_iso()
    db.execute(
        "UPDATE activities SET status = 'CONCLUIDA', completed_at = ?, updated_at = ? WHERE id = ?",
        (now, now, activity_id),
    )
    _touch_lead(db, a["type"], a["lead_id"], now)
    publish(db, user, "ActivityCompleted", "activity", activity_id, {"type": a["type"], "title": a["title"]})
    db.commit()
    return to_dto(_get(db, user, activity_id))


@router.post("/{activity_id}/cancel")
def cancel_activity(activity_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    a = _get(db, user, activity_id)
    if a["status"] != "PENDENTE":
        raise AppError(422, "ACTIVITY_NOT_PENDING", "A atividade não está pendente.")
    db.execute(
        "UPDATE activities SET status = 'CANCELADA', updated_at = ? WHERE id = ?", (now_iso(), activity_id)
    )
    publish(db, user, "ActivityCancelled", "activity", activity_id, {"title": a["title"]})
    db.commit()
    return to_dto(_get(db, user, activity_id))


@router.delete("/{activity_id}", status_code=204)
def delete_activity(activity_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    a = _get(db, user, activity_id)
    if user["role"] not in MANAGER_ROLES and user["id"] not in (a["owner_id"], a["created_by"]):
        raise AppError(403, "FORBIDDEN", "Você não tem permissão para excluir esta atividade.")
    db.execute("DELETE FROM activities WHERE id = ?", (activity_id,))
    publish(db, user, "ActivityDeleted", "activity", activity_id, {"title": a["title"]})
    db.commit()
    return Response(status_code=204)


# ---------- Agenda ----------
@agenda_router.get("")
def agenda(
    frm: datetime = Query(..., alias="from"),
    to: datetime = Query(...),
    owner: str | None = None,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    if to <= frm or (to - frm).days > MAX_AGENDA_DAYS:
        raise AppError(400, "INVALID_RANGE", f"Período inválido (máximo de {MAX_AGENDA_DAYS} dias).")
    where_sql, params = _where(user, owner=_owner_id(owner, user), frm=frm, until=to)
    rows = db.execute(
        SELECT_SQL + where_sql + " AND a.status != 'CANCELADA' ORDER BY a.due_at LIMIT 500", params
    ).fetchall()
    now = now_iso()
    return {"content": [to_dto(r, now) for r in rows]}


# ---------- Tarefas ----------
@tasks_router.get("")
def tasks(owner: str | None = None, db=Depends(get_db), user=Depends(get_current_user)):
    where_sql, params = _where(user, status="PENDENTE", owner=_owner_id(owner, user))
    rows = db.execute(SELECT_SQL + where_sql + " ORDER BY a.due_at LIMIT 300", params).fetchall()
    now = now_iso()
    return {"content": [to_dto(r, now) for r in rows]}