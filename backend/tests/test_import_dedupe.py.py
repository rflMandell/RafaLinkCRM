"""Importação CSV e deduplicação (Etapa 10)."""
from conftest import make_lead

CSV = (
    "Nome;E-mail;Telefone;Empresa;Canal\n"
    "Ana Lima;ana@exemplo.com;(11) 98888-1111;Padaria Estrela LTDA;WhatsApp\n"
    "Bruno Rocha;bruno@exemplo.com;;Rocha Dev;Site\n"
    "Bruno Rocha;bruno@exemplo.com;;Rocha Dev;Site\n"          # repetido no arquivo
    "Carla;carla-sem-arroba;;;\n"                                # e-mail inválido
    ";sem.nome@exemplo.com;;;\n"                                 # sem nome
)


def preview(api, csv=CSV, who="admin", entity="leads", mapping=None):
    body = {"entity": entity, "csv": csv, **({"mapping": mapping} if mapping else {})}
    return api.as_(who).post("/import/preview", body)


def test_preview_detecta_separador_mapeia_colunas_e_classifica_linhas(api):
    r = preview(api)
    assert r.status_code == 200
    p = r.json()
    assert p["delimiter"] == ";" and p["totalRows"] == 5
    assert p["mapping"]["name"] == "Nome" and p["mapping"]["email"] == "E-mail"
    assert p["summary"] == {"total": 5, "ok": 2, "duplicates": 0, "dupInFile": 1, "errors": 2}
    assert [x["row"] for x in p["problems"]] == [4, 5, 6]


def test_preview_nao_grava_nada(api):
    preview(api)
    assert api.as_("admin").get("/leads?q=Ana Lima").json()["totalElements"] == 0


def test_commit_cria_so_o_que_e_valido_e_publica_evento(api):
    r = api.as_("admin").post("/import/commit", {"entity": "leads", "csv": CSV, "onDuplicate": "SKIP"})
    assert r.status_code == 200
    assert r.json() == {"created": 2, "updated": 0, "skipped": 1, "errors": 2, "companiesCreated": 0, "total": 5}
    leads = api.as_("admin").get("/leads?q=exemplo.com&size=50").json()["content"]
    ana = next(x for x in leads if x["name"] == "Ana Lima")
    assert ana["channel"] == "WHATSAPP" and ana["source"] == "Importação CSV" and ana["ownerId"]
    events = api.as_("admin").get("/audit?size=50").json()["content"]
    assert any(e["type"] == "ImportCompleted" for e in events)


def test_reimportar_o_mesmo_arquivo_ignora_existentes(api):
    a = api.as_("admin")
    a.post("/import/commit", {"entity": "leads", "csv": CSV})
    p = preview(api).json()["summary"]
    assert p["duplicates"] == 3 and p["ok"] == 0      # Ana, Bruno e a repetição do Bruno
    again = a.post("/import/commit", {"entity": "leads", "csv": CSV, "onDuplicate": "SKIP"}).json()
    assert again["created"] == 0


def test_politica_atualizar_preenche_sem_apagar(api):
    a = api.as_("admin")
    lead = make_lead(api, name="Ana Lima", email="ana@exemplo.com", company="Padaria Estrela")
    csv = "Nome;E-mail;Telefone\nAna Lima;ana@exemplo.com;11 97777-0000\n"
    r = a.post("/import/commit", {"entity": "leads", "csv": csv, "onDuplicate": "UPDATE"}).json()
    assert r["updated"] == 1 and r["created"] == 0
    got = a.get(f"/leads/{lead['id']}").json()
    assert got["phone"] == "11 97777-0000" and got["company"] == "Padaria Estrela"     # telefone novo, empresa mantida


def test_politica_criar_mesmo_assim_duplica(api):
    a = api.as_("admin")
    make_lead(api, name="Ana Lima", email="ana@exemplo.com")
    csv = "Nome;E-mail\nAna Lima;ana@exemplo.com\n"
    r = a.post("/import/commit", {"entity": "leads", "csv": csv, "onDuplicate": "CREATE"}).json()
    assert r["created"] == 1
    assert a.get("/leads?q=Ana Lima").json()["totalElements"] == 2


def test_contatos_criam_empresa_ausente_quando_pedido(api):
    a = api.as_("admin")
    csv = "Nome;Cargo;Empresa\nDiego Alves;CTO;Nova Empresa Dois SA\n"
    r = a.post("/import/commit", {"entity": "contacts", "csv": csv, "createCompanies": True}).json()
    assert r["created"] == 1 and r["companiesCreated"] == 1
    r = a.post("/import/commit", {"entity": "contacts", "csv": "Nome;Empresa\nElisa Nunes;Outra Inexistente\n",
                                  "createCompanies": False}).json()
    assert r["created"] == 1 and r["companiesCreated"] == 0


