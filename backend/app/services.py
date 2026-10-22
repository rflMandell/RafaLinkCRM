"""Regras e helpers compartilhados entre os módulos (leads, empresas, contatos...)."""
from .database import now_iso
from .errors import AppError
from .events import publish

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def check_owner(db, user, owner_id: int | None) -> None:
    if owner_id is None:
        return
    ok = db.execute(
        "SELECT 1 FROM users WHERE id = ? AND organization_id = ? AND active = 1",
        (owner_id, user["organization_id"]),
    ).fetchone()
    if ok is None:
        raise AppError(422, "OWNER_NOT_FOUND", "Responsável inválido.")


def parse_sort(sort: str, allowed: dict) -> tuple[str, str]:
    """Valida "campo,asc|desc" contra uma lista fixa de colunas (evita SQL injection)."""
    field, _, direction = sort.partition(",")
    column = allowed.get(field)
    if column is None or direction.lower() not in ("", "asc", "desc"):
        raise AppError(400, "INVALID_SORT", "Ordenação inválida.")
    return column, ("DESC" if direction.lower() == "desc" else "ASC")


def find_or_create_company(db, user, name: str, owner_id: int | None = None) -> tuple[int, bool]:
    """Devolve (id, criada_agora). Reaproveita empresa de mesmo nome."""
    row = db.execute(
        "SELECT id FROM companies WHERE organization_id = ? AND lower(name) = lower(?)",
        (user["organization_id"], name.strip()),
    ).fetchone()
    if row:
        return row["id"], False

    now = now_iso()
    cur = db.execute(
        "INSERT INTO companies(organization_id, name, type, owner_id, created_at, updated_at) "
        "VALUES (?, ?, 'PROSPECT', ?, ?, ?)",
        (user["organization_id"], name.strip(), owner_id, now, now),
    )
    publish(db, user, "CompanyCreated", "company", cur.lastrowid,
            {"name": name.strip(), "origin": "lead_conversion"})
    return cur.lastrowid, True


def convert_lead(db, user, lead) -> tuple[int, int | None]:
    """RN04: transforma o lead em contato (e empresa, se informada).
    Não faz commit: quem chama controla a transação."""
    owner_id = lead["owner_id"] or user["id"]

    company_id = None
    if lead["company"] and lead["company"].strip():
        company_id, _ = find_or_create_company(db, user, lead["company"], owner_id)

    now = now_iso()
    cur = db.execute(
        "INSERT INTO contacts(organization_id, company_id, name, email, phone, owner_id, "
        "status, source_lead_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'ATIVO', ?, ?, ?)",
        (
            user["organization_id"], company_id, lead["name"], lead["email"],
            lead["phone"], owner_id, lead["id"], now, now,
        ),
    )
    contact_id = cur.lastrowid
    db.execute(
        "UPDATE leads SET contact_id = ?, company_id = ? WHERE id = ?",
        (contact_id, company_id, lead["id"]),
    )
    publish(db, user, "ContactCreated", "contact", contact_id,
            {"leadId": lead["id"], "origin": "lead_conversion"})
    return contact_id, company_id