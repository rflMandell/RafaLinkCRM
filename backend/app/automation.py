"""Etapa 9: motor de automação + notificações.

Como funciona (sem depender dos nomes dos eventos das etapas antigas):
  - Cada REGRA = um gatilho + uma ação (+ configuração).
  - A cada ciclo (a cada 60 s, ou no botão "Executar agora") o motor procura no banco as
    situações que cada regra ativa descreve ("candidatos").
  - Para cada candidato ainda não tratado (tabela automation_runs, única por regra + chave),
    executa a ação: NOTIFY (cria notificações) ou CREATE_TASK (cria uma tarefa).
  - A chave de deduplicação garante que a mesma situação nunca dispara duas vezes.
"""
import json
from datetime import datetime, timedelta, timezone

from . import scoring
from .database import now_iso
from .errors import AppError
from .routers import sla

TASK_TYPE = "TAREFA"                  # valor de activities.type usado nas tarefas criadas pelo motor
MANAGER_ROLES = ("ADMIN", "SALES_MANAGER")
MAX_PER_RULE_RUN = 50                 # evita "enxurrada" na primeira execução; o resto sai no próximo ciclo

RECIPIENTS = {
    "OWNER": "Responsável",
    "MANAGERS": "Gerentes e administradores",
    "OWNER_AND_MANAGERS": "Responsável e gerentes",
}
ACTIONS = {"NOTIFY": "Enviar notificação", "CREATE_TASK": "Criar tarefa"}

_DAYS = lambda key, label, default, lo, hi: {"key": key, "label": label, "type": "number", "default": default, "min": lo, "max": hi}

CATALOG = {
    "SLA_BREACH": {
        "label": "Violação de SLA", "kind": "estado",
        "description": "Lead ou oportunidade que passou (ou está perto de passar) do prazo de SLA da Etapa 7.",
        "fields": [{"key": "severity", "label": "Avisar quando", "type": "select", "default": "BREACH",
                    "options": [["BREACH", "O prazo estourar"], ["ANY", "O prazo estourar ou estiver perto"]]}],
    },
    "HOT_LEAD": {
        "label": "Lead quente", "kind": "estado",
        "description": "Lead cuja nota da IA (Etapa 8) chegou ao mínimo definido.",
        "fields": [_DAYS("threshold", "Nota mínima", 70, 40, 100)],
    },
    "CHURN_HIGH": {
        "label": "Cliente em risco de churn", "kind": "estado",
        "description": "Cliente cujo risco de perda (Etapa 8) chegou ao mínimo definido. Avisa uma vez por mês.",
        "fields": [_DAYS("threshold", "Risco mínimo", 60, 10, 100)],
    },
    "TASK_OVERDUE": {
        "label": "Tarefa atrasada", "kind": "estado",
        "description": "Tarefa pendente com o prazo vencido.", "fields": [],
    },
    "OPP_CLOSING_SOON": {
        "label": "Fechamento próximo", "kind": "estado",
        "description": "Oportunidade aberta com data prevista de fechamento chegando.",
        "fields": [_DAYS("days", "Avisar quantos dias antes", 3, 1, 30)],
    },
    "NEW_LEAD": {
        "label": "Novo lead", "kind": "evento",
        "description": "Lead cadastrado recentemente.",
        "fields": [_DAYS("lookbackDays", "Considerar leads dos últimos (dias)", 2, 1, 30)],
    },
    "OPP_WON": {
        "label": "Venda ganha", "kind": "evento",
        "description": "Oportunidade marcada como ganha recentemente.",
        "fields": [_DAYS("lookbackDays", "Considerar vendas dos últimos (dias)", 7, 1, 30)],
    },
    "OPP_LOST": {
        "label": "Oportunidade perdida", "kind": "evento",
        "description": "Oportunidade marcada como perdida recentemente.",
        "fields": [_DAYS("lookbackDays", "Considerar perdas dos últimos (dias)", 7, 1, 30)],
    },
}

