import unicodedata

from fastapi import APIRouter, Depends, Query

from ..database import get_db
from ..security import get_current_user

router = APIRouter(prefix="/search", tags=["Busca global"])


def _fold(value) -> str:
    """minúsculas e sem acentos (a busca 'joao' acha 'João')."""
    return unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()


def _like(term: str) -> str:
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


# (chave, rótulo, SQL, quantidade de filtros LIKE, página de destino)
GROUPS = [
    ("leads", "Leads",
     "SELECT id, name AS title, COALESCE(company, email, '') AS sub FROM leads "
     "WHERE organization_id = ? AND (fold(name) LIKE ? ESCAPE '\\' OR fold(email) LIKE ? ESCAPE '\\' "
     "OR fold(phone) LIKE ? ESCAPE '\\' OR fold(company) LIKE ? ESCAPE '\\') ORDER BY updated_at DESC LIMIT ?",
     4, "lead.html?id="),
    ("companies", "Empresas",
     "SELECT id, name AS title, COALESCE(city, industry, '') AS sub FROM companies "
     "WHERE organization_id = ? AND (fold(name) LIKE ? ESCAPE '\\' OR fold(website) LIKE ? ESCAPE '\\' "
     "OR fold(phone) LIKE ? ESCAPE '\\' OR fold(city) LIKE ? ESCAPE '\\') ORDER BY name LIMIT ?",
     4, "company.html?id="),
    ("contacts", "Contatos",
     "SELECT id, name AS title, COALESCE(job_title, email, '') AS sub FROM contacts "
     "WHERE organization_id = ? AND (fold(name) LIKE ? ESCAPE '\\' OR fold(email) LIKE ? ESCAPE '\\' "
     "OR fold(phone) LIKE ? ESCAPE '\\' OR fold(job_title) LIKE ? ESCAPE '\\') ORDER BY name LIMIT ?",
     4, "contact.html?id="),
    ("opportunities", "Oportunidades",
     "SELECT id, title, status AS sub FROM opportunities "
     "WHERE organization_id = ? AND (fold(title) LIKE ? ESCAPE '\\' OR fold(notes) LIKE ? ESCAPE '\\') "
     "ORDER BY updated_at DESC LIMIT ?",
     2, "opportunity.html?id="),
    ("campaigns", "Campanhas",
     "SELECT id, name AS title, COALESCE(channel, '') AS sub FROM campaigns "
     "WHERE organization_id = ? AND (fold(name) LIKE ? ESCAPE '\\' OR fold(description) LIKE ? ESCAPE '\\') "
     "ORDER BY name LIMIT ?",
     2, "campaign.html?id="),
]


@router.get("")
def search(q: str = Query("", max_length=80), limit: int = Query(5, ge=1, le=10),
           db=Depends(get_db), user=Depends(get_current_user)):
    term = _fold(q).strip()
    if len(term) < 2:
        return {"query": q, "groups": [], "total": 0}
    db.create_function("fold", 1, _fold)
    pattern = _like(term)
    groups, total = [], 0
    for key, label, sql, n, href in GROUPS:
        rows = db.execute(sql, [user["organization_id"]] + [pattern] * n + [limit]).fetchall()
        if rows:
            total += len(rows)
            groups.append({"key": key, "label": label, "items": [
                {"id": r["id"], "title": r["title"], "subtitle": r["sub"], "href": f"{href}{r['id']}"} for r in rows]})
    return {"query": q, "groups": groups, "total": total}