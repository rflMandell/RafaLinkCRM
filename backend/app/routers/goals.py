from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from ..database import get_db, now_iso
from ..errors import AppError
from ..events import publish
from ..security import get_current_user, require_roles
from ..services import check_owner

router = APIRouter(prefix="/goals", tags=["Goals"])

Metric = Literal["REVENUE", "WON_COUNT", "NEW_LEADS"]
PeriodType = Literal["MONTH", "QUARTER"]
METRIC_LABEL = {"REVENUE": "Receita ganha", "WON_COUNT": "Vendas ganhas", "NEW_LEADS": "Novos leads"}
METRIC_ORDER = list(METRIC_LABEL)
MANAGERS = ("ADMIN", "SALES_MANAGER")


# ---------- Períodos ----------
def period_bounds(period_type: str, d: date) -> tuple[date, date]:
    """Primeiro dia do período e primeiro dia do período seguinte (fim exclusivo)."""
    if period_type == "MONTH":
        start = date(d.year, d.month, 1)
        months = 1
    else:
        start = date(d.year, ((d.month - 1) // 3) * 3 + 1, 1)
        months = 3
    idx = start.year * 12 + (start.month - 1) + months
    return start, date(idx // 12, idx % 12 + 1, 1)


def _utc(d: date) -> str:
    return datetime.combine(d, time.min, tzinfo=timezone.utc).isoformat(timespec="seconds")


# ---------- Progresso ----------
def compute_progress(db, org: int, goal, now: datetime) -> dict:
    start, end = period_bounds(goal["period_type"], date.fromisoformat(goal["period_start"]))
    s, e = _utc(start), _utc(end)
    owner = goal["owner_id"]
    own_opp = " AND owner_id = ?" if owner else ""
    own_args = [owner] if owner else []

    metric = goal["metric"]
    if metric == "REVENUE":
        actual = db.execute(
            "SELECT COALESCE(SUM(COALESCE(realized_value, value)), 0) FROM opportunities "
            "WHERE organization_id = ? AND status = 'GANHA' AND closed_at >= ? AND closed_at < ?" + own_opp,
            [org, s, e] + own_args,
        ).fetchone()[0]
    elif metric == "WON_COUNT":
        actual = db.execute(
            "SELECT COUNT(*) FROM opportunities "
            "WHERE organization_id = ? AND status = 'GANHA' AND closed_at >= ? AND closed_at < ?" + own_opp,
            [org, s, e] + own_args,
        ).fetchone()[0]
    else:
        actual = db.execute(
            "SELECT COUNT(*) FROM leads WHERE organization_id = ? AND created_at >= ? AND created_at < ?" + own_opp,
            [org, s, e] + own_args,
        ).fetchone()[0]

    projected = None
    if metric == "REVENUE":  # ganho + o que as oportunidades abertas devem render no período
        pipeline = db.execute(
            "SELECT COALESCE(SUM(value * probability / 100.0), 0) FROM opportunities "
            "WHERE organization_id = ? AND status = 'ABERTA' AND expected_close_date >= ? "
            "AND expected_close_date < ?" + own_opp,
            [org, start.isoformat(), end.isoformat()] + own_args,
        ).fetchone()[0]
        projected = round(actual + pipeline, 2)

    target = goal["target"]
    total_s = (end - start).total_seconds()
    start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
    elapsed = min(max((now - start_dt).total_seconds() / total_s, 0), 1)
    expected = target * elapsed

    if actual >= target:
        status = "ATINGIDA"
    elif now < start_dt:
        status = "NAO_INICIADA"
    elif elapsed >= 1:
        status = "NAO_ATINGIDA"
    else:
        pace = actual / expected if expected > 0 else 1
        status = "NO_RITMO" if pace >= 0.9 else "EM_RISCO" if pace >= 0.6 else "ATRASADA"

    return {
        "actual": round(actual, 2),
        "attainment": round(actual / target * 100, 1) if target else 0,
        "expected": round(expected, 2),
        "elapsed": round(elapsed * 100, 1),
        "status": status,
        "projected": projected,
        "projectedAttainment": round(projected / target * 100, 1) if projected is not None and target else None,
    }


def to_dto(db, org: int, g, now: datetime) -> dict:
    return {
        "id": g["id"],
        "ownerId": g["owner_id"],
        "ownerName": g["owner_name"],
        "metric": g["metric"],
        "metricLabel": METRIC_LABEL[g["metric"]],
        "periodType": g["period_type"],
        "periodStart": g["period_start"],
        "target": g["target"],
        **compute_progress(db, org, g, now),
    }


SELECT_SQL = (
    "SELECT g.*, u.name AS owner_name FROM goals g LEFT JOIN users u ON u.id = g.owner_id"
)


def _get(db, user, goal_id: int):
    row = db.execute(
        SELECT_SQL + " WHERE g.id = ? AND g.organization_id = ?", (goal_id, user["organization_id"])
    ).fetchone()
    if row is None:
        raise AppError(404, "GOAL_NOT_FOUND", "Meta não encontrada.")
    return row


# ---------- Schemas ----------
class GoalCreate(BaseModel):
    ownerId: int | None = None          # None = meta da equipe
    metric: Metric
    periodType: PeriodType = "MONTH"
    periodStart: date                   # qualquer dia do período; vira o 1º dia
    target: float = Field(gt=0, le=1_000_000_000)


class GoalUpdate(BaseModel):
    target: float = Field(gt=0, le=1_000_000_000)


# ---------- Endpoints ----------
@router.get("/options")
def options(db=Depends(get_db), user=Depends(get_current_user)):
    owners = db.execute(
        "SELECT id, name FROM users WHERE organization_id = ? AND active = 1 ORDER BY name",
        (user["organization_id"],),
    ).fetchall()
    return {
        "metrics": [{"value": k, "label": v} for k, v in METRIC_LABEL.items()],
        "owners": [dict(o) for o in owners],
        "canManage": user["role"] in MANAGERS,
    }


@router.get("")
def list_goals(
    periodType: PeriodType = "MONTH",
    periodStart: date | None = None,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    org = user["organization_id"]
    now = datetime.now(timezone.utc)
    start, end = period_bounds(periodType, periodStart or now.date())

    where = "g.organization_id = ? AND g.period_type = ? AND g.period_start = ?"
    params: list = [org, periodType, start.isoformat()]
    if user["role"] not in MANAGERS:  # vendedor vê a meta da equipe e as próprias
        where += " AND (g.owner_id IS NULL OR g.owner_id = ?)"
        params.append(user["id"])

    rows = db.execute(SELECT_SQL + " WHERE " + where, params).fetchall()
    goals = [to_dto(db, org, g, now) for g in rows]
    goals.sort(key=lambda g: (g["ownerId"] is not None, g["ownerName"] or "", METRIC_ORDER.index(g["metric"])))

    return {
        "periodType": periodType,
        "periodStart": start.isoformat(),
        "periodEnd": (end - timedelta(days=1)).isoformat(),
        "goals": goals,
        "canManage": user["role"] in MANAGERS,
    }


@router.post("", status_code=201)
def create_goal(data: GoalCreate, db=Depends(get_db), user=Depends(require_roles(*MANAGERS))):
    org = user["organization_id"]
    check_owner(db, user, data.ownerId)
    start, _ = period_bounds(data.periodType, data.periodStart)

    exists = db.execute(
        "SELECT 1 FROM goals WHERE organization_id = ? AND COALESCE(owner_id, 0) = ? AND metric = ? "
        "AND period_type = ? AND period_start = ?",
        (org, data.ownerId or 0, data.metric, data.periodType, start.isoformat()),
    ).fetchone()
    if exists:
        raise AppError(409, "GOAL_ALREADY_EXISTS", "Já existe uma meta igual para este período.")

    now = now_iso()
    cur = db.execute(
        "INSERT INTO goals(organization_id, owner_id, metric, period_type, period_start, target, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (org, data.ownerId, data.metric, data.periodType, start.isoformat(), data.target, now, now),
    )
    publish(db, user, "GoalCreated", "goal", cur.lastrowid,
            {"metric": data.metric, "target": data.target, "ownerId": data.ownerId})
    db.commit()
    return to_dto(db, org, _get(db, user, cur.lastrowid), datetime.now(timezone.utc))


@router.patch("/{goal_id}")
def update_goal(goal_id: int, data: GoalUpdate, db=Depends(get_db), user=Depends(require_roles(*MANAGERS))):
    _get(db, user, goal_id)
    db.execute("UPDATE goals SET target = ?, updated_at = ? WHERE id = ?", (data.target, now_iso(), goal_id))
    publish(db, user, "GoalUpdated", "goal", goal_id, {"target": data.target})
    db.commit()
    return to_dto(db, user["organization_id"], _get(db, user, goal_id), datetime.now(timezone.utc))


@router.delete("/{goal_id}", status_code=204)
def delete_goal(goal_id: int, db=Depends(get_db), user=Depends(require_roles(*MANAGERS))):
    _get(db, user, goal_id)
    db.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
    publish(db, user, "GoalDeleted", "goal", goal_id, {})
    db.commit()
    return Response(status_code=204)