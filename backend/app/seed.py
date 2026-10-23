from datetime import datetime, timedelta, timezone

from .database import get_conn, now_iso
from .security import hash_password
from .services import DEFAULT_STAGES, create_pipeline
from .seed_campaigns import seed_campaigns
from .seed_goals import seed_goals

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

RENEWAL_STAGES = [
    ("Em análise", 30, "OPEN"),
    ("Proposta", 60, "OPEN"),
    ("Aprovação", 85, "OPEN"),
    ("Renovado", 100, "WON"),
    ("Não renovado", 0, "LOST"),
]

# título, valor, pipeline, etapa, empresa, contato, dias até o fechamento, motivo da perda
DEMO_OPPORTUNITIES = [
    ("Contrato de Software", 80000, "Vendas", "Proposta", "Empresa XYZ", "Patrícia Nunes", 40, None),
    ("Licenças Corporativas", 45000, "Vendas", "Negociação", "Empresa XYZ", "André Almeida", 20, None),
    ("Reforma da Sede", 250000, "Vendas", "Reunião", "Construtora Horizonte", "Roberto Campos", 60, None),
    ("Plano de Saúde Corporativo", 32000, "Vendas", "Qualificado", "Clínica Vida Plena", "Helena Duarte", 35, None),
    ("Sistema de Gestão Escolar", 58000, "Vendas", "Proposta", "Escola Novo Saber", "Sandra Lopes", 45, None),
    ("Totem de Autoatendimento", 18500, "Vendas", "Novo Lead", "Mercado Bom Preço", "Paulo Mendes", 50, None),
    ("Expansão da Loja Online", 27000, "Vendas", "Novo Lead", "Bela Flor", "Juliana Martins", 30, None),
    ("Contrato Anual Bela Flor", 40000, "Vendas", "Ganho", "Bela Flor", "Juliana Martins", 0, None),
    ("Pacote de Treinamento", 12000, "Vendas", "Perdido", "Escola Novo Saber", "Sandra Lopes", 0, "Orçamento cortado"),
    ("Renovação Clínica Vida Plena", 22000, "Renovações", "Proposta", "Clínica Vida Plena", "Marcelo Tavares", 25, None),
]

