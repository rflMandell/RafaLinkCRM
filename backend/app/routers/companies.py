from math import ceil
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from ..database import get_db, now_iso
from ..errors import AppError
from ..events import publish
from ..security import get_current_user, require_roles
from ..services import check_owner, parse_sort

router = APIRouter(prefix="/companies", tags=["Companies"])

CompanyType = Literal["PROSPECT", "CLIENTE"]
TYPES = list(CompanyType.__args__)

SORT_FIELDS = {
    "name": "co.name",
    "createdAt": "co.created_at",
    "city": "co.city",
    "contacts": "contact_count",
}

FIELD_TO_COLUMN = {
    "name": "name", "industry": "industry", "website": "website", "phone": "phone",
    "city": "city", "notes": "notes", "type": "type", "ownerId": "owner_id",
}

SELECT_SQL = (
    "SELECT co.*, u.name AS owner_name, "
    "(SELECT COUNT(*) FROM contacts c WHERE c.company_id = co.id) AS contact_count "
    "FROM companies co LEFT JOIN users u ON u.id = co.owner_id"
)


# ---------- Schemas ----------
class CompanyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    industry: str | None = Field(default=None, max_length=80)
    website: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=30)
    city: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=1000)
    type: CompanyType = "PROSPECT"
    ownerId: int | None = None


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    industry: str | None = Field(default=None, max_length=80)
    website: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=30)
    city: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=1000)
    type: CompanyType | None = None
    ownerId: int | None = None


# ---------- Helpers ----------
def to_dto(r) -> dict:
    return {
        "id": r["id"],
        "name": r["name"],
        "industry": r["industry"],
        "website": r["website"],
        "phone": r["phone"],
        "city": r["city"],
        "notes": r["notes"],
        "type": r["type"],
        "ownerId": r["owner_id"],
        "ownerName": r["owner_name"],
        "contactCount": r["contact_count"],
        "createdAt": r["created_at"],
        "updatedAt": r["updated_at"],
    }


def _get_company(db, user, company_id: int):
    row = db.execute(
        SELECT_SQL + " WHERE co.id = ? AND co.organization_id = ?",
        (company_id, user["organization_id"]),
    ).fetchone()
    if row is None:
        raise AppError(404, "COMPANY_NOT_FOUND", "Empresa não encontrada.")
    return row


def _detail(db, user, company_id: int) -> dict:
    """Empresa + contatos + oportunidades (as oportunidades chegam na Etapa 4)."""
    dto = to_dto(_get_company(db, user, company_id))
    contacts = db.execute(
        "SELECT id, name, job_title, email, phone, status FROM contacts "
        "WHERE company_id = ? ORDER BY name",
        (company_id,),
    ).fetchall()
    dto["contacts"] = [
        {
            "id": c["id"], "name": c["name"], "jobTitle": c["job_title"],
            "email": c["email"], "phone": c["phone"], "status": c["status"],
        }
        for c in contacts
    ]
    opps = db.execute(
        "SELECT o.id, o.title, o.value, o.probability, o.status, s.name AS stage_name "
        "FROM opportunities o JOIN pipeline_stages s ON s.id = o.stage_id "
        "WHERE o.company_id = ? ORDER BY o.created_at DESC",
        (company_id,),
    ).fetchall()
    dto["opportunities"] = [
        {
            "id": o["id"], "title": o["title"], "value": o["value"],
            "probability": o["probability"], "status": o["status"], "stageName": o["stage_name"],
        }
        for o in opps
    ]
    return dto


def _ensure_unique_name(db, user, name: str, exclude_id: int | None = None) -> None:
    row = db.execute(
        "SELECT id FROM companies WHERE organization_id = ? AND lower(name) = lower(?)",
        (user["organization_id"], name.strip()),
    ).fetchone()
    if row and row["id"] != exclude_id:
        raise AppError(409, "COMPANY_NAME_EXISTS", "Já existe uma empresa com este nome.")


