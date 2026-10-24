"""Etapa 10: segunda organização de demonstração, para provar o isolamento entre empresas (multi-tenancy).
Idempotente: só cria se ainda não existir a organização "Outra Empresa (demo)"."""
from .database import now_iso
from .security import hash_password

ORG_NAME = "Outra Empresa (demo)"


def seed_tenants(conn) -> None:
    if conn.execute("SELECT 1 FROM organizations WHERE name = ?", (ORG_NAME,)).fetchone():
        return
    if conn.execute("SELECT COUNT(*) FROM organizations").fetchone()[0] == 0:
        return                                        # a organização principal ainda não existe
    cur = conn.execute("INSERT INTO organizations(name) VALUES (?)", (ORG_NAME,))
    org = cur.lastrowid
    admin = conn.execute(
        "INSERT INTO users(organization_id, name, email, password_hash, role) VALUES (?, ?, ?, ?, 'ADMIN')",
        (org, "Admin Outra Empresa", "admin@outraempresa.com", hash_password("admin123"))).lastrowid
    now = now_iso()
    co = conn.execute(
        "INSERT INTO companies(organization_id, name, type, owner_id, created_at, updated_at) VALUES (?, 'Mercado Sol', 'CLIENTE', ?, ?, ?)",
        (org, admin, now, now)).lastrowid
    conn.execute(
        "INSERT INTO contacts(organization_id, company_id, name, email, owner_id, status, created_at, updated_at) "
        "VALUES (?, ?, 'Helena Prado', 'helena@mercadosol.com', ?, 'ATIVO', ?, ?)", (org, co, admin, now, now))
    for name, email in [("Maria Souza", "maria.souza@exemplo.com"), ("Otávio Reis", "otavio@mercadosol.com")]:
        conn.execute(
            "INSERT INTO leads(organization_id, name, email, owner_id, score, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 0, 'NOVO', ?, ?)", (org, name, email, admin, now, now))
    conn.commit()
    print("[seed] organização de demonstração 2 criada (admin@outraempresa.com / admin123)")