from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..database import get_db, now_iso
from ..errors import AppError
from ..events import publish
from ..permissions import require_perm
from ..scoring import rescore_lead
from .importer import REASON, _keys

router = APIRouter(prefix="/dedupe", tags=["Duplicados"])
ENTITIES = ("leads", "companies", "contacts")
MAX_GROUPS = 100

SQL = {
    "leads": ("SELECT l.id, l.name, l.email, l.phone, l.company, l.status, l.created_at, "
              "(SELECT COUNT(*) FROM activities a WHERE a.lead_id = l.id) AS links_a, "
              "(SELECT COUNT(*) FROM opportunities o WHERE o.lead_id = l.id) AS links_b "
              "FROM leads l WHERE l.organization_id = ?"),
    "companies": ("SELECT c.id, c.name, c.website, c.phone, c.city, c.type, c.created_at, "
                  "(SELECT COUNT(*) FROM contacts x WHERE x.company_id = c.id) AS links_a, "
                  "(SELECT COUNT(*) FROM opportunities o WHERE o.company_id = c.id) AS links_b "
                  "FROM companies c WHERE c.organization_id = ?"),
    "contacts": ("SELECT c.id, c.name, c.email, c.phone, c.job_title, co.name AS company, c.created_at, "
                 "(SELECT COUNT(*) FROM activities a WHERE a.contact_id = c.id) AS links_a, "
                 "(SELECT COUNT(*) FROM opportunities o WHERE o.contact_id = c.id) AS links_b "
                 "FROM contacts c LEFT JOIN companies co ON co.id = c.company_id WHERE c.organization_id = ?"),
}
LINK_LABELS = {"leads": ("atividades", "oportunidades"), "companies": ("contatos", "oportunidades"),
               "contacts": ("atividades", "oportunidades")}


def _check_entity(entity: str) -> None:
    if entity not in ENTITIES:
        raise AppError(404, "INVALID_ENTITY", "Escolha leads, empresas ou contatos.")


@router.get("/{entity}")
def find_duplicates(entity: str, db=Depends(get_db), user=Depends(require_perm("data.dedupe"))):
    _check_entity(entity)
    recs = {r["id"]: dict(r) for r in db.execute(SQL[entity], (user["organization_id"],))}
    parent = {i: i for i in recs}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    buckets: dict[str, list[int]] = {}
    for rid, r in recs.items():
        for k in _keys(entity, r):
            buckets.setdefault(k, []).append(rid)
    reasons: dict[int, set] = {}
    for k, ids in buckets.items():
        if len(ids) > 1:
            for other in ids[1:]:
                parent[find(other)] = find(ids[0])
            for i in ids:
                reasons.setdefault(i, set()).add(REASON[k[0]])

    groups: dict[int, list[int]] = {}
    for rid in recs:
        groups.setdefault(find(rid), []).append(rid)
    out = []
    for ids in groups.values():
        if len(ids) < 2:
            continue
        rows = sorted((recs[i] for i in ids), key=lambda r: (-(r["links_a"] + r["links_b"]), r["created_at"]))
        why = sorted(set().union(*(reasons.get(i, set()) for i in ids)))
        out.append({"reasons": why, "suggestedKeepId": rows[0]["id"], "records": [
            {**{k: v for k, v in r.items() if not k.startswith("links_")},
             "links": {"a": r["links_a"], "b": r["links_b"]}} for r in rows]})
    out.sort(key=lambda g: -len(g["records"]))
    return {"entity": entity, "linkLabels": LINK_LABELS[entity], "groups": out[:MAX_GROUPS], "totalGroups": len(out)}


@router.get("/check/{entity}")
def check_before_create(entity: str, name: str = "", email: str = "", phone: str = "", company: str = "", website: str = "",
                        db=Depends(get_db), user=Depends(require_perm("data.dedupe"))):
    """Para formulários de cadastro avisarem "já existe algo parecido" antes de salvar."""
    _check_entity(entity)
    probe = {"name": name, "email": email, "phone": phone, "company": company, "website": website}
    wanted = set(_keys(entity, probe))
    found = []
    for r in db.execute(SQL[entity], (user["organization_id"],)):
        r = dict(r)
        hit = wanted.intersection(_keys(entity, r))
        if hit:
            found.append({"id": r["id"], "name": r["name"], "reason": REASON[sorted(hit)[0][0]]})
    return {"matches": found[:5]}