# ---------- Endpoints ----------
@router.get("/options")
def options(db=Depends(get_db), user=Depends(get_current_user)):
    owners = db.execute(
        "SELECT id, name FROM users WHERE organization_id = ? AND active = 1 ORDER BY name",
        (user["organization_id"],),
    ).fetchall()
    return {"types": TYPES, "owners": [dict(o) for o in owners]}


@router.get("")
def list_companies(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    type: str | None = None,
    owner: int | None = None,
    sort: str = "name,asc",
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    column, direction = parse_sort(sort, SORT_FIELDS)

    where = ["co.organization_id = ?"]
    params: list = [user["organization_id"]]
    if q and q.strip():
        like = f"%{q.strip()}%"
        where.append("(co.name LIKE ? OR co.industry LIKE ? OR co.city LIKE ?)")
        params += [like, like, like]
    if type:
        where.append("co.type = ?")
        params.append(type)
    if owner is not None:
        where.append("co.owner_id = ?")
        params.append(owner)

    where_sql = " WHERE " + " AND ".join(where)
    total = db.execute("SELECT COUNT(*) FROM companies co" + where_sql, params).fetchone()[0]
    rows = db.execute(
        SELECT_SQL + where_sql + f" ORDER BY {column} {direction}, co.id DESC LIMIT ? OFFSET ?",
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
def create_company(data: CompanyCreate, db=Depends(get_db), user=Depends(get_current_user)):
    owner_id = data.ownerId or user["id"]
    check_owner(db, user, owner_id)
    _ensure_unique_name(db, user, data.name)
    now = now_iso()
    cur = db.execute(
        "INSERT INTO companies(organization_id, name, industry, website, phone, city, notes, "
        "type, owner_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user["organization_id"], data.name.strip(), data.industry, data.website, data.phone,
            data.city, data.notes, data.type, owner_id, now, now,
        ),
    )
    publish(db, user, "CompanyCreated", "company", cur.lastrowid, {"name": data.name})
    db.commit()
    return _detail(db, user, cur.lastrowid)


@router.get("/{company_id}")
def get_company(company_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    return _detail(db, user, company_id)


@router.patch("/{company_id}")
def update_company(company_id: int, data: CompanyUpdate, db=Depends(get_db), user=Depends(get_current_user)):
    _get_company(db, user, company_id)
    changes = data.model_dump(exclude_unset=True)
    if "ownerId" in changes:
        check_owner(db, user, changes["ownerId"])
    if changes.get("name"):
        _ensure_unique_name(db, user, changes["name"], exclude_id=company_id)

    sets, params = [], []
    for field, value in changes.items():
        if field in ("name", "type") and value is None:
            continue
        sets.append(f"{FIELD_TO_COLUMN[field]} = ?")
        params.append(value.strip() if field == "name" else value)

    if sets:
        sets.append("updated_at = ?")
        params += [now_iso(), company_id]
        db.execute(f"UPDATE companies SET {', '.join(sets)} WHERE id = ?", params)
        publish(db, user, "CompanyUpdated", "company", company_id, {"fields": list(changes.keys())})
        db.commit()
    return _detail(db, user, company_id)


@router.delete("/{company_id}", status_code=204)
def delete_company(
    company_id: int,
    db=Depends(get_db),
    user=Depends(require_roles("ADMIN", "SALES_MANAGER")),
):
    company = _get_company(db, user, company_id)
    if company["contact_count"] > 0:
        raise AppError(
            409, "COMPANY_HAS_CONTACTS",
            f"A empresa possui {company['contact_count']} contato(s). Exclua ou mova os contatos antes.",
        )
        
    opp_count = db.execute(
        "SELECT COUNT(*) FROM opportunities WHERE company_id = ?", (company_id,)
    ).fetchone()[0]
    if opp_count > 0:
        raise AppError(
            409, "COMPANY_HAS_OPPORTUNITIES",
            f"A empresa possui {opp_count} oportunidade(s). Exclua as oportunidades antes.",
        )

    db.execute("UPDATE leads SET company_id = NULL WHERE company_id = ?", (company_id,))
    db.execute("DELETE FROM companies WHERE id = ?", (company_id,))
    publish(db, user, "CompanyDeleted", "company", company_id, {"name": company["name"]})
    db.commit()
    return Response(status_code=204)