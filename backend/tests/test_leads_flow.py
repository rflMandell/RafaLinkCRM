"""Leads: cadastro, validação, funil de status e conversão (RN02, RN04)."""
from conftest import make_lead


def test_criar_e_buscar_lead(api):
    lead = make_lead(api, name="Fulano de Tal", company="Acme")
    assert lead["status"] == "NOVO" and lead["ownerName"]
    got = api.as_("admin").get(f"/leads/{lead['id']}")
    assert got.status_code == 200 and got.json()["name"] == "Fulano de Tal"


def test_validacao_do_cadastro(api):
    r = api.as_("admin").post("/leads", {"name": "A", "email": "sem-arroba"})
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_ERROR"


def test_listagem_pagina_e_filtra(api):
    for i in range(3):
        make_lead(api, name=f"Zeta Teste {i}", email=f"zeta{i}@exemplo.com")
    r = api.as_("admin").get("/leads?q=Zeta&size=2&sort=name,asc")
    body = r.json()
    assert body["totalElements"] == 3 and body["totalPages"] == 2 and len(body["content"]) == 2
    assert [x["name"] for x in body["content"]] == ["Zeta Teste 0", "Zeta Teste 1"]


def test_ordenacao_invalida(api):
    r = api.as_("admin").get("/leads?sort=senha,asc")
    assert r.status_code == 400 and r.json()["code"] == "INVALID_SORT"


def test_lead_inexistente(api):
    assert api.as_("admin").get("/leads/999999").status_code == 404


def test_responsavel_invalido(api):
    r = api.as_("admin").post("/leads", {"name": "Com Dono", "ownerId": 999999})
    assert r.status_code == 422 and r.json()["code"] == "OWNER_NOT_FOUND"


def test_transicao_invalida(api):
    lead = make_lead(api)
    r = api.as_("admin").post(f"/leads/{lead['id']}/status", {"status": "QUALIFICADO"})   # pulou "em contato"
    assert r.status_code == 422 and r.json()["code"] == "INVALID_LEAD_TRANSITION"


def test_funil_completo_e_conversao_cria_contato_empresa_e_oportunidade(api):
    a = api.as_("admin")
    lead = make_lead(api, name="Cliente Futuro", company="Futuro Tech LTDA", email="futuro@tech.com")
    assert a.post(f"/leads/{lead['id']}/status", {"status": "EM_CONTATO"}).status_code == 200
    assert a.post(f"/leads/{lead['id']}/qualify").status_code == 200
    r = a.post(f"/leads/{lead['id']}/convert")
    assert r.status_code == 200, r.text
    done = r.json()
    assert done["status"] == "CONVERTIDO"
    assert done["contactId"] and done["companyId"] and done["opportunityId"]
    assert a.get(f"/contacts/{done['contactId']}").status_code == 200
    assert a.get(f"/companies/{done['companyId']}").json()["name"] == "Futuro Tech LTDA"
    assert a.get(f"/opportunities/{done['opportunityId']}").status_code == 200


def test_lead_convertido_nao_muda_mais(api):
    a = api.as_("admin")
    lead = make_lead(api)
    for step in ("EM_CONTATO", "QUALIFICADO", "CONVERTIDO"):
        assert a.post(f"/leads/{lead['id']}/status", {"status": step}).status_code == 200
    r = a.post(f"/leads/{lead['id']}/status", {"status": "PERDIDO"})
    assert r.status_code == 422 and r.json()["code"] == "LEAD_ALREADY_CONVERTED"


def test_arquivar_lead(api):
    lead = make_lead(api)
    r = api.as_("admin").post(f"/leads/{lead['id']}/archive")
    assert r.status_code == 200 and r.json()["status"] == "ARQUIVADO"


def test_empresa_com_contato_nao_pode_ser_excluida(api):
    a = api.as_("admin")
    company = a.post("/companies", {"name": "Empresa Teste SA"}).json()
    contact = a.post("/contacts", {"name": "Contato Teste", "companyId": company["id"]})
    assert contact.status_code == 201, contact.text
    r = a.delete(f"/companies/{company['id']}")
    assert r.status_code == 409
    assert a.delete(f"/contacts/{contact.json()['id']}").status_code == 204
    assert a.delete(f"/companies/{company['id']}").status_code == 204


def test_eventos_do_lead_entram_na_auditoria(api):
    lead = make_lead(api, name="Auditado Silva")
    r = api.as_("admin").get("/audit?entity=lead&q=Auditado")
    assert r.status_code == 200
    assert any(e["entityId"] == lead["id"] for e in r.json()["content"])