DEFAULT_RULES = [
    ("Avisar sobre violação de SLA", "SLA_BREACH", "NOTIFY", {"recipients": "OWNER_AND_MANAGERS"}, True),
    ("Avisar sobre lead quente", "HOT_LEAD", "NOTIFY", {"recipients": "OWNER", "threshold": 70}, True),
    ("Avisar sobre cliente em risco", "CHURN_HIGH", "NOTIFY", {"recipients": "OWNER_AND_MANAGERS", "threshold": 60}, True),
    ("Avisar sobre tarefa atrasada", "TASK_OVERDUE", "NOTIFY", {"recipients": "OWNER"}, True),
    ("Avisar sobre fechamento próximo", "OPP_CLOSING_SOON", "NOTIFY", {"recipients": "OWNER", "days": 3}, True),
    ("Criar tarefa de primeiro contato", "NEW_LEAD", "CREATE_TASK",
     {"lookbackDays": 2, "taskTitle": "Fazer o primeiro contato com {name}", "taskDueDays": 1}, True),
    ("Comemorar vendas ganhas", "OPP_WON", "NOTIFY", {"recipients": "MANAGERS", "lookbackDays": 7}, True),
    ("Avisar sobre oportunidades perdidas", "OPP_LOST", "NOTIFY", {"recipients": "MANAGERS", "lookbackDays": 7}, False),
]


# ---------- Validação da configuração ----------
def clean_config(trigger: str, action: str, cfg: dict) -> dict:
    cfg = cfg or {}
    out: dict = {}
    for f in CATALOG[trigger]["fields"]:
        v = cfg.get(f["key"], f["default"])
        if f["type"] == "number":
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise AppError(400, "INVALID_CONFIG", f"{f['label']}: informe um número.")
            if not f["min"] <= v <= f["max"]:
                raise AppError(400, "INVALID_CONFIG", f"{f['label']}: use um valor entre {f['min']} e {f['max']}.")
        elif v not in [o[0] for o in f["options"]]:
            raise AppError(400, "INVALID_CONFIG", f"{f['label']}: opção inválida.")
        out[f["key"]] = v
    rec = cfg.get("recipients", "OWNER")
    if rec not in RECIPIENTS:
        raise AppError(400, "INVALID_CONFIG", "Destinatários inválidos.")
    out["recipients"] = rec
    if action == "CREATE_TASK":
        title = str(cfg.get("taskTitle") or "").strip()
        if not title or len(title) > 120:
            raise AppError(400, "INVALID_CONFIG", "Informe o título da tarefa (até 120 caracteres).")
        try:
            days = int(cfg.get("taskDueDays", 1))
        except (TypeError, ValueError):
            raise AppError(400, "INVALID_CONFIG", "Prazo da tarefa: informe um número de dias.")
        if not 0 <= days <= 60:
            raise AppError(400, "INVALID_CONFIG", "Prazo da tarefa: use de 0 a 60 dias.")
        out["taskTitle"], out["taskDueDays"] = title, days
    return out


# ---------- Notificações e eventos de sistema ----------
def notify(db, org: int, user_id: int, type_: str, title: str, message: str | None,
           entity: str | None = None, entity_id: int | None = None) -> None:
    db.execute(
        "INSERT INTO notifications(organization_id, user_id, type, title, message, entity, entity_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (org, user_id, type_, title[:200], (message or "")[:500], entity, entity_id, now_iso()),
    )


def publish_system(db, org: int, type_: str, entity: str, entity_id: int | None, payload: dict) -> None:
    """Evento sem usuário (feito pelo motor). Aparece na Auditoria como "Sistema"."""
    db.execute(
        "INSERT INTO domain_events(organization_id, user_id, type, entity, entity_id, payload, created_at) "
        "VALUES (?, NULL, ?, ?, ?, ?, ?)",
        (org, type_, entity, entity_id, json.dumps(payload, ensure_ascii=False), now_iso()),
    )


