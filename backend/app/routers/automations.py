import json
from math import ceil

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from ..automation import ACTIONS, CATALOG, MANAGER_ROLES, RECIPIENTS, clean_config, run_org
from ..database import get_db, now_iso
from ..errors import AppError
from ..events import publish
from ..security import get_current_user, require_roles

router = APIRouter(prefix="/automations", tags=["Automações"])


def _dto(r) -> dict:
    return {"id": r["id"], "name": r["name"], "trigger": r["trigger_type"],
            "triggerLabel": CATALOG[r["trigger_type"]]["label"], "action": r["action"],
            "actionLabel": ACTIONS[r["action"]], "config": json.loads(r["config"] or "{}"),
            "active": bool(r["active"]), "runCount": r["run_count"], "lastRunAt": r["last_run_at"]}


def _get(db, user, rule_id: int):
    r = db.execute("SELECT * FROM automation_rules WHERE id = ? AND organization_id = ?",
                   (rule_id, user["organization_id"])).fetchone()
    if r is None:
        raise AppError(404, "AUTOMATION_NOT_FOUND", "Regra de automação não encontrada.")
    return r


class RuleCreate(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    trigger: str
    action: str
    config: dict = {}
    active: bool = True


class RuleUpdate(BaseModel):
    name: str | None = Field(None, min_length=3, max_length=80)
    config: dict | None = None
    active: bool | None = None


def _check_kinds(trigger: str, action: str) -> None:
    if trigger not in CATALOG:
        raise AppError(400, "INVALID_TRIGGER", "Gatilho inválido.")
    if action not in ACTIONS:
        raise AppError(400, "INVALID_ACTION", "Ação inválida.")


@router.get("")
def list_rules(db=Depends(get_db), user=Depends(get_current_user)):
    rows = db.execute("SELECT * FROM automation_rules WHERE organization_id = ? ORDER BY id", (user["organization_id"],)).fetchall()
    return {
        "rules": [_dto(r) for r in rows],
        "catalog": {
            "triggers": [{"key": k, **v} for k, v in CATALOG.items()],
            "actions": [{"key": k, "label": v} for k, v in ACTIONS.items()],
            "recipients": [{"key": k, "label": v} for k, v in RECIPIENTS.items()],
        },
        "canManage": user["role"] in MANAGER_ROLES,
    }


@router.post("", status_code=201)
def create_rule(data: RuleCreate, db=Depends(get_db), user=Depends(require_roles(*MANAGER_ROLES))):
    _check_kinds(data.trigger, data.action)
    cfg = clean_config(data.trigger, data.action, data.config)
    cur = db.execute(
        "INSERT INTO automation_rules(organization_id, name, trigger_type, action, config, active, created_by, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user["organization_id"], data.name.strip(), data.trigger, data.action, json.dumps(cfg), 1 if data.active else 0,
         user["id"], now_iso(), now_iso()))
    publish(db, user, "AutomationRuleCreated", "automation_rule", cur.lastrowid,
            {"name": data.name, "trigger": data.trigger, "action": data.action})
    db.commit()
    return _dto(_get(db, user, cur.lastrowid))


@router.patch("/{rule_id}")
def update_rule(rule_id: int, data: RuleUpdate, db=Depends(get_db), user=Depends(require_roles(*MANAGER_ROLES))):
    r = _get(db, user, rule_id)
    name = data.name.strip() if data.name else r["name"]
    active = r["active"] if data.active is None else (1 if data.active else 0)
    cfg = r["config"]
    if data.config is not None:
        cfg = json.dumps(clean_config(r["trigger_type"], r["action"], data.config))
    db.execute("UPDATE automation_rules SET name = ?, config = ?, active = ?, updated_at = ? WHERE id = ?",
               (name, cfg, active, now_iso(), rule_id))
    publish(db, user, "AutomationRuleUpdated", "automation_rule", rule_id,
            {"name": name, "active": bool(active), "configChanged": data.config is not None})
    db.commit()
    return _dto(_get(db, user, rule_id))


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db=Depends(get_db), user=Depends(require_roles(*MANAGER_ROLES))):
    r = _get(db, user, rule_id)
    db.execute("DELETE FROM automation_runs WHERE rule_id = ?", (rule_id,))
    db.execute("DELETE FROM automation_rules WHERE id = ?", (rule_id,))
    publish(db, user, "AutomationRuleDeleted", "automation_rule", rule_id, {"name": r["name"]})
    db.commit()
    return Response(status_code=204)


@router.post("/run")
def run_now(db=Depends(get_db), user=Depends(require_roles(*MANAGER_ROLES))):
    """Executa o motor agora (o worker já faz isso sozinho a cada 60 s)."""
    return run_org(db, user["organization_id"])


@router.get("/runs")
def list_runs(ruleId: int | None = None, status: str | None = Query(None, pattern="^(OK|ERROR)$"),
              page: int = Query(0, ge=0), size: int = Query(20, ge=1, le=100),
              db=Depends(get_db), user=Depends(get_current_user)):
    where, args = "r.organization_id = ?", [user["organization_id"]]
    if ruleId is not None:
        where += " AND r.rule_id = ?"
        args.append(ruleId)
    if status:
        where += " AND r.status = ?"
        args.append(status)
    total = db.execute(f"SELECT COUNT(*) FROM automation_runs r WHERE {where}", args).fetchone()[0]
    rows = db.execute(
        f"SELECT r.*, a.name AS rule_name FROM automation_runs r JOIN automation_rules a ON a.id = r.rule_id "
        f"WHERE {where} ORDER BY r.id DESC LIMIT ? OFFSET ?", args + [size, page * size]).fetchall()
    return {
        "content": [{"id": r["id"], "ruleId": r["rule_id"], "ruleName": r["rule_name"], "entity": r["entity"],
                     "entityId": r["entity_id"], "entityName": r["entity_name"], "status": r["status"],
                     "message": r["message"], "createdAt": r["created_at"]} for r in rows],
        "page": page, "size": size, "totalElements": total, "totalPages": ceil(total / size) if total else 0,
    }