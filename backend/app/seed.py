from datetime import datetime, timedelta, timezone

from .database import get_conn, now_iso
from .security import hash_password

# Usuários de demonstração (um por papel). Senhas simples de propósito, só para uso local.
DEMO_USERS = [
    ("Rafael Admin", "admin@rafalink.com", "admin123", "ADMIN"),
    ("Gerente Comercial", "gerente@rafalink.com", "gerente123", "SALES_MANAGER"),
    ("Vendedor Demo", "vendedor@rafalink.com", "vendedor123", "SALES"),
]

# nome, e-mail, telefone, empresa, origem, canal, status, score, próxima ação
DEMO_LEADS = [
    ("Maria Souza", "maria@empresaxyz.com", "11999990001", "Empresa XYZ", "Indicação", "EMAIL", "QUALIFICADO", 87, "Enviar proposta"),
    ("João Silva", "joao@techsul.com", "11999990002", "Tech Sul", "Site", "SITE", "EM_CONTATO", 62, "Agendar reunião"),
    ("Carlos Oliveira", "carlos@aurora.com", "11999990003", "Grupo Aurora", "Evento", "EVENTO", "NOVO", 35, "Primeiro contato"),
    ("Ana Paula Lima", "ana@lumina.com", "11999990004", "Lumina Design", "Anúncio", "REDES_SOCIAIS", "NOVO", 48, "Ligar hoje"),
    ("Fernanda Costa", "fernanda@vertice.com", "11999990005", "Vértice Consultoria", "Indicação", "WHATSAPP", "OPORTUNIDADE", 91, "Negociar prazo"),
    ("Ricardo Alves", "ricardo@norte.com", "11999990006", "Norte Logística", "LinkedIn", "REDES_SOCIAIS", "EM_CONTATO", 55, "Enviar material"),
    ("Juliana Martins", "juliana@belaflor.com", "11999990007", "Bela Flor", "Site", "SITE", "CONVERTIDO", 95, None),
    ("Pedro Santos", "pedro@santosadv.com", "11999990008", "Santos Advogados", "Evento", "EVENTO", "PERDIDO", 28, None),
    ("Camila Ribeiro", "camila@ribeirocorp.com", "11999990009", "Ribeiro Corp", "Anúncio", "EMAIL", "NOVO", 41, "Enviar e-mail de boas-vindas"),
    ("Lucas Ferreira", "lucas@alfa.com", "11999990010", "Alfa Tecnologia", "Indicação", "WHATSAPP", "QUALIFICADO", 79, "Apresentar demo"),
    ("Beatriz Rocha", "beatriz@oldcrm.com", "11999990011", "Old CRM Ltda", "Site", "SITE", "ARQUIVADO", 15, None),
    ("Marcos Pereira", "marcos@pereiraseg.com", "11999990012", "Pereira Seguros", "LinkedIn", "EMAIL", "EM_CONTATO", 58, "Follow-up em 2 dias"),
]

# nome, segmento, site, telefone, cidade, tipo
DEMO_COMPANIES = [
    ("Empresa XYZ", "Tecnologia", "www.empresaxyz.com", "1133330001", "São Paulo", "PROSPECT"),
    ("Bela Flor", "Varejo", "www.belaflor.com", "1133330002", "Campinas", "CLIENTE"),
    ("Construtora Horizonte", "Construção", "www.horizonte.com.br", "1133330003", "Curitiba", "PROSPECT"),
    ("Clínica Vida Plena", "Saúde", "www.vidaplena.com.br", "1133330004", "Belo Horizonte", "CLIENTE"),
    ("Escola Novo Saber", "Educação", "www.novosaber.edu.br", "1133330005", "Porto Alegre", "PROSPECT"),
    ("Mercado Bom Preço", "Varejo", None, "1133330006", "Santos", "PROSPECT"),
]