def _managers(db, org: int) -> list[int]:
    return [r["id"] for r in db.execute(
        "SELECT id FROM users WHERE organization_id = ? AND active = 1 AND role IN (?, ?) ORDER BY id",
        (org, *MANAGER_ROLES))]


def _recipients(db, org: int, mode: str, owner_id: int | None) -> list[int]:
    ids: list[int] = []
    if mode in ("OWNER", "OWNER_AND_MANAGERS") and owner_id:
        active = db.execute("SELECT 1 FROM users WHERE id = ? AND organization_id = ? AND active = 1", (owner_id, org)).fetchone()
        if active:
            ids.append(owner_id)
    if mode in ("MANAGERS", "OWNER_AND_MANAGERS") or not ids:   # sem responsável: cai para os gerentes
        ids += _managers(db, org)
    return list(dict.fromkeys(ids))


# ---------- Utilidades ----------
def _brl(v) -> str:
    return "R$ " + f"{float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _dmy(day: str | None) -> str:
    return f"{day[8:10]}/{day[5:7]}/{day[:4]}" if day else "—"


def _owner_of(db, entity: str, entity_id: int) -> int | None:
    table = {"lead": "leads", "opportunity": "opportunities", "company": "companies", "activity": "activities"}.get(entity)
    if not table:
        return None
    r = db.execute(f"SELECT owner_id FROM {table} WHERE id = ?", (entity_id,)).fetchone()
    return r["owner_id"] if r else None


# ---------- Candidatos de cada gatilho ----------
# Cada gerador devolve dicts: entity, id, name, owner_id, dedupe, title, message
def _c_sla(db, org, cfg, now):
    ov = sla.overview(None, db, {"organization_id": org, "role": "ADMIN", "id": 0})
    out = []
    for it in ov["items"]:
        if cfg.get("severity", "BREACH") == "BREACH" and it["severity"] != "BREACH":
            continue
        verb = "estourou" if it["severity"] == "BREACH" else "está perto de estourar"
        out.append({
            "entity": it["entity"], "id": it["entityId"], "name": it["name"],
            "owner_id": _owner_of(db, it["entity"], it["entityId"]),
            "dedupe": f"sla:{it['kind']}:{it['entityId']}:{it['severity']}:{it['since']}",
            "title": f"SLA {verb}: {it['name']}",
            "message": f"{sla.POLICIES[it['kind']][0]}: {it['age']:g} {it['unit']} (limite {it['threshold']:g}).",
        })
    return out


def _c_hot_lead(db, org, cfg, now):
    w, limits = scoring.load_weights(db, org), scoring.sla_limits(db, org)
    out = []
    for r in scoring.lead_rows(db, org, now):
        sc = scoring.score_lead(r, w, now, limits)
        if sc["score"] >= cfg.get("threshold", 70):
            action = scoring.lead_actions(r, sc, now, limits)[0]
            out.append({"entity": "lead", "id": r["id"], "name": r["name"], "owner_id": r["owner_id"],
                        "dedupe": f"hot:{r['id']}", "title": f"Lead quente: {r['name']}",
                        "message": f"Nota {sc['score']}/100. Sugestão: {action['title']}."})
    return out


def _c_churn(db, org, cfg, now):
    w = scoring.load_weights(db, org)
    out = []
    for ctx in scoring.customer_contexts(db, org, now):
        ch = scoring.churn_company(ctx, w, now)
        if ch["risk"] >= cfg.get("threshold", 60):
            c = ctx["company"]
            why = ch["factors"][0]["detail"] if ch["factors"] else "vários sinais"
            out.append({"entity": "company", "id": c["id"], "name": c["name"], "owner_id": c["owner_id"],
                        "dedupe": f"churn:{c['id']}:{now:%Y-%m}", "title": f"Cliente em risco: {c['name']}",
                        "message": f"Risco de perda {ch['risk']}/100 ({why})."})
    return out


