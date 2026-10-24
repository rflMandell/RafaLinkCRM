"""Multi-tenancy (cada organização só enxerga o que é seu) e busca global."""
from conftest import make_lead


def test_organizacoes_tem_dados_separados(api):
    mine = make_lead(api, "admin", name="Segredo da Org Um", email="segredo@um.com")
    theirs = make_lead(api, "admin2", name="Segredo da Org Dois", email="segredo@dois.com")
    one = {x["id"] for x in api.as_("admin").get("/leads?size=100").json()["content"]}
    two = {x["id"] for x in api.as_("admin2").get("/leads?size=100").json()["content"]}
    assert mine["id"] in one and theirs["id"] in two
    assert not (one & two)


def test_org_nao_acessa_registro_da_outra(api):
    mine = make_lead(api, "admin", name="Só da Org Um")
    assert api.as_("admin2").get(f"/leads/{mine['id']}").status_code == 404
    assert api.as_("admin2").patch(f"/leads/{mine['id']}", {"name": "Invadido"}).status_code == 404
    assert api.as_("admin2").post(f"/leads/{mine['id']}/archive").status_code == 404
    assert api.as_("admin").get(f"/leads/{mine['id']}").json()["name"] == "Só da Org Um"


def test_usuarios_nao_vazam_entre_organizacoes(api):
    emails = {u["email"] for u in api.as_("admin").get("/settings/users").json()["content"]}
    assert "admin@outraempresa.com" not in emails
    emails2 = {u["email"] for u in api.as_("admin2").get("/settings/users").json()["content"]}
    assert emails2 == {"admin@outraempresa.com"}


def test_nao_da_para_atribuir_lead_a_usuario_de_outra_org(api):
    other = api.as_("admin2").get("/settings/me").json()["id"]
    r = api.as_("admin").post("/leads", {"name": "Lead Atribuído", "ownerId": other})
    assert r.status_code == 422 and r.json()["code"] == "OWNER_NOT_FOUND"


def test_mesclar_entre_organizacoes_e_recusado(api):
    mine = make_lead(api, "admin", name="Meu Lead", email="a@a.com")
    theirs = make_lead(api, "admin2", name="Lead Deles", email="b@b.com")
    r = api.as_("admin").post("/dedupe/leads/merge", {"keepId": mine["id"], "mergeIds": [theirs["id"]]})
    assert r.status_code == 404
    assert api.as_("admin2").get(f"/leads/{theirs['id']}").status_code == 200       # nada foi apagado


def test_importacao_e_duplicados_nao_enxergam_a_outra_org(api):
    make_lead(api, "admin2", name="Helena Prado Teste", email="helena.teste@exemplo.com")
    p = api.as_("admin").post("/import/preview", {"entity": "leads", "csv": "Nome;E-mail\nHelena Prado Teste;helena.teste@exemplo.com"})
    assert p.json()["summary"]["duplicates"] == 0      # na org 1 ela não existe: não é duplicada


def test_auditoria_e_permissoes_sao_por_organizacao(api):
    make_lead(api, "admin2", name="Evento da Org Dois")
    api.as_("admin2").put("/settings/permissions", {"role": "SALES", "permission": "data.import", "allowed": True})
    names = {e["summary"] for e in api.as_("admin").get("/audit?size=100").json()["content"]}
    assert not any("Evento da Org Dois" in n for n in names)
    assert api.as_("vendedor").post("/import/preview", {"entity": "leads", "csv": "Nome\nAna"}).status_code == 403


# ---------- busca global ----------
def test_busca_ignora_acentos_e_maiusculas(api):
    make_lead(api, name="João Pereira", email="joao.p@exemplo.com")
    for q in ("joao", "JOÃO", "joão pe"):
        r = api.as_("admin").get(f"/search?q={q}").json()
        titles = [i["title"] for g in r["groups"] for i in g["items"]]
        assert "João Pereira" in titles, q


def test_busca_agrupa_e_devolve_links(api):
    api.as_("admin").post("/companies", {"name": "Zênite Aeroespacial"})
    make_lead(api, name="Zenaide Costa")
    r = api.as_("admin").get("/search?q=zen").json()
    keys = {g["key"] for g in r["groups"]}
    assert {"leads", "companies"} <= keys
    lead_item = next(g for g in r["groups"] if g["key"] == "leads")["items"][0]
    assert lead_item["href"].startswith("lead.html?id=")


def test_busca_curta_vazia_e_com_curinga(api):
    a = api.as_("admin")
    assert a.get("/search?q=a").json() == {"query": "a", "groups": [], "total": 0}
    assert a.get("/search?q=%25%25").json()["total"] == 0          # "%%" é texto, não curinga
    assert a.get("/search?q=" + "x" * 81).status_code == 400


def test_busca_exige_login(client):
    assert client.get("/api/v1/search?q=ana").status_code == 401


def test_busca_nao_mostra_dados_da_outra_org(api):
    make_lead(api, "admin2", name="Exclusivo Dois", email="ex@dois.com")
    r = api.as_("admin").get("/search?q=exclusivo").json()
    assert r["total"] == 0