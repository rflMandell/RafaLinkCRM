import csv
import io
import json
import re
from datetime import date, timedelta
from math import ceil

from fastapi import APIRouter, Depends, Query, Response

from ..database import get_db
from ..security import require_roles
from ..permissions import require_perm

router = APIRouter(prefix="/audit", tags=["Auditoria"])
MANAGERS = ("ADMIN", "SALES_MANAGER")

# A auditoria lê a tabela domain_events (tudo que o sistema já publica). Tipos não listados
# aparecem com o nome "quebrado em palavras" (ex.: LeadCreated -> Lead Created): adicione aqui para traduzir.
EVENT_LABELS = {
    "LeadScored": "Nota do lead calculada", "LeadScoresRecalculated": "Notas dos leads recalculadas",
    "AiWeightsUpdated": "Pesos da IA alterados", "AiWeightsReset": "Pesos da IA restaurados",
    "GoalCreated": "Meta criada", "GoalUpdated": "Meta alterada", "GoalDeleted": "Meta excluída",
    "SlaPolicyUpdated": "Política de SLA alterada",
    "AutomationRuleCreated": "Regra de automação criada", "AutomationRuleUpdated": "Regra de automação alterada",
    "AutomationRuleDeleted": "Regra de automação excluída", "AutomationExecuted": "Automação executada",
    "UserCreated": "Usuário criado", "UserUpdated": "Usuário alterado",
    "OrganizationUpdated": "Organização alterada", "PermissionChanged": "Permissão alterada",
    "PermissionsReset": "Permissões restauradas", "ImportCompleted": "Importação CSV concluída",
    "RecordsMerged": "Registros mesclados",
}
ENTITY_LABELS = {
    "lead": "Lead", "company": "Empresa", "contact": "Contato", "opportunity": "Oportunidade", "activity": "Atividade",
    "campaign": "Campanha", "goal": "Meta", "sla_policy": "SLA", "ai_weights": "Pesos da IA",
    "automation_rule": "Automação", "user": "Usuário", "pipeline": "Pipeline",
    "organization": "Organização", "role_permission": "Permissões",
}


def _label(type_: str) -> str:
    return EVENT_LABELS.get(type_) or re.sub(r"(?<!^)(?=[A-Z])", " ", type_)


def _summary(payload: dict) -> str:
    parts = [f"{k}: {v}" for k, v in payload.items() if isinstance(v, (str, int, float, bool)) and v != ""]
    return " · ".join(parts[:3])


def _filters(org, entity, type_, user_id, q, date_from, date_to):
    where, args = "e.organization_id = ?", [org]
    if entity:
        where += " AND e.entity = ?"; args.append(entity)
    if type_:
        where += " AND e.type = ?"; args.append(type_)
    if user_id is not None:
        where += " AND e.user_id = ?"; args.append(user_id)
    if q:
        where += " AND (e.type LIKE ? OR e.payload LIKE ?)"; args += [f"%{q}%", f"%{q}%"]
    if date_from:
        where += " AND e.created_at >= ?"; args.append(date_from.isoformat() + "T00:00:00")
    if date_to:
        where += " AND e.created_at < ?"; args.append((date_to + timedelta(days=1)).isoformat() + "T00:00:00")
    return where, args


def _dto(r) -> dict:
    payload = json.loads(r["payload"] or "{}")
    return {"id": r["id"], "type": r["type"], "typeLabel": _label(r["type"]), "entity": r["entity"],
            "entityLabel": ENTITY_LABELS.get(r["entity"], r["entity"]), "entityId": r["entity_id"],
            "userId": r["user_id"], "userName": r["user_name"] or "Sistema", "payload": payload,
            "summary": _summary(payload), "createdAt": r["created_at"]}


SELECT = "SELECT e.*, u.name AS user_name FROM domain_events e LEFT JOIN users u ON u.id = e.user_id"


@router.get("")
def list_audit(entity: str | None = None, type: str | None = None, userId: int | None = None, q: str | None = None,
               dateFrom: date | None = None, dateTo: date | None = None,
               page: int = Query(0, ge=0), size: int = Query(25, ge=1, le=100),
               db=Depends(get_db), user=Depends(require_perm("audit.read"))):
    where, args = _filters(user["organization_id"], entity, type, userId, q, dateFrom, dateTo)
    total = db.execute(f"SELECT COUNT(*) FROM domain_events e WHERE {where}", args).fetchone()[0]
    rows = db.execute(f"{SELECT} WHERE {where} ORDER BY e.id DESC LIMIT ? OFFSET ?", args + [size, page * size]).fetchall()
    return {"content": [_dto(r) for r in rows], "page": page, "size": size, "totalElements": total,
            "totalPages": ceil(total / size) if total else 0}


@router.get("/options")
def options(db=Depends(get_db), user=Depends(require_perm("audit.read"))):
    org = user["organization_id"]
    types = [r[0] for r in db.execute("SELECT DISTINCT type FROM domain_events WHERE organization_id = ? ORDER BY type", (org,))]
    entities = [r[0] for r in db.execute("SELECT DISTINCT entity FROM domain_events WHERE organization_id = ? ORDER BY entity", (org,))]
    users = db.execute("SELECT id, name FROM users WHERE organization_id = ? ORDER BY name", (org,)).fetchall()
    return {"types": [{"value": t, "label": _label(t)} for t in types],
            "entities": [{"value": e, "label": ENTITY_LABELS.get(e, e)} for e in entities],
            "users": [dict(u) for u in users]}


@router.get("/export")
def export_csv(entity: str | None = None, type: str | None = None, userId: int | None = None, q: str | None = None,
               dateFrom: date | None = None, dateTo: date | None = None,
               db=Depends(get_db), user=Depends(require_perm("audit.read"))):
    where, args = _filters(user["organization_id"], entity, type, userId, q, dateFrom, dateTo)
    rows = db.execute(f"{SELECT} WHERE {where} ORDER BY e.id DESC LIMIT 5000", args).fetchall()
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Data (UTC)", "Usuário", "Ação", "Entidade", "ID", "Detalhes"])
    for r in rows:
        d = _dto(r)
        w.writerow([d["createdAt"], d["userName"], d["typeLabel"], d["entityLabel"], d["entityId"] or "",
                    json.dumps(d["payload"], ensure_ascii=False)])
    return Response(content="\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="auditoria.csv"'})