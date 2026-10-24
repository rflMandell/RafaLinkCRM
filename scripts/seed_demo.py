"""Etapa 11: gera um volume realista de dados de demonstração (empresas, contatos, leads, oportunidades,
atividades), com datas espalhadas pelos últimos 90 dias e alguns duplicados de propósito.

Uso (o jeito mais fácil): python start.py --demo

Direto, na raiz do projeto, com o ambiente virtual do backend:
    Windows:  backend\\.venv\\Scripts\\python scripts\\seed_demo.py
    Mac:      backend/.venv/bin/python scripts/seed_demo.py

Opções:
    --leads 80   quantos leads criar (padrão 48)
    --force      cria mesmo que os dados de demonstração já existam
    --seed 7     muda a "semente" aleatória (outro conjunto de nomes e datas)

Não precisa do servidor ligado: o script usa a própria API por dentro, então todas as regras valem
(validações, eventos de auditoria, pontuação da IA). Por isso é seguro rodar mais de uma vez: sem --force ele
detecta que já existe e não faz nada.
"""
import argparse
import os
import random
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["RAFALINK_NO_WORKER"] = "1"                       # não precisa da automação em segundo plano aqui
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi.testclient import TestClient                    # noqa: E402

from backend.app import database                                      # noqa: E402
from backend.app.automation import run_all                             # noqa: E402
from backend.app.main import app                                       # noqa: E402
from backend.app.scoring import rescore_lead                           # noqa: E402

TAG = "Demo"                                                   # marca os leads criados por este script

FIRST = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Fábio", "Gabriela", "Heitor", "Isabela", "João", "Karina",
         "Lucas", "Mariana", "Nelson", "Olívia", "Paulo", "Quitéria", "Rafael", "Sabrina", "Thiago", "Úrsula",
         "Vinícius", "Wagner", "Yasmin", "Zélia", "Aline", "Caio", "Débora", "Eduardo", "Fernanda"]
LAST = ["Almeida", "Barbosa", "Cardoso", "Dias", "Esteves", "Ferraz", "Gomes", "Henrique", "Ibrahim", "Jardim",
        "Klein", "Lopes", "Moreira", "Nogueira", "Oliveira", "Pacheco", "Queiroz", "Ramos", "Siqueira", "Teixeira",
        "Ueda", "Vasconcelos", "Xavier", "Yamamoto", "Zanetti"]
COMPANY_BASES = [("Padaria Estrela", "Alimentação", "Recife"), ("Clínica Vida Nova", "Saúde", "São Paulo"),
                 ("Construtora Horizonte", "Construção", "Belo Horizonte"), ("Escola Novo Saber", "Educação", "Curitiba"),
                 ("Mercado Bom Preço", "Varejo", "Salvador"), ("Transportes Rápido Sul", "Logística", "Porto Alegre"),
                 ("Studio Lume Design", "Design", "Florianópolis"), ("Tech Norte Sistemas", "Tecnologia", "Fortaleza"),
                 ("Contabilidade Prisma", "Serviços", "Goiânia"), ("Agro Campo Verde", "Agronegócio", "Cuiabá"),
                 ("Hotel Brisa Mar", "Turismo", "Natal"), ("Farmácia Saúde Já", "Saúde", "Manaus"),
                 ("Auto Center Veloz", "Automotivo", "Campinas"), ("Imobiliária Lar Doce", "Imóveis", "Vitória"),
                 ("Academia Corpo Ativo", "Fitness", "Brasília")]
SUFFIX = ["LTDA", "ME", "SA", "EIRELI", ""]
CHANNELS = ["EMAIL", "WHATSAPP", "SMS", "REDES_SOCIAIS", "SITE", "EVENTO", "OUTROS"]
JOBS = ["Diretor Comercial", "Gerente de TI", "Sócio-proprietário", "Analista de Compras", "CEO", "Coordenadora de Marketing"]
OPP_TITLES = ["Contrato anual de software", "Licenças corporativas", "Projeto de implantação", "Renovação de contrato",
              "Expansão de unidades", "Plano premium", "Consultoria de processos", "Treinamento da equipe"]
LEAD_STATUS_PATH = {
    "NOVO": [], "EM_CONTATO": ["EM_CONTATO"], "QUALIFICADO": ["EM_CONTATO", "QUALIFICADO"],
    "OPORTUNIDADE": ["EM_CONTATO", "QUALIFICADO", "OPORTUNIDADE"], "CONVERTIDO": ["EM_CONTATO", "QUALIFICADO", "CONVERTIDO"],
    "PERDIDO": ["EM_CONTATO", "PERDIDO"], "ARQUIVADO": ["ARQUIVADO"],
}
LEAD_STATUS_WEIGHTS = [("NOVO", 26), ("EM_CONTATO", 22), ("QUALIFICADO", 16), ("OPORTUNIDADE", 8),
                       ("CONVERTIDO", 8), ("PERDIDO", 12), ("ARQUIVADO", 4)]
LOST_REASONS = ["Sem orçamento", "Escolheu concorrente", "Sem resposta", "Projeto adiado"]


