"""Dados de demonstração da Etapa 6: campanhas, atribuição de leads e vendas ganhas.
É idempotente: só cria algo se ainda não existir nenhuma campanha."""
import random
from datetime import datetime, timedelta, timezone

# nome, canal, status, orçamento, investido, início (dias atrás), fim (dias à frente), descrição
CAMPAIGNS = [
    ("Black Friday 2026", "EMAIL", "ATIVA", 15000, 11800, 20, 38, "Sequência de e-mails com oferta de fim de ano."),
    ("Webinar CRM na Prática", "EVENTO", "ENCERRADA", 8000, 7200, 70, -35, "Webinar ao vivo com demonstração do produto."),
    ("Anúncios LinkedIn Q4", "REDES_SOCIAIS", "ATIVA", 20000, 9500, 45, 40, "Anúncios segmentados para diretores de TI."),
    ("Indicação Premiada", "OUTROS", "ATIVA", 5000, 2100, 60, 30, "Bônus para clientes que indicam novos clientes."),
    ("Google Ads Institucional", "SITE", "PAUSADA", 12000, 6400, 55, 10, "Anúncios de busca com a marca."),
    ("Newsletter Mensal", "EMAIL", "RASCUNHO", 1500, 0, 0, 60, "Conteúdo mensal para a base de contatos."),
]

# lead existente (pelo nome) -> campanha
LEAD_CAMPAIGN = {
    "Maria Souza": "Black Friday 2026", "Camila Ribeiro": "Black Friday 2026",
    "João Silva": "Google Ads Institucional",
    "Carlos Oliveira": "Webinar CRM na Prática", "Juliana Martins": "Webinar CRM na Prática",
    "Pedro Santos": "Webinar CRM na Prática",
    "Ana Paula Lima": "Anúncios LinkedIn Q4", "Ricardo Alves": "Anúncios LinkedIn Q4",
    "Marcos Pereira": "Anúncios LinkedIn Q4",
    "Fernanda Costa": "Indicação Premiada", "Lucas Ferreira": "Indicação Premiada",
}

# oportunidade existente (pelo título) -> campanha
OPP_CAMPAIGN = {
    "Contrato de Software": "Black Friday 2026", "Licenças Corporativas": "Black Friday 2026",
    "Contrato Anual Bela Flor": "Webinar CRM na Prática", "Pacote de Treinamento": "Webinar CRM na Prática",
    "Sistema de Gestão Escolar": "Webinar CRM na Prática",
    "Reforma da Sede": "Anúncios LinkedIn Q4",
    "Plano de Saúde Corporativo": "Indicação Premiada",
    "Totem de Autoatendimento": "Google Ads Institucional",
}

# campanha -> leads extras e valores das vendas ganhas extras
EXTRA = {
    "Black Friday 2026": (6, [18000, 26000]),
    "Webinar CRM na Prática": (4, [12000]),
    "Anúncios LinkedIn Q4": (6, [30000]),
    "Indicação Premiada": (3, [9000, 14000]),
    "Google Ads Institucional": (5, [4500]),
}

FIRST = ["Alice", "Bruno", "Cíntia", "Diego", "Elisa", "Fábio", "Gabriela", "Henrique", "Isabela",
         "Jorge", "Karina", "Leandro", "Marina", "Nelson", "Olívia", "Paulo", "Queila", "Rodrigo",
         "Sabrina", "Tiago", "Valéria", "Wagner"]
LAST = ["Andrade", "Barbosa", "Cardoso", "Dias", "Esteves", "Fonseca", "Gomes", "Holanda", "Ibrahim",
        "Jardim", "Klein", "Leal", "Moraes", "Nogueira", "Oliveira", "Pires", "Queiroz", "Ramos"]
SOURCE_BY_CHANNEL = {"EMAIL": "E-mail marketing", "EVENTO": "Evento", "REDES_SOCIAIS": "LinkedIn",
                     "OUTROS": "Indicação", "SITE": "Anúncio"}
LEAD_STATUSES = ["NOVO", "EM_CONTATO", "QUALIFICADO", "OPORTUNIDADE", "PERDIDO", "ARQUIVADO"]
LEAD_WEIGHTS = [3, 3, 2, 1, 2, 1]


