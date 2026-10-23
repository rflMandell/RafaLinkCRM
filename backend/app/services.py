"""Regras e helpers compartilhados entre os módulos (leads, empresas, contatos...)."""
from .database import now_iso
from .errors import AppError
from .events import publish
from datetime import datetime, timezone

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


def convert_lead(db, user, lead) -> tuple[int, int | None, int | None]:
    """RN04: transforma o lead em contato, empresa (se informada) e oportunidade.
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
    publish(db, user, "ContactCreated", "contact", contact_id,
            {"leadId": lead["id"], "origin": "lead_conversion"})

    # Oportunidade na primeira etapa do pipeline padrão (valor 0: o vendedor ajusta depois)
    opportunity_id = None
    pipeline = get_default_pipeline(db, user["organization_id"])
    stage = first_open_stage(db, pipeline["id"]) if pipeline else None
    if stage:
        cur = db.execute(
            "INSERT INTO opportunities(organization_id, title, value, probability, status, "
            "pipeline_id, stage_id, company_id, contact_id, owner_id, lead_id, campaign_id, "
            "stage_changed_at, created_at, updated_at) "
            "VALUES (?, ?, 0, ?, 'ABERTA', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user["organization_id"], f"Oportunidade - {base}", stage["probability"],
                stage["pipeline_id"], stage["id"], company_id, contact_id, owner_id,
                lead["id"], lead["campaign_id"], now, now, now,
            ),
        )

    db.execute(
        "UPDATE leads SET contact_id = ?, company_id = ?, opportunity_id = ? WHERE id = ?",
        (contact_id, company_id, opportunity_id, lead["id"]),
    )
    return contact_id, company_id, opportunity_id

# ---------- Pipelines ----------
# nome da etapa, probabilidade, tipo (OPEN = em andamento, WON = ganho, LOST = perdido)
DEFAULT_STAGES = [
    ("Novo Lead", 10, "OPEN"),
    ("Qualificado", 25, "OPEN"),
    ("Reunião", 40, "OPEN"),
    ("Proposta", 60, "OPEN"),
    ("Negociação", 80, "OPEN"),
    ("Ganho", 100, "WON"),
    ("Perdido", 0, "LOST"),
]


def create_pipeline(db, org_id: int, name: str, stages: list, is_default: bool = False) -> int:
    cur = db.execute(
        "INSERT INTO pipelines(organization_id, name, is_default, created_at) VALUES (?, ?, ?, ?)",
        (org_id, name.strip(), 1 if is_default else 0, now_iso()),
    )
    pipeline_id = cur.lastrowid
    for position, (stage_name, probability, kind) in enumerate(stages):
        db.execute(
            "INSERT INTO pipeline_stages(pipeline_id, name, position, probability, kind) "
            "VALUES (?, ?, ?, ?, ?)",
            (pipeline_id, stage_name, position, probability, kind),
        )
    return pipeline_id


def get_pipeline(db, org_id: int, pipeline_id: int):
    return db.execute(
        "SELECT * FROM pipelines WHERE id = ? AND organization_id = ?", (pipeline_id, org_id)
    ).fetchone()


def get_default_pipeline(db, org_id: int):
    return db.execute(
        "SELECT * FROM pipelines WHERE organization_id = ? ORDER BY is_default DESC, id LIMIT 1",
        (org_id,),
    ).fetchone()


def first_open_stage(db, pipeline_id: int):
    return db.execute(
        "SELECT * FROM pipeline_stages WHERE pipeline_id = ? AND kind = 'OPEN' "
        "ORDER BY position LIMIT 1",
        (pipeline_id,),
    ).fetchone()


def list_stages(db, pipeline_id: int) -> list[dict]:
    rows = db.execute(
        "SELECT id, name, position, probability, kind FROM pipeline_stages "
        "WHERE pipeline_id = ? ORDER BY position",
        (pipeline_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def pipeline_dto(db, p) -> dict:
    return {
        "id": p["id"],
        "name": p["name"],
        "isDefault": bool(p["is_default"]),
        "stages": list_stages(db, p["id"]),
    }


def list_pipelines(db, org_id: int) -> list[dict]:
    rows = db.execute(
        "SELECT * FROM pipelines WHERE organization_id = ? ORDER BY is_default DESC, name",
        (org_id,),
    ).fetchall()
    return [pipeline_dto(db, p) for p in rows]


def add_history(db, user, opportunity_id: int, from_stage, to_stage: str, probability: int, note=None) -> None:
    db.execute(
        "INSERT INTO opportunity_history(opportunity_id, user_id, from_stage, to_stage, "
        "probability, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (opportunity_id, user["id"], from_stage, to_stage, probability, note, now_iso()),
    )
    
def to_utc_iso(dt: datetime) -> str:
    """Normaliza qualquer data/hora para UTC no formato único usado no banco.
    Datas sem fuso são tratadas como UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")

def check_campaign(db, user, campaign_id: int | None, must_be_open: bool = False):
    """Garante que a campanha existe na organização. Campanha encerrada não recebe novos leads."""
    if campaign_id is None:
        return None
    row = db.execute(
        "SELECT id, name, status FROM campaigns WHERE id = ? AND organization_id = ?",
        (campaign_id, user["organization_id"]),
    ).fetchone()
    if row is None:
        raise AppError(422, "CAMPAIGN_NOT_FOUND", "Campanha inválida.")
    if must_be_open and row["status"] == "ENCERRADA":
        raise AppError(422, "CAMPAIGN_CLOSED", "A campanha está encerrada e não aceita novos leads.")
    return row