# ---------- Mesclar ----------
class MergeRequest(BaseModel):
    keepId: int
    mergeIds: list[int] = Field(min_length=1, max_length=10)


# tabelas e colunas que apontam para cada entidade
RELINKS = {
    "leads": [("activities", "lead_id"), ("opportunities", "lead_id"), ("contacts", "source_lead_id")],
    "companies": [("contacts", "company_id"), ("opportunities", "company_id"), ("activities", "company_id"), ("leads", "company_id")],
    "contacts": [("opportunities", "contact_id"), ("activities", "contact_id"), ("leads", "contact_id")],
}
FILL_COLUMNS = {
    "leads": ["email", "phone", "company", "source", "channel", "campaign_id", "contact_id", "company_id", "opportunity_id", "next_action"],
    "companies": ["industry", "website", "phone", "city", "notes"],
    "contacts": ["job_title", "email", "phone", "company_id", "contact_preference", "source_lead_id"],
}
TABLE = {"leads": "leads", "companies": "companies", "contacts": "contacts"}


@router.post("/{entity}/merge")
def merge(entity: str, data: MergeRequest, db=Depends(get_db), user=Depends(require_perm("data.merge"))):
    _check_entity(entity)
    org, table = user["organization_id"], TABLE[entity]
    if data.keepId in data.mergeIds:
        raise AppError(400, "INVALID_MERGE", "O registro mantido não pode estar na lista dos mesclados.")
    ids = [data.keepId] + data.mergeIds
    rows = {r["id"]: r for r in db.execute(
        f"SELECT * FROM {table} WHERE organization_id = ? AND id IN ({','.join('?' * len(ids))})", [org] + ids)}
    if len(rows) != len(set(ids)):
        raise AppError(404, "RECORD_NOT_FOUND", "Algum registro não foi encontrado.")
    keep = rows[data.keepId]

    try:
        # 1) completa os campos vazios do mantido com o que os outros tinham
        fills = {}
        for col in FILL_COLUMNS[entity]:
            if keep[col] in (None, ""):
                for mid in data.mergeIds:
                    if rows[mid][col] not in (None, ""):
                        fills[col] = rows[mid][col]
                        break
        if entity == "companies" and any(rows[m]["type"] == "CLIENTE" for m in data.mergeIds):
            fills["type"] = "CLIENTE"                       # quem já comprou continua cliente
        if entity == "leads":
            firsts = [rows[i]["first_contact_at"] for i in ids if rows[i]["first_contact_at"]]
            lasts = [rows[i]["last_interaction_at"] for i in ids if rows[i]["last_interaction_at"]]
            if firsts:
                fills["first_contact_at"] = min(firsts)
            if lasts:
                fills["last_interaction_at"] = max(lasts)
        if fills:
            db.execute(f"UPDATE {table} SET {', '.join(c + ' = ?' for c in fills)}, updated_at = ? WHERE id = ?",
                       list(fills.values()) + [now_iso(), data.keepId])
        # 2) aponta tudo que era dos mesclados para o mantido
        marks = ",".join("?" * len(data.mergeIds))
        for tbl, col in RELINKS[entity]:
            db.execute(f"UPDATE {tbl} SET {col} = ? WHERE {col} IN ({marks})", [data.keepId] + data.mergeIds)
        # 3) remove os mesclados
        db.execute(f"DELETE FROM {table} WHERE id IN ({marks})", data.mergeIds)
        publish(db, user, "RecordsMerged", {"leads": "lead", "companies": "company", "contacts": "contact"}[entity], data.keepId,
                {"keep": keep["name"], "merged": [rows[m]["name"] for m in data.mergeIds], "mergedIds": data.mergeIds})
        db.commit()
    except Exception:
        db.rollback()
        raise
    if entity == "leads":
        rescore_lead(db, org, data.keepId)
        db.commit()
    return {"keepId": data.keepId, "merged": len(data.mergeIds), "filledFields": sorted(fills)}