# nome, cargo, e-mail, telefone, empresa, preferência de contato
DEMO_CONTACTS = [
    ("Patrícia Nunes", "Compras", "patricia@empresaxyz.com", "11988880001", "Empresa XYZ", "EMAIL"),
    ("André Almeida", "Diretor Financeiro", "andre@empresaxyz.com", "11988880002", "Empresa XYZ", "WHATSAPP"),
    ("Juliana Martins", "Gerente", "juliana@belaflor.com", "11999990007", "Bela Flor", "EMAIL"),
    ("Roberto Campos", "Engenheiro Chefe", "roberto@horizonte.com.br", "11988880004", "Construtora Horizonte", "TELEFONE"),
    ("Helena Duarte", "Diretora Clínica", "helena@vidaplena.com.br", "11988880005", "Clínica Vida Plena", "EMAIL"),
    ("Marcelo Tavares", "TI", "marcelo@vidaplena.com.br", "11988880006", "Clínica Vida Plena", "WHATSAPP"),
    ("Sandra Lopes", "Coordenadora", "sandra@novosaber.edu.br", "11988880007", "Escola Novo Saber", "EMAIL"),
    ("Paulo Mendes", "Proprietário", None, "11988880008", "Mercado Bom Preço", "TELEFONE"),
]


def seed() -> None:
    conn = get_conn()

    if conn.execute("SELECT COUNT(*) FROM organizations").fetchone()[0] == 0:
        cur = conn.execute("INSERT INTO organizations(name) VALUES (?)", ("RafaLink Demo",))
        org_id = cur.lastrowid
        for name, email, password, role in DEMO_USERS:
            conn.execute(
                "INSERT INTO users(organization_id, name, email, password_hash, role) "
                "VALUES (?, ?, ?, ?, ?)",
                (org_id, name, email, hash_password(password), role),
            )
        conn.commit()
        print("[seed] organização e usuários de demonstração criados")

    if conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0:
        org_id = conn.execute("SELECT id FROM organizations ORDER BY id LIMIT 1").fetchone()["id"]
        owner_ids = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM users WHERE organization_id = ? ORDER BY id", (org_id,)
            )
        ]
        now = datetime.now(timezone.utc)
        for i, (name, email, phone, company, source, channel, status, score, next_action) in enumerate(DEMO_LEADS):
            created = now - timedelta(days=i * 2 + 1)
            last = None if status == "NOVO" else (created + timedelta(days=1)).isoformat(timespec="seconds")
            created_iso = created.isoformat(timespec="seconds")
            conn.execute(
                "INSERT INTO leads(organization_id, name, email, phone, company, source, channel, "
                "owner_id, score, status, lost_reason, next_action, last_interaction_at, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    org_id, name, email, phone, company, source, channel,
                    owner_ids[i % len(owner_ids)], score, status,
                    "Sem orçamento disponível" if status == "PERDIDO" else None,
                    next_action, last, created_iso, last or created_iso,
                ),
            )
        conn.commit()
        print("[seed] leads de demonstração criados")
        
    if conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 0:
        org_id = conn.execute("SELECT id FROM organizations ORDER BY id LIMIT 1").fetchone()["id"]
        owner_ids = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM users WHERE organization_id = ? ORDER BY id", (org_id,)
            )
        ]
        now = now_iso()

        company_ids = {}
        for i, (name, industry, website, phone, city, ctype) in enumerate(DEMO_COMPANIES):
            cur = conn.execute(
                "INSERT INTO companies(organization_id, name, industry, website, phone, city, "
                "type, owner_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (org_id, name, industry, website, phone, city, ctype,
                 owner_ids[i % len(owner_ids)], now, now),
            )
            company_ids[name] = cur.lastrowid

        for i, (name, job, email, phone, company, pref) in enumerate(DEMO_CONTACTS):
            # Se o contato veio de um lead já convertido, guarda o vínculo nos dois lados
            lead = conn.execute(
                "SELECT id FROM leads WHERE organization_id = ? AND email = ? AND status = 'CONVERTIDO'",
                (org_id, email),
            ).fetchone() if email else None
            cur = conn.execute(
                "INSERT INTO contacts(organization_id, company_id, name, job_title, email, phone, "
                "owner_id, status, contact_preference, source_lead_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'ATIVO', ?, ?, ?, ?)",
                (org_id, company_ids[company], name, job, email, phone,
                 owner_ids[i % len(owner_ids)], pref, lead["id"] if lead else None, now, now),
            )
            if lead:
                conn.execute(
                    "UPDATE leads SET contact_id = ?, company_id = ? WHERE id = ?",
                    (cur.lastrowid, company_ids[company], lead["id"]),
                )
        conn.commit()
        print("[seed] empresas e contatos de demonstração criados")

    conn.close()