from math import ceil
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from ..database import get_db, now_iso
from ..errors import AppError
from ..events import publish
from ..security import get_current_user, require_roles
from ..services import EMAIL_PATTERN, check_owner, parse_sort

router = APIRouter(prefix="/contacts", tags=["Contacts"])

ContactStatus = Literal["ATIVO", "INATIVO"]
Preference = Literal["EMAIL", "WHATSAPP", "TELEFONE", "NENHUMA"]
STATUSES = list(ContactStatus.__args__)
PREFERENCES = list(Preference.__args__)

SORT_FIELDS = {"name": "c.name", "createdAt": "c.created_at", "company": "co.name"}

FIELD_TO_COLUMN = {
    "name": "name", "jobTitle": "job_title", "email": "email", "phone": "phone",
    "companyId": "company_id", "ownerId": "owner_id", "status": "status",
    "contactPreference": "contact_preference",
}

SELECT_SQL = (
    "SELECT c.*, u.name AS owner_name, co.name AS company_name, l.name AS source_lead_name "
    "FROM contacts c "
    "LEFT JOIN users u ON u.id = c.owner_id "
    "LEFT JOIN companies co ON co.id = c.company_id "
    "LEFT JOIN leads l ON l.id = c.source_lead_id"
)


# ---------- Schemas ----------
class ContactCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    jobTitle: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, pattern=EMAIL_PATTERN, max_length=160)
    phone: str | None = Field(default=None, max_length=30)
    companyId: int | None = None
    ownerId: int | None = None
    status: ContactStatus = "ATIVO"
    contactPreference: Preference | None = None


class ContactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    jobTitle: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, pattern=EMAIL_PATTERN, max_length=160)
    phone: str | None = Field(default=None, max_length=30)
    companyId: int | None = None
    ownerId: int | None = None
    status: ContactStatus | None = None
    contactPreference: Preference | None = None


# ---------- Helpers ----------
def to_dto(r) -> dict:
    return {
        "id": r["id"],
        "name": r["name"],
        "jobTitle": r["job_title"],
        "email": r["email"],
        "phone": r["phone"],
        "companyId": r["company_id"],
        "companyName": r["company_name"],
        "ownerId": r["owner_id"],
        "ownerName": r["owner_name"],
        "status": r["status"],
        "contactPreference": r["contact_preference"],
        "sourceLeadId": r["source_lead_id"],
        "sourceLeadName": r["source_lead_name"],
        "createdAt": r["created_at"],
        "updatedAt": r["updated_at"],
    }


def _get_contact(db, user, contact_id: int):
    row = db.execute(
        SELECT_SQL + " WHERE c.id = ? AND c.organization_id = ?",
        (contact_id, user["organization_id"]),
    ).fetchone()
    if row is None:
        raise AppError(404, "CONTACT_NOT_FOUND", "Contato não encontrado.")
    return row


def _check_company(db, user, company_id: int | None) -> None:
    if company_id is None:
        return
    ok = db.execute(
        "SELECT 1 FROM companies WHERE id = ? AND organization_id = ?",
        (company_id, user["organization_id"]),
    ).fetchone()
    if ok is None:
        raise AppError(422, "COMPANY_NOT_FOUND", "Empresa inválida.")


# ---------- Endpoints ----------
@router.get("/options")
def options(db=Depends(get_db), user=Depends(get_current_user)):
    org = user["organization_id"]
    owners = db.execute(
        "SELECT id, name FROM users WHERE organization_id = ? AND active = 1 ORDER BY name", (org,)
    ).fetchall()
    companies = db.execute(
        "SELECT id, name FROM companies WHERE organization_id = ? ORDER BY name", (org,)
    ).fetchall()
    return {
        "statuses": STATUSES,
        "preferences": PREFERENCES,
        "owners": [dict(o) for o in owners],
        "companies": [dict(c) for c in companies],
    }


@router.get("")
def list_contacts(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    companyId: int | None = None,
    status: str | None = None,
    owner: int | None = None,
    sort: str = "name,asc",
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    column, direction = parse_sort(sort, SORT_FIELDS)

    where = ["c.organization_id = ?"]
    params: list = [user["organization_id"]]
    if q and q.strip():
        like = f"%{q.strip()}%"
        where.append("(c.name LIKE ? OR c.email LIKE ? OR c.job_title LIKE ? OR co.name LIKE ?)")
        params += [like, like, like, like]
    if companyId is not None:
        where.append("c.company_id = ?")
        params.append(companyId)
    if status:
        where.append("c.status = ?")
        params.append(status)
    if owner is not None:
        where.append("c.owner_id = ?")
        params.append(owner)

    where_sql = " WHERE " + " AND ".join(where)
    total = db.execute(
        "SELECT COUNT(*) FROM contacts c LEFT JOIN companies co ON co.id = c.company_id" + where_sql,
        params,
    ).fetchone()[0]
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
def create_contact(data: ContactCreate, db=Depends(get_db), user=Depends(get_current_user)):
    owner_id = data.ownerId or user["id"]
    check_owner(db, user, owner_id)
    _check_company(db, user, data.companyId)
    now = now_iso()
    cur = db.execute(
        "INSERT INTO contacts(organization_id, company_id, name, job_title, email, phone, "
        "owner_id, status, contact_preference, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user["organization_id"], data.companyId, data.name.strip(), data.jobTitle, data.email,
            data.phone, owner_id, data.status, data.contactPreference, now, now,
        ),
    )
    publish(db, user, "ContactCreated", "contact", cur.lastrowid, {"name": data.name})
    db.commit()
    return to_dto(_get_contact(db, user, cur.lastrowid))


@router.get("/{contact_id}")
def get_contact(contact_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    return to_dto(_get_contact(db, user, contact_id))


@router.patch("/{contact_id}")
def update_contact(contact_id: int, data: ContactUpdate, db=Depends(get_db), user=Depends(get_current_user)):
    _get_contact(db, user, contact_id)
    changes = data.model_dump(exclude_unset=True)
    if "ownerId" in changes:
        check_owner(db, user, changes["ownerId"])
    if "companyId" in changes:
        _check_company(db, user, changes["companyId"])

    sets, params = [], []
    for field, value in changes.items():
        if field in ("name", "status") and value is None:
            continue
        sets.append(f"{FIELD_TO_COLUMN[field]} = ?")
        params.append(value.strip() if field == "name" else value)

    if sets:
        sets.append("updated_at = ?")
        params += [now_iso(), contact_id]
        db.execute(f"UPDATE contacts SET {', '.join(sets)} WHERE id = ?", params)
        publish(db, user, "ContactUpdated", "contact", contact_id, {"fields": list(changes.keys())})
        db.commit()
    return to_dto(_get_contact(db, user, contact_id))


@router.delete("/{contact_id}", status_code=204)
def delete_contact(
    contact_id: int,
    db=Depends(get_db),
    user=Depends(require_roles("ADMIN", "SALES_MANAGER")),
):
    contact = _get_contact(db, user, contact_id)
    db.execute("UPDATE opportunities SET contact_id = NULL WHERE contact_id = ?", (contact_id,))
    db.execute("UPDATE leads SET contact_id = NULL WHERE contact_id = ?", (contact_id,))
    db.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    publish(db, user, "ContactDeleted", "contact", contact_id, {"name": contact["name"]})
    db.commit()
    return Response(status_code=204)