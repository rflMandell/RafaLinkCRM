from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from ..database import get_db
from ..security import get_current_user

router = APIRouter(prefix="/reports", tags=["Reports"])

FUNNEL = ["NOVO", "EM_CONTATO", "QUALIFICADO", "OPORTUNIDADE", "CONVERTIDO"]


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _kpis(db, org: int, start: datetime, end: datetime) -> dict:
    """Indicadores de um intervalo [start, end). Leads contam pela data de criação;
    vendas contam pela data de fechamento."""
    s, e = _iso(start), _iso(end)

    leads = db.execute(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(CASE WHEN status = 'CONVERTIDO' THEN 1 ELSE 0 END), 0) AS converted "
        "FROM leads WHERE organization_id = ? AND created_at >= ? AND created_at < ?",
        (org, s, e),
    ).fetchone()

    won = db.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(COALESCE(realized_value, value)), 0) AS revenue, "
        "AVG(julianday(closed_at) - julianday(created_at)) AS cycle_days "
        "FROM opportunities WHERE organization_id = ? AND status = 'GANHA' "
        "AND closed_at >= ? AND closed_at < ?",
        (org, s, e),
    ).fetchone()

    contact = db.execute(
        "SELECT AVG((julianday(first_contact_at) - julianday(created_at)) * 24) AS hours "
        "FROM leads WHERE organization_id = ? AND created_at >= ? AND created_at < ? "
        "AND first_contact_at IS NOT NULL AND first_contact_at >= created_at",
        (org, s, e),
    ).fetchone()

    total, converted = leads["total"], leads["converted"]
    n, revenue = won["n"], won["revenue"]
    return {
        "leads": total,
        "converted": converted,
        "conversionRate": round(converted / total * 100, 1) if total else 0,
        "wonCount": n,
        "revenue": round(revenue, 2),
        "avgTicket": round(revenue / n, 2) if n else None,
        "avgCycleDays": round(won["cycle_days"], 1) if won["cycle_days"] is not None else None,
        "avgFirstContactHours": round(contact["hours"], 1) if contact["hours"] is not None else None,
    }


def _series(db, org: int, start: datetime, end: datetime, bucket: int) -> list[dict]:
    rows = db.execute(
        "SELECT substr(created_at, 1, 10) AS d, COUNT(*) AS n FROM leads "
        "WHERE organization_id = ? AND created_at >= ? AND created_at < ? GROUP BY d",
        (org, _iso(start), _iso(end)),
    ).fetchall()
    per_day = {r["d"]: r["n"] for r in rows}

    first, last = start.date(), (end - timedelta(seconds=1)).date()
    points, day = [], first
    while day <= last:
        total = 0
        for i in range(bucket):
            d = day + timedelta(days=i)
            if d <= last:
                total += per_day.get(d.isoformat(), 0)
        points.append({"date": day.isoformat(), "value": total})
        day += timedelta(days=bucket)
    return points


@router.get("/overview")
def overview(
    days: int = Query(30, ge=1, le=365),
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    """Painel analítico do dashboard. Tudo respeita o mesmo período e a organização (RN11)."""
    org = user["organization_id"]
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = today - timedelta(days=days - 1)       # hoje + (days-1) dias anteriores
    end = today + timedelta(days=1)                 # exclusivo
    prev_start, prev_end = start - timedelta(days=days), start
    s, e = _iso(start), _iso(end)

    # Funil: quantos leads do período chegaram a cada etapa (contagem acumulada).
    by_status = {
        r["status"]: r["n"]
        for r in db.execute(
            "SELECT status, COUNT(*) AS n FROM leads "
            "WHERE organization_id = ? AND created_at >= ? AND created_at < ? GROUP BY status",
            (org, s, e),
        )
    }
    funnel = []
    for i, status in enumerate(FUNNEL):
        funnel.append({"status": status, "count": sum(by_status.get(x, 0) for x in FUNNEL[i:])})

    channels = db.execute(
        "SELECT COALESCE(channel, 'SEM_CANAL') AS channel, COUNT(*) AS leads, "
        "COALESCE(SUM(CASE WHEN status = 'CONVERTIDO' THEN 1 ELSE 0 END), 0) AS converted "
        "FROM leads WHERE organization_id = ? AND created_at >= ? AND created_at < ? "
        "GROUP BY COALESCE(channel, 'SEM_CANAL') ORDER BY leads DESC, channel",
        (org, s, e),
    ).fetchall()

    campaigns = db.execute(
        "SELECT ca.id, ca.name, ca.status, "
        "(SELECT COUNT(*) FROM leads l WHERE l.campaign_id = ca.id "
        "   AND l.created_at >= ? AND l.created_at < ?) AS leads, "
        "(SELECT COUNT(*) FROM leads l WHERE l.campaign_id = ca.id AND l.status = 'CONVERTIDO' "
        "   AND l.created_at >= ? AND l.created_at < ?) AS converted, "
        "(SELECT COALESCE(SUM(COALESCE(o.realized_value, o.value)), 0) FROM opportunities o "
        "   WHERE o.campaign_id = ca.id AND o.status = 'GANHA' "
        "   AND o.closed_at >= ? AND o.closed_at < ?) AS revenue "
        "FROM campaigns ca WHERE ca.organization_id = ? "
        "ORDER BY revenue DESC, leads DESC, ca.name LIMIT 8",
        (s, e, s, e, s, e, org),
    ).fetchall()

    return {
        "days": days,
        "from": s,
        "to": e,
        "bucketDays": 1 if days <= 31 else 7,
        "kpis": {
            "current": _kpis(db, org, start, end),
            "previous": _kpis(db, org, prev_start, prev_end),
        },
        "leadsSeries": _series(db, org, start, end, 1 if days <= 31 else 7),
        "funnel": funnel,
        "lostCount": by_status.get("PERDIDO", 0),
        "archivedCount": by_status.get("ARQUIVADO", 0),
        "channels": [
            {
                "channel": c["channel"],
                "leads": c["leads"],
                "converted": c["converted"],
                "conversionRate": round(c["converted"] / c["leads"] * 100, 1) if c["leads"] else 0,
            }
            for c in channels
        ],
        "campaigns": [
            {"id": c["id"], "name": c["name"], "status": c["status"], "leads": c["leads"],
             "converted": c["converted"], "revenue": round(c["revenue"], 2)}
            for c in campaigns
            if c["leads"] > 0 or c["revenue"] > 0
        ],
    }