def _c_task_overdue(db, org, cfg, now):
    rows = db.execute(
        "SELECT id, title, owner_id, due_at FROM activities WHERE organization_id = ? AND status = 'PENDENTE' AND due_at < ?",
        (org, now.isoformat(timespec="seconds"))).fetchall()
    return [{"entity": "activity", "id": r["id"], "name": r["title"], "owner_id": r["owner_id"],
             "dedupe": f"task:{r['id']}", "title": f"Tarefa atrasada: {r['title']}",
             "message": f"Venceu em {_dmy(r['due_at'][:10])}."} for r in rows]


def _c_closing(db, org, cfg, now):
    today = now.date()
    last = today + timedelta(days=cfg.get("days", 3))
    rows = db.execute(
        "SELECT id, title, owner_id, value, expected_close_date FROM opportunities "
        "WHERE organization_id = ? AND status = 'ABERTA' AND expected_close_date >= ? AND expected_close_date <= ?",
        (org, today.isoformat(), last.isoformat())).fetchall()
    return [{"entity": "opportunity", "id": r["id"], "name": r["title"], "owner_id": r["owner_id"],
             "dedupe": f"close:{r['id']}:{r['expected_close_date']}", "title": f"Fechamento próximo: {r['title']}",
             "message": f"Previsto para {_dmy(r['expected_close_date'])} · {_brl(r['value'])}."} for r in rows]


def _since(now, cfg, default):
    return (now - timedelta(days=cfg.get("lookbackDays", default))).isoformat(timespec="seconds")


def _c_new_lead(db, org, cfg, now):
    rows = db.execute(
        "SELECT id, name, owner_id, channel, source FROM leads WHERE organization_id = ? AND created_at >= ? "
        "AND status NOT IN ('ARQUIVADO', 'PERDIDO')", (org, _since(now, cfg, 2))).fetchall()
    return [{"entity": "lead", "id": r["id"], "name": r["name"], "owner_id": r["owner_id"],
             "dedupe": f"newlead:{r['id']}", "title": f"Novo lead: {r['name']}",
             "message": f"Origem: {r['source'] or r['channel'] or 'não informada'}."} for r in rows]


def _c_won(db, org, cfg, now):
    rows = db.execute(
        "SELECT id, title, owner_id, value, realized_value FROM opportunities "
        "WHERE organization_id = ? AND status = 'GANHA' AND closed_at >= ?", (org, _since(now, cfg, 7))).fetchall()
    return [{"entity": "opportunity", "id": r["id"], "name": r["title"], "owner_id": r["owner_id"],
             "dedupe": f"won:{r['id']}", "title": f"Venda ganha: {r['title']}",
             "message": f"Valor realizado: {_brl(r['realized_value'] or r['value'])}."} for r in rows]


def _c_lost(db, org, cfg, now):
    rows = db.execute(
        "SELECT id, title, owner_id, lost_reason FROM opportunities "
        "WHERE organization_id = ? AND status = 'PERDIDA' AND closed_at >= ?", (org, _since(now, cfg, 7))).fetchall()
    return [{"entity": "opportunity", "id": r["id"], "name": r["title"], "owner_id": r["owner_id"],
             "dedupe": f"lost:{r['id']}", "title": f"Oportunidade perdida: {r['title']}",
             "message": f"Motivo: {r['lost_reason'] or 'não informado'}."} for r in rows]


GENERATORS = {
    "SLA_BREACH": _c_sla, "HOT_LEAD": _c_hot_lead, "CHURN_HIGH": _c_churn, "TASK_OVERDUE": _c_task_overdue,
    "OPP_CLOSING_SOON": _c_closing, "NEW_LEAD": _c_new_lead, "OPP_WON": _c_won, "OPP_LOST": _c_lost,
}


