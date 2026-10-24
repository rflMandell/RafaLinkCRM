"""Etapa 9: cria as regras padrão (uma vez por organização) e roda o motor na inicialização."""
import json

from .automation import DEFAULT_RULES, clean_config, run_all
from .database import now_iso


def seed_automation(conn) -> None:
    for org in conn.execute("SELECT id FROM organizations").fetchall():
        if conn.execute("SELECT COUNT(*) FROM automation_rules WHERE organization_id = ?", (org["id"],)).fetchone()[0]:
            continue
        for name, trigger, action, cfg, active in DEFAULT_RULES:
            conn.execute(
                "INSERT INTO automation_rules(organization_id, name, trigger_type, action, config, active, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (org["id"], name, trigger, action, json.dumps(clean_config(trigger, action, cfg)), 1 if active else 0,
                 now_iso(), now_iso()))
        print("[seed] regras de automação criadas")
    conn.commit()
    r = run_all(conn)
    if r["executed"]:
        print(f"[seed] automações executaram {r['executed']} vez(es)")