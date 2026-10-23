from datetime import date
from math import ceil

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from ..database import get_db, now_iso
from ..errors import AppError
from ..events import publish
from ..security import get_current_user, require_roles
from ..services import (
    add_history, check_owner, first_open_stage, get_default_pipeline, get_pipeline,
    list_pipelines, list_stages, parse_sort,
)

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])

STATUS_BY_KIND = {"OPEN": "ABERTA", "WON": "GANHA", "LOST": "PERDIDA"}

SORT_FIELDS = {
    "createdAt": "o.created_at",
    "value": "o.value",
    "expectedCloseDate": "o.expected_close_date",
    "title": "o.title",
    "probability": "o.probability",
}

FIELD_TO_COLUMN = {
    "title": "title", "value": "value", "companyId": "company_id", "contactId": "contact_id",
    "ownerId": "owner_id", "expectedCloseDate": "expected_close_date", "notes": "notes",
}

SELECT_SQL = (
    "SELECT o.*, p.name AS pipeline_name, s.name AS stage_name, s.kind AS stage_kind, "
    "co.name AS company_name, c.name AS contact_name, u.name AS owner_name "
    "FROM opportunities o "
    "JOIN pipelines p ON p.id = o.pipeline_id "
    "JOIN pipeline_stages s ON s.id = o.stage_id "
    "LEFT JOIN companies co ON co.id = o.company_id "
    "LEFT JOIN contacts c ON c.id = o.contact_id "
    "LEFT JOIN users u ON u.id = o.owner_id"
)


