import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "rafalink.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """Dependência do FastAPI: abre e fecha a conexão a cada requisição."""
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# Migrations simples
# Para novas tabelas nas próximas etapas, basta adicionar um item no fim da lista.
MIGRATIONS = [
    (
        "V1__create_organizations",
        """
        CREATE TABLE organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
    ),
    (
        "V2__create_users",
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
    ),
        (
        "V3__create_leads",
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            company TEXT,
            source TEXT,
            channel TEXT,
            owner_id INTEGER REFERENCES users(id),
            score INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'NOVO',
            lost_reason TEXT,
            next_action TEXT,
            last_interaction_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX idx_leads_org_status ON leads(organization_id, status);
        """,
    ),
    (
        "V4__create_domain_events",
        """
        CREATE TABLE domain_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            user_id INTEGER REFERENCES users(id),
            type TEXT NOT NULL,
            entity TEXT NOT NULL,
            entity_id INTEGER,
            payload TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        """,
    ),
]


def run_migrations() -> None:
    conn = get_conn()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               version TEXT PRIMARY KEY,
               applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
           )"""
    )
    applied = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
    for version, sql in MIGRATIONS:
        if version not in applied:
            conn.executescript(sql)
            conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
            conn.commit()
            print(f"[migration] aplicada: {version}")
    conn.close()