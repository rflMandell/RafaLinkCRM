from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..database import get_db
from ..errors import AppError
from ..events import publish
from ..security import get_current_user, require_roles
from ..services import create_pipeline, get_pipeline, list_pipelines, list_stages, pipeline_dto
from .opportunities import SELECT_SQL, to_dto

router = APIRouter(prefix="/pipelines", tags=["Pipelines"])

CLOSED_COLUMN_LIMIT = 20  # nas colunas Ganho/Perdido mostramos só as mais recentes


class StageIn(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    probability: int = Field(ge=0, le=99)


class PipelineCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    stages: list[StageIn] = Field(min_length=2, max_length=8)


@router.get("")
def list_all(db=Depends(get_db), user=Depends(get_current_user)):
    return list_pipelines(db, user["organization_id"])


@router.post("", status_code=201)
def create(
    data: PipelineCreate,
    db=Depends(get_db),
    user=Depends(require_roles("ADMIN", "SALES_MANAGER")),
):
    org = user["organization_id"]
    exists = db.execute(
        "SELECT 1 FROM pipelines WHERE organization_id = ? AND lower(name) = lower(?)",
        (org, data.name.strip()),
    ).fetchone()
    if exists:
        raise AppError(409, "PIPELINE_NAME_EXISTS", "Já existe um pipeline com este nome.")

    names = [s.name.strip().lower() for s in data.stages]
    if len(set(names)) != len(names) or {"ganho", "perdido"} & set(names):
        raise AppError(
            422, "INVALID_STAGES",
            'As etapas não podem repetir nomes nem usar "Ganho" e "Perdido" (são criadas automaticamente).',
        )

    stages = [(s.name.strip(), s.probability, "OPEN") for s in data.stages]
    stages += [("Ganho", 100, "WON"), ("Perdido", 0, "LOST")]
    pipeline_id = create_pipeline(db, org, data.name, stages)
    publish(db, user, "PipelineCreated", "pipeline", pipeline_id, {"name": data.name})
    db.commit()
    return pipeline_dto(db, get_pipeline(db, org, pipeline_id))


@router.get("/{pipeline_id}/board")
def board(
    pipeline_id: int,
    owner: int | None = None,
    q: str | None = None,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    org = user["organization_id"]
    pipeline = get_pipeline(db, org, pipeline_id)
    if pipeline is None:
        raise AppError(404, "PIPELINE_NOT_FOUND", "Pipeline não encontrado.")

    where = ["o.organization_id = ?", "o.pipeline_id = ?"]
    params: list = [org, pipeline_id]
    if owner is not None:
        where.append("o.owner_id = ?")
        params.append(owner)
    if q and q.strip():
        like = f"%{q.strip()}%"
        where.append("(o.title LIKE ? OR co.name LIKE ?)")
        params += [like, like]

    rows = db.execute(
        SELECT_SQL + " WHERE " + " AND ".join(where) + " ORDER BY o.updated_at DESC, o.id DESC",
        params,
    ).fetchall()

    stages = list_stages(db, pipeline_id)
    by_stage = {s["id"]: [] for s in stages}
    for r in rows:
        by_stage[r["stage_id"]].append(r)

    columns = []
    open_count, open_value, weighted = 0, 0.0, 0.0
    for s in stages:
        items = by_stage[s["id"]]
        if s["kind"] == "WON":
            total = sum(r["realized_value"] if r["realized_value"] is not None else r["value"] for r in items)
        else:
            total = sum(r["value"] for r in items)
        if s["kind"] == "OPEN":
            open_count += len(items)
            open_value += total
            weighted += sum(r["value"] * r["probability"] / 100 for r in items)
        shown = items if s["kind"] == "OPEN" else items[:CLOSED_COLUMN_LIMIT]
        columns.append({
            "stage": s,
            "count": len(items),
            "totalValue": round(total, 2),
            "opportunities": [to_dto(r) for r in shown],
        })

    return {
        "pipeline": {"id": pipeline["id"], "name": pipeline["name"]},
        "columns": columns,
        "summary": {
            "openCount": open_count,
            "openValue": round(open_value, 2),
            "weightedValue": round(weighted, 2),
        },
    }