# ---------- Schemas ----------
class OpportunityCreate(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    value: float = Field(default=0, ge=0, le=1_000_000_000)
    pipelineId: int | None = None
    stageId: int | None = None
    companyId: int | None = None
    contactId: int | None = None
    ownerId: int | None = None
    expectedCloseDate: date | None = None
    notes: str | None = Field(default=None, max_length=1000)


class OpportunityUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    value: float | None = Field(default=None, ge=0, le=1_000_000_000)
    companyId: int | None = None
    contactId: int | None = None
    ownerId: int | None = None
    expectedCloseDate: date | None = None
    notes: str | None = Field(default=None, max_length=1000)


class MoveRequest(BaseModel):
    stageId: int
    reason: str | None = Field(default=None, max_length=200)
    realizedValue: float | None = Field(default=None, ge=0, le=1_000_000_000)


# ---------- Helpers ----------
def to_dto(r) -> dict:
    return {
        "id": r["id"],
        "title": r["title"],
        "value": r["value"],
        "probability": r["probability"],
        "weightedValue": round(r["value"] * r["probability"] / 100, 2),
        "status": r["status"],
        "realizedValue": r["realized_value"],
        "pipelineId": r["pipeline_id"],
        "pipelineName": r["pipeline_name"],
        "stageId": r["stage_id"],
        "stageName": r["stage_name"],
        "stageKind": r["stage_kind"],
        "companyId": r["company_id"],
        "companyName": r["company_name"],
        "contactId": r["contact_id"],
        "contactName": r["contact_name"],
        "ownerId": r["owner_id"],
        "ownerName": r["owner_name"],
        "expectedCloseDate": r["expected_close_date"],
        "lostReason": r["lost_reason"],
        "notes": r["notes"],
        "leadId": r["lead_id"],
        "closedAt": r["closed_at"],
        "stageChangedAt": r["stage_changed_at"],
        "createdAt": r["created_at"],
        "updatedAt": r["updated_at"],
    }


def _get(db, user, opp_id: int):
    row = db.execute(
        SELECT_SQL + " WHERE o.id = ? AND o.organization_id = ?",
        (opp_id, user["organization_id"]),
    ).fetchone()
    if row is None:
        raise AppError(404, "OPPORTUNITY_NOT_FOUND", "Oportunidade não encontrada.")
    return row


def _get_stage(db, org_id: int, stage_id: int):
    return db.execute(
        "SELECT s.* FROM pipeline_stages s JOIN pipelines p ON p.id = s.pipeline_id "
        "WHERE s.id = ? AND p.organization_id = ?",
        (stage_id, org_id),
    ).fetchone()


def _detail(db, user, opp_id: int) -> dict:
    opp = _get(db, user, opp_id)
    dto = to_dto(opp)
    dto["stages"] = list_stages(db, opp["pipeline_id"])
    history = db.execute(
        "SELECT h.*, u.name AS user_name FROM opportunity_history h "
        "LEFT JOIN users u ON u.id = h.user_id WHERE h.opportunity_id = ? "
        "ORDER BY h.created_at DESC, h.id DESC",
        (opp_id,),
    ).fetchall()
    dto["history"] = [
        {
            "id": h["id"], "fromStage": h["from_stage"], "toStage": h["to_stage"],
            "probability": h["probability"], "note": h["note"],
            "userName": h["user_name"], "createdAt": h["created_at"],
        }
        for h in history
    ]
    return dto


def _resolve_links(db, user, company_id: int | None, contact_id: int | None):
    """RN16: o contato precisa pertencer à empresa escolhida."""
    org = user["organization_id"]
    if company_id is not None:
        ok = db.execute(
            "SELECT 1 FROM companies WHERE id = ? AND organization_id = ?", (company_id, org)
        ).fetchone()
        if ok is None:
            raise AppError(422, "COMPANY_NOT_FOUND", "Empresa inválida.")
    if contact_id is not None:
        c = db.execute(
            "SELECT company_id FROM contacts WHERE id = ? AND organization_id = ?", (contact_id, org)
        ).fetchone()
        if c is None:
            raise AppError(422, "CONTACT_NOT_FOUND", "Contato inválido.")
        if company_id is None:
            company_id = c["company_id"]
        elif c["company_id"] is not None and c["company_id"] != company_id:
            raise AppError(422, "CONTACT_COMPANY_MISMATCH", "O contato pertence a outra empresa.")
    return company_id, contact_id


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
    contacts = db.execute(
        "SELECT id, name, company_id FROM contacts WHERE organization_id = ? AND status = 'ATIVO' ORDER BY name",
        (org,),
    ).fetchall()
    return {
        "pipelines": list_pipelines(db, org),
        "owners": [dict(o) for o in owners],
        "companies": [dict(c) for c in companies],
        "contacts": [{"id": c["id"], "name": c["name"], "companyId": c["company_id"]} for c in contacts],
    }


@router.get("/summary")
def summary(db=Depends(get_db), user=Depends(get_current_user)):
    r = db.execute(
        "SELECT "
        "COALESCE(SUM(CASE WHEN status = 'ABERTA' THEN 1 ELSE 0 END), 0) AS open_count, "
        "COALESCE(SUM(CASE WHEN status = 'ABERTA' THEN value ELSE 0 END), 0) AS open_value, "
        "COALESCE(SUM(CASE WHEN status = 'ABERTA' THEN value * probability / 100.0 ELSE 0 END), 0) AS weighted, "
        "COALESCE(SUM(CASE WHEN status = 'GANHA' THEN 1 ELSE 0 END), 0) AS won_count, "
        "COALESCE(SUM(CASE WHEN status = 'GANHA' THEN COALESCE(realized_value, value) ELSE 0 END), 0) AS won_value, "
        "COALESCE(SUM(CASE WHEN status = 'PERDIDA' THEN 1 ELSE 0 END), 0) AS lost_count "
        "FROM opportunities WHERE organization_id = ?",
        (user["organization_id"],),
    ).fetchone()
    return {
        "openCount": r["open_count"],
        "openValue": round(r["open_value"], 2),
        "weightedValue": round(r["weighted"], 2),
        "wonCount": r["won_count"],
        "wonValue": round(r["won_value"], 2),
        "lostCount": r["lost_count"],
    }


@router.get("")
def list_opportunities(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    pipelineId: int | None = None,
    stageId: int | None = None,
    status: str | None = None,
    owner: int | None = None,
    companyId: int | None = None,
    q: str | None = None,
    sort: str = "createdAt,desc",
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    column, direction = parse_sort(sort, SORT_FIELDS)

    where = ["o.organization_id = ?"]
    params: list = [user["organization_id"]]
    for sql, value in (
        ("o.pipeline_id = ?", pipelineId), ("o.stage_id = ?", stageId), ("o.status = ?", status),
        ("o.owner_id = ?", owner), ("o.company_id = ?", companyId),
    ):
        if value is not None and value != "":
            where.append(sql)
            params.append(value)
    if q and q.strip():
        like = f"%{q.strip()}%"
        where.append("(o.title LIKE ? OR co.name LIKE ?)")
        params += [like, like]

    where_sql = " WHERE " + " AND ".join(where)
    total = db.execute(
        "SELECT COUNT(*) FROM opportunities o LEFT JOIN companies co ON co.id = o.company_id" + where_sql,
        params,
    ).fetchone()[0]
    rows = db.execute(
        SELECT_SQL + where_sql + f" ORDER BY {column} {direction}, o.id DESC LIMIT ? OFFSET ?",
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
def create_opportunity(data: OpportunityCreate, db=Depends(get_db), user=Depends(get_current_user)):
    org = user["organization_id"]
    owner_id = data.ownerId or user["id"]
    check_owner(db, user, owner_id)
    company_id, contact_id = _resolve_links(db, user, data.companyId, data.contactId)

    if data.stageId is not None:
        stage = _get_stage(db, org, data.stageId)
        if stage is None:
            raise AppError(422, "STAGE_NOT_FOUND", "Etapa inválida.")
        if data.pipelineId is not None and stage["pipeline_id"] != data.pipelineId:
            raise AppError(422, "STAGE_NOT_IN_PIPELINE", "A etapa não pertence ao pipeline informado.")
    else:
        pipeline = (
            get_pipeline(db, org, data.pipelineId)
            if data.pipelineId is not None
            else get_default_pipeline(db, org)
        )
        if pipeline is None:
            raise AppError(422, "PIPELINE_NOT_FOUND", "Pipeline inválido ou não configurado.")
        stage = first_open_stage(db, pipeline["id"])
    if stage["kind"] != "OPEN":
        raise AppError(422, "INVALID_STAGE", "Uma nova oportunidade deve começar em uma etapa aberta.")

    now = now_iso()
    cur = db.execute(
        "INSERT INTO opportunities(organization_id, title, value, probability, status, pipeline_id, "
        "stage_id, company_id, contact_id, owner_id, expected_close_date, notes, "
        "stage_changed_at, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'ABERTA', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            org, data.title.strip(), data.value, stage["probability"], stage["pipeline_id"],
            stage["id"], company_id, contact_id, owner_id,
            data.expectedCloseDate.isoformat() if data.expectedCloseDate else None,
            data.notes, now, now, now,
        ),
    )
    opp_id = cur.lastrowid
    add_history(db, user, opp_id, None, stage["name"], stage["probability"], "Oportunidade criada")
    publish(db, user, "OpportunityCreated", "opportunity", opp_id,
            {"title": data.title, "value": data.value})
    db.commit()
    return _detail(db, user, opp_id)


@router.get("/{opp_id}")
def get_opportunity(opp_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    return _detail(db, user, opp_id)


@router.patch("/{opp_id}")
def update_opportunity(opp_id: int, data: OpportunityUpdate, db=Depends(get_db), user=Depends(get_current_user)):
    opp = _get(db, user, opp_id)
    if opp["status"] != "ABERTA":
        raise AppError(422, "OPPORTUNITY_CLOSED", "Oportunidade encerrada não pode ser editada. Reabra para editar.")

    changes = data.model_dump(exclude_unset=True)
    if "ownerId" in changes:
        check_owner(db, user, changes["ownerId"])
    if "companyId" in changes or "contactId" in changes:
        company_id, contact_id = _resolve_links(
            db, user,
            changes.get("companyId", opp["company_id"]),
            changes.get("contactId", opp["contact_id"]),
        )
        changes["companyId"], changes["contactId"] = company_id, contact_id

    sets, params = [], []
    for field, value in changes.items():
        if field in ("title", "value") and value is None:
            continue
        if isinstance(value, date):
            value = value.isoformat()
        sets.append(f"{FIELD_TO_COLUMN[field]} = ?")
        params.append(value.strip() if field == "title" else value)

    if sets:
        sets.append("updated_at = ?")
        params += [now_iso(), opp_id]
        db.execute(f"UPDATE opportunities SET {', '.join(sets)} WHERE id = ?", params)
        publish(db, user, "OpportunityUpdated", "opportunity", opp_id, {"fields": list(changes.keys())})
        db.commit()
    return _detail(db, user, opp_id)


@router.post("/{opp_id}/move")
def move_opportunity(opp_id: int, data: MoveRequest, db=Depends(get_db), user=Depends(get_current_user)):
    opp = _get(db, user, opp_id)
    if opp["status"] != "ABERTA":
        raise AppError(422, "OPPORTUNITY_CLOSED", "Oportunidade encerrada. Reabra para movê-la.")

    stage = _get_stage(db, user["organization_id"], data.stageId)
    if stage is None or stage["pipeline_id"] != opp["pipeline_id"]:  # RN16
        raise AppError(422, "STAGE_NOT_IN_PIPELINE", "A etapa não pertence ao pipeline da oportunidade.")
    if stage["id"] == opp["stage_id"]:
        raise AppError(422, "SAME_STAGE", "A oportunidade já está nesta etapa.")

    now = now_iso()
    kind = stage["kind"]
    realized = lost_reason = closed_at = None
    note = None
    if kind == "WON":
        realized = data.realizedValue if data.realizedValue is not None else opp["value"]  # RN09
        closed_at = now
        note = f"Valor realizado: {realized:.2f}"
    elif kind == "LOST":
        lost_reason = data.reason
        closed_at = now
        note = data.reason

    db.execute(
        "UPDATE opportunities SET stage_id = ?, probability = ?, status = ?, realized_value = ?, "
        "lost_reason = ?, closed_at = ?, stage_changed_at = ?, updated_at = ? WHERE id = ?",
        (stage["id"], stage["probability"], STATUS_BY_KIND[kind], realized, lost_reason,
         closed_at, now, now, opp_id),
    )
    add_history(db, user, opp_id, opp["stage_name"], stage["name"], stage["probability"], note)

    payload = {
        "from": opp["stage_name"], "to": stage["name"],
        "fromProbability": opp["probability"], "toProbability": stage["probability"],
    }
    publish(db, user, "OpportunityStageChanged", "opportunity", opp_id, payload)
    if kind == "WON":
        publish(db, user, "OpportunityWon", "opportunity", opp_id, {"realizedValue": realized})
        if opp["company_id"]:  # empresa que comprou vira cliente
            promoted = db.execute(
                "UPDATE companies SET type = 'CLIENTE', updated_at = ? WHERE id = ? AND type != 'CLIENTE'",
                (now, opp["company_id"]),
            )
            if promoted.rowcount:
                publish(db, user, "CompanyUpdated", "company", opp["company_id"], {"fields": ["type"]})
    elif kind == "LOST":
        publish(db, user, "OpportunityLost", "opportunity", opp_id, {"reason": data.reason})

    db.commit()
    return _detail(db, user, opp_id)


@router.post("/{opp_id}/reopen")
def reopen_opportunity(opp_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    opp = _get(db, user, opp_id)
    if opp["status"] == "ABERTA":
        raise AppError(422, "OPPORTUNITY_NOT_CLOSED", "A oportunidade já está aberta.")
    stage = first_open_stage(db, opp["pipeline_id"])
    now = now_iso()
    db.execute(
        "UPDATE opportunities SET stage_id = ?, probability = ?, status = 'ABERTA', realized_value = NULL, "
        "lost_reason = NULL, closed_at = NULL, stage_changed_at = ?, updated_at = ? WHERE id = ?",
        (stage["id"], stage["probability"], now, now, opp_id),
    )
    add_history(db, user, opp_id, opp["stage_name"], stage["name"], stage["probability"], "Oportunidade reaberta")
    publish(db, user, "OpportunityReopened", "opportunity", opp_id, {"to": stage["name"]})
    db.commit()
    return _detail(db, user, opp_id)


@router.delete("/{opp_id}", status_code=204)
def delete_opportunity(
    opp_id: int,
    db=Depends(get_db),
    user=Depends(require_roles("ADMIN", "SALES_MANAGER")),
):
    opp = _get(db, user, opp_id)
    db.execute("UPDATE leads SET opportunity_id = NULL WHERE opportunity_id = ?", (opp_id,))
    db.execute("DELETE FROM opportunity_history WHERE opportunity_id = ?", (opp_id,))
    db.execute("DELETE FROM opportunities WHERE id = ?", (opp_id,))
    publish(db, user, "OpportunityDeleted", "opportunity", opp_id, {"title": opp["title"]})
    db.commit()
    return Response(status_code=204)