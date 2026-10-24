"""RBAC (Etapa 10): papéis, matriz de permissões e proteções contra se trancar fora do sistema."""


def _uid(api, email):
    users = api.as_("admin").get("/settings/users").json()["content"]
    return next(u["id"] for u in users if u["email"] == email)


def test_padroes_por_papel(api):
    me = lambda who: set(api.as_(who).get("/settings/me").json()["permissions"])
    assert "settings.users" in me("admin") and "data.import" in me("admin")
    assert "data.import" in me("gerente") and "settings.users" not in me("gerente")
    assert me("vendedor") == set()


def test_vendedor_nao_importa_nem_ve_duplicados_nem_auditoria(api):
    v = api.as_("vendedor")
    assert v.post("/import/preview", {"entity": "leads", "csv": "nome\nAna"}).status_code == 403
    assert v.get("/dedupe/leads").status_code == 403
    assert v.get("/audit").status_code == 403
    assert v.get("/settings/users").status_code == 403


def test_gerente_nao_gerencia_usuarios_nem_permissoes(api):
    g = api.as_("gerente")
    assert g.get("/settings/users").status_code == 403
    r = g.put("/settings/permissions", {"role": "SALES", "permission": "data.import", "allowed": True})
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"


def test_admin_libera_e_revoga_permissao_na_pratica(api):
    admin, vend = api.as_("admin"), api.as_("vendedor")
    csv = {"entity": "leads", "csv": "nome\nAna Teste"}
    assert vend.post("/import/preview", csv).status_code == 403
    r = admin.put("/settings/permissions", {"role": "SALES", "permission": "data.import", "allowed": True})
    assert r.status_code == 200
    cell = next(p for p in r.json()["permissions"] if p["key"] == "data.import")["values"]["SALES"]
    assert cell["allowed"] and cell["custom"]
    assert vend.post("/import/preview", csv).status_code == 200            # vale na hora
    admin.put("/settings/permissions", {"role": "SALES", "permission": "data.import", "allowed": False})
    assert vend.post("/import/preview", csv).status_code == 403
    assert not next(p for p in admin.get("/settings/permissions").json()["permissions"]
                    if p["key"] == "data.import")["values"]["SALES"]["custom"]   # voltou ao padrão: sem exceção guardada


def test_revogar_do_gerente_vale_para_as_rotas_antigas(api):
    admin, ger = api.as_("admin"), api.as_("gerente")
    assert ger.get("/audit").status_code == 200
    admin.put("/settings/permissions", {"role": "SALES_MANAGER", "permission": "audit.read", "allowed": False})
    assert ger.get("/audit").status_code == 403


def test_restaurar_padrao(api):
    admin = api.as_("admin")
    admin.put("/settings/permissions", {"role": "SALES", "permission": "data.dedupe", "allowed": True})
    admin.put("/settings/permissions", {"role": "SALES_MANAGER", "permission": "data.merge", "allowed": False})
    assert admin.delete("/settings/permissions").status_code == 200
    assert api.as_("vendedor").get("/dedupe/leads").status_code == 403
    assert api.as_("gerente").get("/dedupe/leads").status_code == 200


def test_permissoes_de_configuracao_sao_travadas(api):
    admin = api.as_("admin")
    r = admin.put("/settings/permissions", {"role": "SALES_MANAGER", "permission": "settings.users", "allowed": True})
    assert r.status_code == 409 and r.json()["code"] == "PERMISSION_LOCKED"
    r = admin.put("/settings/permissions", {"role": "ADMIN", "permission": "data.import", "allowed": False})
    assert r.status_code == 400 and r.json()["code"] == "INVALID_ROLE"
    r = admin.put("/settings/permissions", {"role": "SALES", "permission": "inventada", "allowed": True})
    assert r.status_code == 400 and r.json()["code"] == "UNKNOWN_PERMISSION"


def test_admin_nao_altera_a_si_mesmo(api):
    admin = api.as_("admin")
    me = _uid(api, "admin@rafalink.com")
    r = admin.patch(f"/settings/users/{me}", {"role": "SALES"})
    assert r.status_code == 409 and r.json()["code"] == "CANNOT_MODIFY_SELF"
    r = admin.patch(f"/settings/users/{me}", {"active": False})
    assert r.status_code == 409 and r.json()["code"] == "CANNOT_MODIFY_SELF"


def test_nunca_fica_sem_administrador(api):
    admin = api.as_("admin")
    r = admin.post("/settings/users", {"name": "Segundo Admin", "email": "admin2@rafalink.com",
                                        "password": "senhaforte1", "role": "ADMIN"})
    assert r.status_code == 201
    second = r.json()["id"]
    first = _uid(api, "admin@rafalink.com")
    # o segundo admin pode ser rebaixado enquanto o primeiro existir
    assert admin.patch(f"/settings/users/{second}", {"role": "SALES"}).status_code == 200
    # mas ninguém consegue rebaixar o último admin (aqui quem barra é a regra de não alterar a si mesmo)
    r = admin.patch(f"/settings/users/{first}", {"role": "SALES"})
    assert r.status_code == 409


def test_criar_usuario_regras(api, client):
    admin = api.as_("admin")
    ok = {"name": "Novo Vendedor", "email": "Novo@Teste.com", "password": "senhaforte1", "role": "SALES"}
    r = admin.post("/settings/users", ok)
    assert r.status_code == 201 and r.json()["email"] == "novo@teste.com"
    assert admin.post("/settings/users", ok).json()["code"] == "EMAIL_ALREADY_EXISTS"
    assert admin.post("/settings/users", {**ok, "email": "outro@teste.com", "password": "curta"}).status_code == 400
    assert admin.post("/settings/users", {**ok, "email": "outro@teste.com", "role": "DONO"}).json()["code"] == "INVALID_ROLE"
    login = client.post("/api/v1/auth/login", json={"email": "novo@teste.com", "password": "senhaforte1"})
    assert login.status_code == 200 and login.json()["user"]["role"] == "SALES"


def test_permissoes_alteradas_ficam_na_auditoria(api):
    admin = api.as_("admin")
    admin.put("/settings/permissions", {"role": "SALES", "permission": "data.import", "allowed": True})
    types = {e["type"] for e in admin.get("/audit?size=50").json()["content"]}
    assert "PermissionChanged" in types


def test_flag_canmanage_das_telas_segue_a_matriz(api):
    admin, ger = api.as_("admin"), api.as_("gerente")
    assert ger.get("/goals/options").json()["canManage"] is True
    assert ger.get("/sla").json()["canManage"] is True
    assert ger.get("/ai/weights").json()["canManage"] is True
    assert ger.get("/automations").json()["canManage"] is True
    for perm in ("goals.manage", "ai.weights", "automation.manage"):
        admin.put("/settings/permissions", {"role": "SALES_MANAGER", "permission": perm, "allowed": False})
    assert ger.get("/goals/options").json()["canManage"] is False
    assert ger.get("/ai/weights").json()["canManage"] is False
    assert ger.get("/automations").json()["canManage"] is False
    assert ger.get("/sla").json()["canManage"] is False