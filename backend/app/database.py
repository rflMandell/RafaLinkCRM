import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "rafalink.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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
    (
        "V5__create_companies",
        """
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            name TEXT NOT NULL,
            industry TEXT,
            website TEXT,
            phone TEXT,
            city TEXT,
            notes TEXT,
            type TEXT NOT NULL DEFAULT 'PROSPECT',
            owner_id INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX idx_companies_org_name ON companies(organization_id, name);
        """,
    ),
    (
        "V6__create_contacts",
        """
        CREATE TABLE contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            company_id INTEGER REFERENCES companies(id),
            name TEXT NOT NULL,
            job_title TEXT,
            email TEXT,
            phone TEXT,
            owner_id INTEGER REFERENCES users(id),
            status TEXT NOT NULL DEFAULT 'ATIVO',
            contact_preference TEXT,
            source_lead_id INTEGER REFERENCES leads(id),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX idx_contacts_org_name ON contacts(organization_id, name);
        CREATE INDEX idx_contacts_company ON contacts(company_id);
        """,
    ),
    (
        "V7__add_lead_conversion_links",
        """
        ALTER TABLE leads ADD COLUMN contact_id INTEGER REFERENCES contacts(id);
        ALTER TABLE leads ADD COLUMN company_id INTEGER REFERENCES companies(id);
        """,
    ),
    (
        "V8__create_pipelines",
        """
        CREATE TABLE pipelines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            name TEXT NOT NULL,
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        """,
    ),
    (
        "V9__create_pipeline_stages",
        """
        CREATE TABLE pipeline_stages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_id INTEGER NOT NULL REFERENCES pipelines(id),
            name TEXT NOT NULL,
            position INTEGER NOT NULL,
            probability INTEGER NOT NULL,
            kind TEXT NOT NULL DEFAULT 'OPEN'
        );
        CREATE INDEX idx_stages_pipeline ON pipeline_stages(pipeline_id, position);
        """,
    ),
    (
        "V10__create_opportunities",
        """
        CREATE TABLE opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            title TEXT NOT NULL,
            value REAL NOT NULL DEFAULT 0,
            probability INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'ABERTA',
            pipeline_id INTEGER NOT NULL REFERENCES pipelines(id),
            stage_id INTEGER NOT NULL REFERENCES pipeline_stages(id),
            company_id INTEGER REFERENCES companies(id),
            contact_id INTEGER REFERENCES contacts(id),
            owner_id INTEGER REFERENCES users(id),
            lead_id INTEGER REFERENCES leads(id),
            expected_close_date TEXT,
            realized_value REAL,
            lost_reason TEXT,
            notes TEXT,
            closed_at TEXT,
            stage_changed_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX idx_opps_org_pipeline ON opportunities(organization_id, pipeline_id, stage_id);
        CREATE INDEX idx_opps_company ON opportunities(company_id);
        """,
    ),
    (
        "V11__create_opportunity_history",
        """
        CREATE TABLE opportunity_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
            user_id INTEGER REFERENCES users(id),
            from_stage TEXT,
            to_stage TEXT NOT NULL,
            probability INTEGER,
            note TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX idx_opp_history ON opportunity_history(opportunity_id);
        """,
    ),
    (
        "V12__add_lead_opportunity_link",
        """
        ALTER TABLE leads ADD COLUMN opportunity_id INTEGER REFERENCES opportunities(id);
        """,
    ),
    (
        "V13__create_activities",
        """
        CREATE TABLE activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'PENDENTE',
            due_at TEXT NOT NULL,
            completed_at TEXT,
            owner_id INTEGER REFERENCES users(id),
            created_by INTEGER REFERENCES users(id),
            lead_id INTEGER REFERENCES leads(id),
            contact_id INTEGER REFERENCES contacts(id),
            company_id INTEGER REFERENCES companies(id),
            opportunity_id INTEGER REFERENCES opportunities(id),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX idx_activities_org_due ON activities(organization_id, status, due_at);
        CREATE INDEX idx_activities_lead ON activities(lead_id);
        CREATE INDEX idx_activities_contact ON activities(contact_id);
        CREATE INDEX idx_activities_company ON activities(company_id);
        CREATE INDEX idx_activities_opportunity ON activities(opportunity_id);
        """,
    ),
    (
        "V14__create_campaigns",
        """
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            name TEXT NOT NULL,
            channel TEXT,
            status TEXT NOT NULL DEFAULT 'RASCUNHO',
            budget REAL NOT NULL DEFAULT 0,
            cost REAL NOT NULL DEFAULT 0,
            start_date TEXT,
            end_date TEXT,
            description TEXT,
            owner_id INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX idx_campaigns_org ON campaigns(organization_id, status);
        """,
    ),
    (
        "V15__add_campaign_attribution",
        """
        ALTER TABLE leads ADD COLUMN campaign_id INTEGER REFERENCES campaigns(id);
        ALTER TABLE leads ADD COLUMN first_contact_at TEXT;
        ALTER TABLE opportunities ADD COLUMN campaign_id INTEGER REFERENCES campaigns(id);
        UPDATE leads SET first_contact_at = last_interaction_at WHERE last_interaction_at IS NOT NULL;
        CREATE INDEX idx_leads_campaign ON leads(campaign_id);
        CREATE INDEX idx_opps_campaign ON opportunities(campaign_id);
        """,
    ),
    (
        "V16__create_goals",
        """
        CREATE TABLE goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            owner_id INTEGER REFERENCES users(id),
            metric TEXT NOT NULL,
            period_type TEXT NOT NULL,
            period_start TEXT NOT NULL,
            target REAL NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX uq_goals_scope
            ON goals(organization_id, COALESCE(owner_id, 0), metric, period_type, period_start);
        """,
    ),
    (
        "V17__create_sla_policies",
        """
        CREATE TABLE sla_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL REFERENCES organizations(id),
            kind TEXT NOT NULL,
            threshold REAL NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL,
            UNIQUE (organization_id, kind)
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