def test_limites_e_arquivos_invalidos(api):
    a = api.as_("admin")
    assert a.post("/import/preview", {"entity": "leads", "csv": ""}).json()["code"] == "EMPTY_CSV"
    assert a.post("/import/preview", {"entity": "leads", "csv": "Nome\n"}).json()["code"] == "EMPTY_CSV"
    assert a.post("/import/preview", {"entity": "tudo", "csv": "Nome\nA"}).json()["code"] == "INVALID_ENTITY"
    big = "Nome\n" + "\n".join(f"Pessoa {i}" for i in range(2001))
    assert a.post("/import/preview", {"entity": "leads", "csv": big}).json()["code"] == "IMPORT_TOO_LARGE"
    bad = a.post("/import/preview", {"entity": "leads", "csv": "Nome\nAna", "mapping": {"name": "Inexistente"}})
    assert bad.status_code == 400 and bad.json()["code"] == "INVALID_MAPPING"
    r = a.post("/import/commit", {"entity": "leads", "csv": "Nome\nAna Maria", "onDuplicate": "TALVEZ"})
    assert r.json()["code"] == "INVALID_POLICY"


def test_csv_com_bom_e_virgula(api):
    csv = "\ufeffname,email\nZeca Pagodinho,zeca@exemplo.com\n"
    p = preview(api, csv).json()
    assert p["delimiter"] == "," and p["mapping"]["name"] == "name" and p["summary"]["ok"] == 1


# ---------- duplicados ----------
def _dup_leads(api):
    a = make_lead(api, name="João Silva", email="joao@exemplo.com", phone="(11) 98888-7777")
    b = make_lead(api, name="Joao S.", email="JOAO@exemplo.com", company="Silva ME")
    return a, b


def test_encontra_grupo_de_duplicados(api):
    a, b = _dup_leads(api)
    r = api.as_("admin").get("/dedupe/leads").json()
    group = next(g for g in r["groups"] if {x["id"] for x in g["records"]} >= {a["id"], b["id"]})
    assert "mesmo e-mail" in group["reasons"]
    assert group["suggestedKeepId"] in (a["id"], b["id"])


def test_mesclar_preenche_campos_move_vinculos_e_apaga(api):
    admin = api.as_("admin")
    a, b = _dup_leads(api)                                         # só o "b" tem empresa
    act = admin.post("/activities", {"type": "NOTA", "title": "Nota no duplicado", "leadId": b["id"]})
    assert act.status_code == 201, act.text
    r = admin.post("/dedupe/leads/merge", {"keepId": a["id"], "mergeIds": [b["id"]]})
    assert r.status_code == 200 and r.json()["merged"] == 1 and "company" in r.json()["filledFields"]
    assert admin.get(f"/leads/{b['id']}").status_code == 404
    assert admin.get(f"/leads/{a['id']}").json()["company"] == "Silva ME"
    mine = admin.get(f"/activities?leadId={a['id']}").json()
    assert any(x["title"] == "Nota no duplicado" for x in mine["content"])        # a atividade foi junto
    assert any(e["type"] == "RecordsMerged" for e in admin.get("/audit?size=50").json()["content"])


def test_mesclar_validacoes(api):
    a, b = _dup_leads(api)
    admin = api.as_("admin")
    assert admin.post("/dedupe/leads/merge", {"keepId": a["id"], "mergeIds": [a["id"]]}).json()["code"] == "INVALID_MERGE"
    assert admin.post("/dedupe/leads/merge", {"keepId": a["id"], "mergeIds": [999999]}).json()["code"] == "RECORD_NOT_FOUND"
    assert admin.post("/dedupe/leads/merge", {"keepId": a["id"], "mergeIds": []}).status_code == 400
    assert admin.get("/dedupe/clientes").status_code == 404


def test_check_antes_de_criar_avisa_parecidos(api):
    a, _ = _dup_leads(api)
    r = api.as_("admin").get("/dedupe/check/leads?email=joao@exemplo.com").json()
    assert any(m["id"] == a["id"] for m in r["matches"])


def test_empresas_duplicadas_por_nome_sem_sufixo_e_por_site(api):
    admin = api.as_("admin")
    a = admin.post("/companies", {"name": "Mercado Bom Preço LTDA", "website": "https://www.bompreco.com"}).json()
    b = admin.post("/companies", {"name": "Mercado Bom Preco", "website": "bompreco.com/contato"}).json()
    groups = admin.get("/dedupe/companies").json()["groups"]
    assert any({a["id"], b["id"]} <= {r["id"] for r in g["records"]} for g in groups)