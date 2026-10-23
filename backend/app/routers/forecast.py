from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from ..database import get_db
from ..security import get_current_user

router = APIRouter(prefix="/forecast", tags=["Forecast"])

# Categorias de confiança, pela probabilidade da etapa atual da oportunidade
COMMIT_MIN = 80      # "commit": quase fechada
BEST_MIN = 40        # "best case": boa chance
CATEGORIES = ["commit", "bestCase", "pipeline"]


def category(probability: int) -> str:
    if probability >= COMMIT_MIN:
        return "commit"
    if probability >= BEST_MIN:
        return "bestCase"
    return "pipeline"


def month_key(year: int, month: int, plus: int) -> str:
    idx = year * 12 + (month - 1) + plus
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def _empty(kind: str, key: str | None) -> dict:
    return {
        "key": key, "kind": kind, "won": 0.0, "count": 0, "openValue": 0.0,
        "weighted": {c: 0.0 for c in CATEGORIES},
        "raw": {c: 0.0 for c in CATEGORIES},
    }


@router.get("")
def forecast(
    months: int = Query(6, ge=1, le=12),
    owner: int | None = None,
    pipeline: int | None = None,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    """Receita prevista por mês de fechamento esperado, ponderada pela probabilidade da etapa."""
    org = user["organization_id"]
    now = datetime.now(timezone.utc)
    keys = [month_key(now.year, now.month, i) for i in range(months)]
    current = keys[0]
    next_month = month_key(now.year, now.month, 1)
    cur_start = f"{current}-01"
    horizon_end = month_key(now.year, now.month, months) + "-01"

    extra, params = "", []
    if owner is not None:
        extra += " AND o.owner_id = ?"
        params.append(owner)
    if pipeline is not None:
        extra += " AND o.pipeline_id = ?"
        params.append(pipeline)

    buckets = {"overdue": _empty("overdue", None), "nodate": _empty("nodate", None),
               "later": _empty("later", None)}
    for k in keys:
        buckets[k] = _empty("month", k)

    open_rows = db.execute(
        "SELECT o.id, o.value, o.probability, o.expected_close_date, o.owner_id, u.name AS owner_name "
        "FROM opportunities o LEFT JOIN users u ON u.id = o.owner_id "
        "WHERE o.organization_id = ? AND o.status = 'ABERTA'" + extra,
        [org] + params,
    ).fetchall()

    owners: dict = {}
    for r in open_rows:
        d = r["expected_close_date"]
        if not d:
            b = buckets["nodate"]
        elif d < cur_start:
            b = buckets["overdue"]
        elif d >= horizon_end:
            b = buckets["later"]
        else:
            b = buckets[d[:7]]
        cat = category(r["probability"])
        weighted = r["value"] * r["probability"] / 100
        b["count"] += 1
        b["openValue"] += r["value"]
        b["weighted"][cat] += weighted
        b["raw"][cat] += r["value"]

        o = owners.setdefault(r["owner_id"], {
            "ownerId": r["owner_id"], "ownerName": r["owner_name"] or "Sem responsável",
            "openCount": 0, "openValue": 0.0, "weighted": 0.0, "commit": 0.0, "wonMonth": 0.0,
        })
        o["openCount"] += 1
        o["openValue"] += r["value"]
        o["weighted"] += weighted
        if cat == "commit":
            o["commit"] += weighted

    # Ganhos do mês atual (a receita já garantida entra na previsão do mês)
    won_rows = db.execute(
        "SELECT o.owner_id, u.name AS owner_name, COALESCE(SUM(COALESCE(o.realized_value, o.value)), 0) AS total "
        "FROM opportunities o LEFT JOIN users u ON u.id = o.owner_id "
        "WHERE o.organization_id = ? AND o.status = 'GANHA' AND o.closed_at >= ? AND o.closed_at < ?"
        + extra + " GROUP BY o.owner_id, u.name",
        [org, cur_start + "T00:00:00+00:00", next_month + "-01T00:00:00+00:00"] + params,
    ).fetchall()
    won_total = 0.0
    for r in won_rows:
        won_total += r["total"]
        o = owners.setdefault(r["owner_id"], {
            "ownerId": r["owner_id"], "ownerName": r["owner_name"] or "Sem responsável",
            "openCount": 0, "openValue": 0.0, "weighted": 0.0, "commit": 0.0, "wonMonth": 0.0,
        })
        o["wonMonth"] += r["total"]
    buckets[current]["won"] = won_total

    cm = buckets[current]
    scenarios = {
        # só o que já está quase fechado, ponderado
        "conservative": round(won_total + cm["weighted"]["commit"], 2),
        # tudo ponderado pela probabilidade
        "expected": round(won_total + sum(cm["weighted"].values()), 2),
        # commit + best case pelo valor cheio
        "optimistic": round(won_total + cm["raw"]["commit"] + cm["raw"]["bestCase"], 2),
    }

    goal = db.execute(
        "SELECT target FROM goals WHERE organization_id = ? AND owner_id IS NULL AND metric = 'REVENUE' "
        "AND period_type = 'MONTH' AND period_start = ?",
        (org, cur_start),
    ).fetchone()

    order = ["overdue"] + keys + ["later", "nodate"]
    out = []
    for name in order:
        b = buckets[name]
        if name in ("overdue", "later", "nodate") and b["count"] == 0:
            continue  # colunas especiais só aparecem quando existem
        total_weighted = sum(b["weighted"].values())
        out.append({
            "key": b["key"], "kind": b["kind"], "won": round(b["won"], 2), "count": b["count"],
            "openValue": round(b["openValue"], 2), "weightedTotal": round(total_weighted, 2),
            "weighted": {c: round(v, 2) for c, v in b["weighted"].items()},
            "raw": {c: round(v, 2) for c, v in b["raw"].items()},
        })

    pipelines = db.execute(
        "SELECT id, name FROM pipelines WHERE organization_id = ? ORDER BY is_default DESC, name", (org,)
    ).fetchall()
    team = db.execute(
        "SELECT id, name FROM users WHERE organization_id = ? AND active = 1 ORDER BY name", (org,)
    ).fetchall()

    return {
        "months": out,
        "currentMonth": current,
        "scenarios": scenarios,
        "wonThisMonth": round(won_total, 2),
        "monthGoal": goal["target"] if goal else None,
        "thresholds": {"commitMin": COMMIT_MIN, "bestMin": BEST_MIN},
        "owners": sorted(
            ({**o, "openValue": round(o["openValue"], 2), "weighted": round(o["weighted"], 2),
              "commit": round(o["commit"], 2), "wonMonth": round(o["wonMonth"], 2)} for o in owners.values()),
            key=lambda o: -o["weighted"],
        ),
        "filters": {
            "owners": [dict(t) for t in team],
            "pipelines": [dict(p) for p in pipelines],
        },
    }