def slug(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower().replace(" ", ".")


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


class Demo:
    def __init__(self, c: TestClient, rnd: random.Random, seed: int):
        self.c, self.rnd, self.seed = c, rnd, seed
        r = c.post("/api/v1/auth/login", json={"email": "admin@rafalink.com", "password": "admin123"})
        r.raise_for_status()
        self.h = {"Authorization": "Bearer " + r.json()["accessToken"]}
        self.org = r.json()["user"]["organizationId"]
        self.owners = [u["id"] for u in self.get("/settings/users")["content"] if u["active"]]
        pipe = next(p for p in self.get("/pipelines") if p["isDefault"])
        self.pipeline, self.stages = pipe["id"], pipe["stages"]
        self.now = datetime.now(timezone.utc)
        self.lead_ids, self.opp_ids = [], []

    # --- API ---
    def get(self, path):
        r = self.c.get("/api/v1" + path, headers=self.h)
        r.raise_for_status()
        return r.json()

    def post(self, path, body=None, expect=(200, 201)):
        r = self.c.post("/api/v1" + path, json=body, headers=self.h)
        if r.status_code not in expect:
            raise RuntimeError(f"POST {path} -> {r.status_code}: {r.text}")
        return r.json() if r.content else None

    def person(self):
        return f"{self.rnd.choice(FIRST)} {self.rnd.choice(LAST)}"

    def phone(self):
        return f"(11) 9{self.rnd.randint(1000, 9999)}-{self.rnd.randint(1000, 9999)}"

    def owner(self):
        return self.rnd.choice(self.owners)

    # --- criação ---
    def companies(self, n):
        out = []
        for base, industry, city in self.rnd.sample(COMPANY_BASES, min(n, len(COMPANY_BASES))):
            suffix = self.rnd.choice(SUFFIX)
            name = f"{base} {suffix}".strip()
            payload = {
                "name": name, "industry": industry, "city": city, "ownerId": self.owner(),
                "website": f"https://www.{slug(base).replace('.', '')}.com.br", "phone": self.phone(),
                "type": self.rnd.choice(["PROSPECT", "PROSPECT", "CLIENTE"]), "notes": "[demo]"}
            r = self.c.post("/api/v1/companies", json=payload, headers=self.h)
            if r.status_code == 409:                              # rodando de novo com --force: reaproveita a existente
                found = self.get(f"/companies?q={name}&size=1")["content"]
                out.append(found[0])
                continue
            r.raise_for_status()
            out.append(r.json())
        return out

    def contacts(self, companies, n):
        out = []
        for i in range(n):
            name = self.person()
            co = companies[i % len(companies)]
            out.append(self.post("/contacts", {
                "name": name, "email": f"{slug(name)}{i}.{self.seed}@{slug(co['name']).split('.')[0]}.com.br", "phone": self.phone(),
                "jobTitle": self.rnd.choice(JOBS), "companyId": co["id"], "ownerId": self.owner()}))
        return out

    def leads(self, n):
        for i in range(n):
            name = self.person()
            company = self.rnd.choice(COMPANY_BASES)[0] + " " + self.rnd.choice(SUFFIX)
            lead = self.post("/leads", {
                "name": name, "email": f"{slug(name)}.{i}.{self.seed}@exemplo.com", "phone": self.phone(), "company": company.strip(),
                "source": TAG, "channel": self.rnd.choice(CHANNELS), "ownerId": self.owner(),
                "nextAction": self.rnd.choice(["Ligar amanhã", "Enviar proposta", "Agendar demo", None])})
            self.lead_ids.append(lead["id"])
            statuses, weights = zip(*LEAD_STATUS_WEIGHTS)
            status = self.rnd.choices(statuses, weights)[0]
            for step in LEAD_STATUS_PATH[status]:
                body = {"status": step}
                if step == "PERDIDO":
                    body["reason"] = self.rnd.choice(LOST_REASONS)
                self.post(f"/leads/{lead['id']}/status", body)
        return self.lead_ids

    def duplicates(self):
        """Três pares de leads quase iguais, para você testar a tela de duplicados e a importação."""
        pairs = [("Marcos Tavares", "marcos.tavares@duplicado.com", "(11) 95555-0001", "Marcos T.", "MARCOS.TAVARES@duplicado.com"),
                 ("Priscila Furtado", "priscila@duplicado.com", "(21) 94444-0002", "Priscila F. Furtado", "priscila.f@duplicado.com"),
                 ("Renato Bastos", "renato@duplicado.com", "(31) 93333-0003", "Renato Bastos", "outro@duplicado.com")]
        for name, email, phone, name2, email2 in pairs:
            for nm, em, ph in ((name, email, phone), (name2, email2, phone)):        # mesmo telefone nos dois
                lead = self.post("/leads", {"name": nm, "email": em, "phone": ph, "company": "Duplicados & Cia",
                                            "source": TAG, "ownerId": self.owner()})
                self.lead_ids.append(lead["id"])

    def opportunities(self, companies, contacts, n):
        open_stages = [s for s in self.stages if s["kind"] == "OPEN"]
        won = next(s for s in self.stages if s["kind"] == "WON")
        lost = next(s for s in self.stages if s["kind"] == "LOST")
        for i in range(n):
            co = companies[i % len(companies)]
            ct = next((c for c in contacts if c["companyId"] == co["id"]), None)
            opp = self.post("/opportunities", {
                "title": f"{self.rnd.choice(OPP_TITLES)} - {co['name']}", "value": self.rnd.choice([8, 12, 18, 25, 40, 65, 90, 150]) * 1000,
                "pipelineId": self.pipeline, "companyId": co["id"], "contactId": ct["id"] if ct else None, "ownerId": self.owner(),
                "expectedCloseDate": (self.now + timedelta(days=self.rnd.randint(-5, 60))).date().isoformat()})
            self.opp_ids.append(opp["id"])
            roll = self.rnd.random()
            target = won if roll < .22 else lost if roll < .38 else self.rnd.choice(open_stages)
            if target["id"] != opp["stageId"]:
                body = {"stageId": target["id"]}
                if target is lost:
                    body["reason"] = self.rnd.choice(LOST_REASONS)
                self.post(f"/opportunities/{opp['id']}/move", body)

    def activities(self, n):
        types = ["LIGACAO", "EMAIL", "WHATSAPP", "REUNIAO", "TAREFA", "FOLLOW_UP", "NOTA"]
        for i in range(n):
            days = self.rnd.randint(-12, 14)
            kind = self.rnd.choice(types)
            if kind == "NOTA":
                days = -abs(days)                       # nota é algo que já aconteceu: não pode ficar no futuro
            body = {"type": kind, "title": self.rnd.choice(
                ["Retornar contato", "Enviar proposta revisada", "Reunião de alinhamento", "Follow-up da demo", "Atualizar cadastro"]),
                "dueAt": iso(self.now + timedelta(days=days, hours=self.rnd.randint(-5, 5))), "ownerId": self.owner()}
            if self.rnd.random() < .6 and self.lead_ids:
                body["leadId"] = self.rnd.choice(self.lead_ids)
            elif self.opp_ids:
                body["opportunityId"] = self.rnd.choice(self.opp_ids)
            act = self.post("/activities", body)
            if days < 0 and body["type"] != "NOTA" and self.rnd.random() < .6:
                self.post(f"/activities/{act['id']}/complete")

    # --- datas realistas ---
    def backdate(self):
        conn = database.get_conn()
        try:
            for lid in self.lead_ids:
                age = self.rnd.randint(1, 90)
                created = self.now - timedelta(days=age, hours=self.rnd.randint(0, 20))
                last = created + timedelta(days=self.rnd.randint(0, max(age - 1, 0)))
                conn.execute(
                    "UPDATE leads SET created_at = ?, updated_at = ?, "
                    "last_interaction_at = CASE WHEN status = 'NOVO' THEN NULL ELSE ? END WHERE id = ?",
                    (iso(created), iso(last), iso(last), lid))
            for oid in self.opp_ids:
                age = self.rnd.randint(3, 80)
                created = self.now - timedelta(days=age)
                changed = created + timedelta(days=self.rnd.randint(0, age - 1))
                conn.execute(
                    "UPDATE opportunities SET created_at = ?, stage_changed_at = ?, updated_at = ?, "
                    "closed_at = CASE WHEN closed_at IS NULL THEN NULL ELSE ? END WHERE id = ?",
                    (iso(created), iso(changed), iso(changed), iso(changed), oid))
            conn.commit()
            for lid in self.lead_ids:                                   # a nota da IA depende das datas
                rescore_lead(conn, self.org, lid)
            conn.commit()
            return run_all(conn)["executed"]                            # a automação reage ao novo cenário
        finally:
            conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera dados de demonstração do RafaLink CRM.")
    ap.add_argument("--leads", type=int, default=48)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    if not 1 <= args.leads <= 500:
        sys.exit("Use --leads entre 1 e 500.")

    with TestClient(app) as client:                                      # liga o app: cria o banco se precisar
        demo = Demo(client, random.Random(args.seed), args.seed)
        if demo.get(f"/leads?source={TAG}&size=1")["totalElements"] and not args.force:
            print("Os dados de demonstração já existem. Nada a fazer (use --force para criar mais).")
            return
        companies = demo.companies(12)
        contacts = demo.contacts(companies, 30)
        demo.leads(args.leads)
        demo.duplicates()
        demo.opportunities(companies, contacts, 22)
        demo.activities(40)
        fired = demo.backdate()
        print(f"Pronto: {len(companies)} empresas, {len(contacts)} contatos, {len(demo.lead_ids)} leads "
              f"(com 3 pares duplicados), {len(demo.opp_ids)} oportunidades e 40 atividades. "
              f"A automação gerou {fired} aviso(s)/tarefa(s).")
        print("Abra o sistema e veja: Dashboard, Pipeline, Forecast, IA e Configurações > Duplicados.")


if __name__ == "__main__":
    main()