# ---------- Ações ----------
LINK_COLUMN = {"lead": "lead_id", "opportunity": "opportunity_id", "company": "company_id"}


def _do_notify(db, org, rule, cfg, cand) -> str:
    ids = _recipients(db, org, cfg.get("recipients", "OWNER"), cand["owner_id"])
    for uid in ids:
        notify(db, org, uid, rule["trigger_type"], cand["title"], cand["message"], cand["entity"], cand["id"])
    return f"{len(ids)} notificação(ões)"


def _do_task(db, org, rule, cfg, cand, now) -> str:
    owner = cand["owner_id"] or (_managers(db, org) or [None])[0]
    if owner is None:
        return "sem responsável: tarefa não criada"
    title = cfg["taskTitle"].replace("{name}", cand["name"])[:150]
    due = (now + timedelta(days=cfg.get("taskDueDays", 1))).isoformat(timespec="seconds")
    cols = ["organization_id", "type", "title", "description", "status", "due_at", "owner_id", "created_by",
            "created_at", "updated_at"]
    vals = [org, TASK_TYPE, title, f"Criada pela automação “{rule['name']}”.", "PENDENTE", due, owner, owner,
            now_iso(), now_iso()]
    link = LINK_COLUMN.get(cand["entity"])
    if link:
        cols.append(link)
        vals.append(cand["id"])
    db.execute(f"INSERT INTO activities({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", vals)
    return "tarefa criada"


# ---------- Execução ----------
def run_rule(db, rule, now: datetime) -> int:
    cfg = json.loads(rule["config"] or "{}")
    org = rule["organization_id"]
    done = 0
    for cand in GENERATORS[rule["trigger_type"]](db, org, cfg, now):
        if done >= MAX_PER_RULE_RUN:
            break
        cur = db.execute(
            "INSERT OR IGNORE INTO automation_runs(organization_id, rule_id, dedupe_key, entity, entity_id, entity_name, "
            "status, message, created_at) VALUES (?, ?, ?, ?, ?, ?, 'OK', NULL, ?)",
            (org, rule["id"], cand["dedupe"], cand["entity"], cand["id"], cand["name"], now_iso()))
        if cur.rowcount == 0:
            continue                       # esta situação já foi tratada por esta regra
        run_id = cur.lastrowid
        try:
            msg = _do_notify(db, org, rule, cfg, cand) if rule["action"] == "NOTIFY" else _do_task(db, org, rule, cfg, cand, now)
            db.execute("UPDATE automation_runs SET message = ? WHERE id = ?", (msg, run_id))
            done += 1
        except Exception as exc:          # uma falha não derruba as outras
            db.execute("UPDATE automation_runs SET status = 'ERROR', message = ? WHERE id = ?", (str(exc)[:300], run_id))
    if done:
        db.execute("UPDATE automation_rules SET run_count = run_count + ?, last_run_at = ? WHERE id = ?",
                   (done, now_iso(), rule["id"]))
        publish_system(db, org, "AutomationExecuted", "automation_rule", rule["id"],
                       {"rule": rule["name"], "trigger": rule["trigger_type"], "action": rule["action"], "executed": done})
    db.commit()
    return done


def run_org(db, org: int) -> dict:
    now = datetime.now(timezone.utc)
    total, by_rule = 0, []
    for rule in db.execute("SELECT * FROM automation_rules WHERE organization_id = ? AND active = 1 ORDER BY id", (org,)).fetchall():
        n = run_rule(db, rule, now)
        total += n
        if n:
            by_rule.append({"ruleId": rule["id"], "name": rule["name"], "executed": n})
    return {"executed": total, "rules": by_rule}


def run_all(db) -> dict:
    out = {"executed": 0, "rules": []}
    for org in db.execute("SELECT id FROM organizations").fetchall():
        r = run_org(db, org["id"])
        out["executed"] += r["executed"]
        out["rules"] += r["rules"]
    return out