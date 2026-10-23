"""Metas de demonstração da Etapa 7. Idempotente: só cria se ainda não houver nenhuma meta."""
from datetime import datetime, timedelta, timezone

from .database import now_iso
from .routers.goals import period_bounds


def seed_goals(conn) -> None:
    if conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0] > 0:
        return
    org = conn.execute("SELECT id FROM organizations ORDER BY id LIMIT 1").fetchone()
    if org is None:
        return
    org_id = org["id"]
    owners = [r["id"] for r in conn.execute(
        "SELECT id FROM users WHERE organization_id = ? ORDER BY id", (org_id,))]

    today = datetime.now(timezone.utc).date()
    month_start, _ = period_bounds("MONTH", today)
    quarter_start, _ = period_bounds("QUARTER", today)
    prev_month, _ = period_bounds("MONTH", month_start - timedelta(days=1))

    # dono (None = equipe), métrica, tipo de período, início, alvo
    rows = [
        (None, "REVENUE", "MONTH", month_start, 150000),
        (None, "WON_COUNT", "MONTH", month_start, 6),
        (None, "NEW_LEADS", "MONTH", month_start, 30),
        (None, "REVENUE", "QUARTER", quarter_start, 450000),
        (None, "REVENUE", "MONTH", prev_month, 120000),
    ]
    rows += [(o, "REVENUE", "MONTH", month_start, 50000) for o in owners]

    now = now_iso()
    for owner, metric, ptype, start, target in rows:
        conn.execute(
            "INSERT INTO goals(organization_id, owner_id, metric, period_type, period_start, target, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (org_id, owner, metric, ptype, start.isoformat(), target, now, now),
        )
    conn.commit()
    print("[seed] metas de demonstração criadas")