# tipo, título, descrição, dias (negativo = passado), hora (UTC), status,
# lead, contato, empresa, oportunidade
DEMO_ACTIVITIES = [
    ("LIGACAO", "Ligação de qualificação", "Cliente demonstrou interesse na versão corporativa.", -2, 14, "CONCLUIDA", "Maria Souza", None, None, None),
    ("EMAIL", "Proposta comercial enviada", "Enviada proposta com 3 opções de plano.", -1, 17, "CONCLUIDA", "Maria Souza", None, None, None),
    ("REUNIAO", "Reunião de descoberta", "Levantamento de requisitos com a equipe de TI.", -4, 15, "CONCLUIDA", "João Silva", None, None, None),
    ("NOTA", "Perfil do cliente", "Decisor é o diretor financeiro; prefere contato por e-mail.", -3, 16, "CONCLUIDA", None, "André Almeida", "Empresa XYZ", None),
    ("LIGACAO", "Alinhamento de prazos", "Combinado o envio do contrato até sexta.", -1, 19, "CONCLUIDA", None, "Patrícia Nunes", "Empresa XYZ", "Contrato de Software"),
    ("FOLLOW_UP", "Follow-up da proposta", "Perguntar se houve retorno do jurídico.", 0, 18, "PENDENTE", None, "Patrícia Nunes", "Empresa XYZ", "Contrato de Software"),
    ("REUNIAO", "Apresentação final da proposta", "Reunião com Patrícia e André.", 2, 14, "PENDENTE", None, "Patrícia Nunes", "Empresa XYZ", "Contrato de Software"),
    ("TAREFA", "Preparar contrato para assinatura", "Revisar as cláusulas de SLA.", -1, 13, "PENDENTE", None, None, "Empresa XYZ", "Licenças Corporativas"),
    ("LIGACAO", "Primeiro contato", "Ligar e apresentar a empresa.", 0, 17, "PENDENTE", "Ana Paula Lima", None, None, None),
    ("WHATSAPP", "Enviar material institucional", None, 1, 15, "PENDENTE", "Carlos Oliveira", None, None, None),
    ("REUNIAO", "Visita técnica na obra", "Visita com o engenheiro chefe.", 4, 13, "PENDENTE", None, "Roberto Campos", "Construtora Horizonte", "Reforma da Sede"),
    ("TAREFA", "Elaborar orçamento da reforma", None, 3, 16, "PENDENTE", None, None, "Construtora Horizonte", "Reforma da Sede"),
    ("FOLLOW_UP", "Retomar contato", "Sem resposta há 5 dias.", -3, 15, "PENDENTE", "Ricardo Alves", None, None, None),
    ("EMAIL", "Enviar proposta de renovação", None, 1, 14, "PENDENTE", None, "Marcelo Tavares", "Clínica Vida Plena", "Renovação Clínica Vida Plena"),
    ("REUNIAO", "Reunião de kickoff", "Início do contrato anual.", -10, 14, "CONCLUIDA", None, "Juliana Martins", "Bela Flor", "Contrato Anual Bela Flor"),
    ("NOTA", "Cliente satisfeito", "Elogiou o atendimento da equipe.", -6, 16, "CONCLUIDA", None, "Helena Duarte", "Clínica Vida Plena", None),
    ("LIGACAO", "Ligação de reagendamento", "Cliente pediu para remarcar.", -2, 18, "CANCELADA", "Pedro Santos", None, None, None),
    ("REUNIAO", "Reunião mensal de acompanhamento", None, 8, 14, "PENDENTE", None, "Marcelo Tavares", "Clínica Vida Plena", None),
    ("TAREFA", "Atualizar planilha de metas", None, 5, 17, "PENDENTE", None, None, None, None),
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

    org_id = conn.execute("SELECT id FROM organizations ORDER BY id LIMIT 1").fetchone()["id"]

    if conn.execute("SELECT COUNT(*) FROM pipelines").fetchone()[0] == 0:
        create_pipeline(conn, org_id, "Vendas", DEFAULT_STAGES, is_default=True)
        create_pipeline(conn, org_id, "Renovações", RENEWAL_STAGES)
        conn.commit()
        print("[seed] pipelines de demonstração criados")

    if conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0] == 0:
        owner_ids = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM users WHERE organization_id = ? ORDER BY id", (org_id,)
            )
        ]
        now = datetime.now(timezone.utc)
        status_by_kind = {"OPEN": "ABERTA", "WON": "GANHA", "LOST": "PERDIDA"}

        for i, (title, value, pipeline, stage_name, company, contact, days, reason) in enumerate(DEMO_OPPORTUNITIES):
            stage = conn.execute(
                "SELECT s.id, s.name, s.pipeline_id, s.probability, s.kind FROM pipeline_stages s "
                "JOIN pipelines p ON p.id = s.pipeline_id "
                "WHERE p.organization_id = ? AND p.name = ? AND s.name = ?",
                (org_id, pipeline, stage_name),
            ).fetchone()
            if stage is None:
                continue
            company_row = conn.execute(
                "SELECT id FROM companies WHERE organization_id = ? AND name = ?", (org_id, company)
            ).fetchone()
            contact_row = conn.execute(
                "SELECT id FROM contacts WHERE organization_id = ? AND name = ?", (org_id, contact)
            ).fetchone()

            kind = stage["kind"]
            owner = owner_ids[i % len(owner_ids)]
            changed = (now - timedelta(days=i * 3 + 1)).isoformat(timespec="seconds")
            closed = changed if kind != "OPEN" else None
            close_date = (now + timedelta(days=days)).date().isoformat() if kind == "OPEN" else None

            cur = conn.execute(
                "INSERT INTO opportunities(organization_id, title, value, probability, status, pipeline_id, "
                "stage_id, company_id, contact_id, owner_id, expected_close_date, realized_value, "
                "lost_reason, closed_at, stage_changed_at, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    org_id, title, value, stage["probability"], status_by_kind[kind],
                    stage["pipeline_id"], stage["id"],
                    company_row["id"] if company_row else None,
                    contact_row["id"] if contact_row else None,
                    owner, close_date,
                    value if kind == "WON" else None,
                    reason if kind == "LOST" else None,
                    closed, changed, changed, changed,
                ),
            )
            conn.execute(
                "INSERT INTO opportunity_history(opportunity_id, user_id, from_stage, to_stage, "
                "probability, note, created_at) VALUES (?, ?, NULL, ?, ?, 'Oportunidade criada', ?)",
                (cur.lastrowid, owner, stage["name"], stage["probability"], changed),
            )
        conn.commit()
        print("[seed] oportunidades de demonstração criadas")
    
    if conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0] == 0:
        owner_ids = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM users WHERE organization_id = ? ORDER BY id", (org_id,)
            )
        ]
        now = datetime.now(timezone.utc)

        def find(table, col, value):
            if not value:
                return None
            row = conn.execute(
                f"SELECT id FROM {table} WHERE organization_id = ? AND {col} = ?", (org_id, value)
            ).fetchone()
            return row["id"] if row else None

        for i, (atype, title, desc, days, hour, status, lead, contact, company, opp) in enumerate(DEMO_ACTIVITIES):
            when = now.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=days)
            when_iso = when.isoformat(timespec="seconds")
            created = (min(when, now) - timedelta(days=2)).isoformat(timespec="seconds")
            owner = owner_ids[i % len(owner_ids)]
            conn.execute(
                "INSERT INTO activities(organization_id, type, title, description, status, due_at, "
                "completed_at, owner_id, created_by, lead_id, contact_id, company_id, opportunity_id, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    org_id, atype, title, desc, status, when_iso,
                    when_iso if status == "CONCLUIDA" else None,
                    owner, owner,
                    find("leads", "name", lead), find("contacts", "name", contact),
                    find("companies", "name", company), find("opportunities", "title", opp),
                    created, created,
                ),
            )
        conn.commit()
        print("[seed] atividades de demonstração criadas")
    
    seed_campaigns(conn)
    seed_goals(conn)
    
    conn.close()