def seed_campaigns(conn) -> None:
    # Leads antigos ganham "primeiro contato" aproximado pela última interação.
    conn.execute(
        "UPDATE leads SET first_contact_at = last_interaction_at "
        "WHERE first_contact_at IS NULL AND last_interaction_at IS NOT NULL"
    )
    conn.commit()

    if conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0] > 0:
        return
    org = conn.execute("SELECT id FROM organizations ORDER BY id LIMIT 1").fetchone()
    if org is None:
        return
    org_id = org["id"]
    owners = [r["id"] for r in conn.execute(
        "SELECT id FROM users WHERE organization_id = ? ORDER BY id", (org_id,))]

    rng = random.Random(42)  # mesma demonstração a cada instalação
    now = datetime.now(timezone.utc)
    iso = lambda dt: dt.isoformat(timespec="seconds")

    # 1) Campanhas
    ids, channels = {}, {}
    for i, (name, channel, status, budget, cost, started, ends, desc) in enumerate(CAMPAIGNS):
        created = iso(now - timedelta(days=started + 2))
        cur = conn.execute(
            "INSERT INTO campaigns(organization_id, name, channel, status, budget, cost, start_date, "
            "end_date, description, owner_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (org_id, name, channel, status, budget, cost,
             (now - timedelta(days=started)).date().isoformat(),
             (now + timedelta(days=ends)).date().isoformat(),
             desc, owners[i % len(owners)], created, created),
        )
        ids[name], channels[name] = cur.lastrowid, channel

    # 2) Atribui leads e oportunidades que já existiam
    for lead, campaign in LEAD_CAMPAIGN.items():
        conn.execute("UPDATE leads SET campaign_id = ? WHERE organization_id = ? AND name = ?",
                     (ids[campaign], org_id, lead))
    for title, campaign in OPP_CAMPAIGN.items():
        conn.execute("UPDATE opportunities SET campaign_id = ? WHERE organization_id = ? AND title = ?",
                     (ids[campaign], org_id, title))

    # Vendas antigas da demo nasceram e fecharam no mesmo instante: dá a elas um ciclo realista.
    for r in conn.execute("SELECT id, closed_at FROM opportunities WHERE status = 'GANHA' "
                          "AND closed_at IS NOT NULL AND created_at >= closed_at").fetchall():
        closed = datetime.fromisoformat(r["closed_at"])
        conn.execute("UPDATE opportunities SET created_at = ? WHERE id = ?",
                     (iso(closed - timedelta(days=28)), r["id"]))

    # 3) Leads extras (variam no tempo para o gráfico de tendência ter forma)
    def new_lead(campaign, status, created):
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        slug = name.lower().replace(" ", ".").replace("í", "i").replace("á", "a").replace("é", "e") \
                   .replace("ê", "e").replace("ô", "o").replace("ç", "c").replace("ú", "u")
        first_contact = None
        if status not in ("NOVO", "ARQUIVADO"):
            first_contact = min(now, created + timedelta(hours=rng.randint(1, 60)))
        channel = channels[campaign]
        cur = conn.execute(
            "INSERT INTO leads(organization_id, name, email, company, source, channel, owner_id, score, "
            "status, lost_reason, last_interaction_at, first_contact_at, campaign_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (org_id, name, f"{slug}@exemplo.com", f"{name.split()[1]} & Cia",
             SOURCE_BY_CHANNEL.get(channel, "Outros"), channel, rng.choice(owners), rng.randint(20, 95),
             status, "Sem orçamento no momento" if status == "PERDIDO" else None,
             iso(first_contact) if first_contact else None,
             iso(first_contact) if first_contact else None,
             ids[campaign], iso(created), iso(first_contact or created)),
        )
        return cur.lastrowid

    for campaign, (n_leads, _) in EXTRA.items():
        for _i in range(n_leads):
            created = now - timedelta(days=rng.randint(0, 58), hours=rng.randint(0, 20))
            new_lead(campaign, rng.choices(LEAD_STATUSES, LEAD_WEIGHTS)[0], created)

    # 4) Vendas ganhas extras (lead CONVERTIDO + oportunidade GANHA no pipeline padrão)
    stage = conn.execute(
        "SELECT s.id, s.pipeline_id, s.name FROM pipeline_stages s JOIN pipelines p ON p.id = s.pipeline_id "
        "WHERE p.organization_id = ? AND p.is_default = 1 AND s.kind = 'WON' ORDER BY s.position LIMIT 1",
        (org_id,),
    ).fetchone()
    if stage is not None:
        for campaign, (_, wins) in EXTRA.items():
            for value in wins:
                closed = now - timedelta(days=rng.randint(2, 50), hours=rng.randint(0, 12))
                opp_created = closed - timedelta(days=rng.randint(5, 22))
                lead_created = opp_created - timedelta(days=rng.randint(1, 5))
                lead_id = new_lead(campaign, "CONVERTIDO", lead_created)
                owner = rng.choice(owners)
                lead_name = conn.execute("SELECT name FROM leads WHERE id = ?", (lead_id,)).fetchone()["name"]
                cur = conn.execute(
                    "INSERT INTO opportunities(organization_id, title, value, probability, status, pipeline_id, "
                    "stage_id, owner_id, lead_id, campaign_id, realized_value, closed_at, stage_changed_at, "
                    "created_at, updated_at) VALUES (?, ?, ?, 100, 'GANHA', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (org_id, f"Venda - {lead_name}", value, stage["pipeline_id"], stage["id"], owner,
                     lead_id, ids[campaign], value, iso(closed), iso(closed), iso(opp_created), iso(closed)),
                )
                conn.execute(
                    "INSERT INTO opportunity_history(opportunity_id, user_id, from_stage, to_stage, "
                    "probability, note, created_at) VALUES (?, ?, NULL, ?, 100, 'Venda ganha (demo)', ?)",
                    (cur.lastrowid, owner, stage["name"], iso(closed)),
                )
                conn.execute("UPDATE leads SET opportunity_id = ? WHERE id = ?", (cur.lastrowid, lead_id))

    conn.commit()
    print("[seed] campanhas e dados de atribuição criados")