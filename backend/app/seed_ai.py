"""Etapa 8: calcula o score de todos os leads uma vez na inicialização (idempotente)."""
from datetime import datetime, timezone

from .scoring import apply_score, lead_rows, load_weights, score_lead, sla_limits


def seed_ai(conn) -> None:
    now = datetime.now(timezone.utc)
    for org in conn.execute("SELECT id FROM organizations").fetchall():
        w, limits = load_weights(conn, org["id"]), sla_limits(conn, org["id"])
        todo = [r for r in lead_rows(conn, org["id"], now) if r["scored_at"] is None]
        for r in todo:
            apply_score(conn, r["id"], score_lead(r, w, now, limits))
        if todo:
            print(f"[seed] score de {len(todo)} lead(s) calculado")
    conn.commit()