"""Login, proteção das rotas e formato padronizado dos erros."""


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["status"] == "UP"


def test_login_ok_devolve_token_e_usuario(client):
    r = client.post("/api/v1/auth/login", json={"email": "ADMIN@rafalink.com ", "password": "admin123"})
    assert r.status_code == 200
    body = r.json()
    assert body["tokenType"] == "Bearer" and body["accessToken"]
    assert body["user"]["role"] == "ADMIN"
    assert "password" not in str(body).lower()


def test_login_senha_errada(client):
    r = client.post("/api/v1/auth/login", json={"email": "admin@rafalink.com", "password": "errada"})
    assert r.status_code == 401 and r.json()["code"] == "INVALID_CREDENTIALS"


def test_login_usuario_inexistente(client):
    r = client.post("/api/v1/auth/login", json={"email": "ninguem@x.com", "password": "123"})
    assert r.status_code == 401 and r.json()["code"] == "INVALID_CREDENTIALS"


def test_login_sem_corpo_e_erro_de_validacao(client):
    r = client.post("/api/v1/auth/login", json={"email": "a@b.com"})
    assert r.status_code == 400 and r.json()["code"] == "VALIDATION_ERROR"
    assert "password" in r.json()["message"]            # a mensagem diz qual campo faltou


def test_rota_protegida_sem_token(client):
    r = client.get("/api/v1/leads")
    assert r.status_code == 401 and r.json()["code"] == "NOT_AUTHENTICATED"


def test_token_invalido(client):
    r = client.get("/api/v1/leads", headers={"Authorization": "Bearer lixo"})
    assert r.status_code == 401 and r.json()["code"] == "INVALID_TOKEN"


def test_me(api):
    r = api.as_("vendedor").get("/auth/me")
    assert r.status_code == 200 and r.json()["email"] == "vendedor@rafalink.com"


def test_usuario_desativado_nao_entra_nem_usa_token(api, client):
    admin = api.as_("admin")
    users = admin.get("/settings/users").json()["content"]
    vend = next(u for u in users if u["email"] == "vendedor@rafalink.com")
    assert admin.patch(f"/settings/users/{vend['id']}", {"active": False}).status_code == 200
    # o token antigo para de valer na hora
    assert api.as_("vendedor").get("/leads").json()["code"] == "USER_NOT_FOUND"
    r = client.post("/api/v1/auth/login", json={"email": "vendedor@rafalink.com", "password": "vendedor123"})
    assert r.status_code == 403 and r.json()["code"] == "USER_INACTIVE"


def test_erro_tem_o_formato_padrao(client):
    j = client.get("/api/v1/leads").json()
    assert set(j) == {"timestamp", "status", "code", "message", "path"}
    assert j["path"] == "/api/v1/leads"


def test_rota_da_api_inexistente_devolve_json_404(client):
    r = client.get("/api/v1/nao-existe")
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"


def test_pagina_inexistente_mostra_a_pagina_404_do_site(client):
    r = client.get("/pagina-que-nao-existe.html")
    assert r.status_code == 404
    assert "text/html" in r.headers["content-type"] and "404" in r.text


def _rota_temporaria(app, path, fn):
    """Registra uma rota só para o teste, antes da rota coringa /api/{...}."""
    app.get(path)(fn)
    app.router.routes.insert(0, app.router.routes.pop())


def _remove_rota(app, path):
    app.router.routes[:] = [x for x in app.router.routes if getattr(x, "path", "") != path]


def test_erro_inesperado_vira_500_padronizado_sem_vazar_detalhes(client, caplog):
    from app.main import app

    def boom():
        raise RuntimeError("segredo interno")

    _rota_temporaria(app, "/api/v1/_boom", boom)

    with caplog.at_level("ERROR", logger="rafalink"):
        r = client.get("/api/v1/_boom")
    assert r.status_code == 500 and r.json()["code"] == "INTERNAL_ERROR"
    assert "segredo" not in r.text                      # o usuário não vê o detalhe...
    assert "segredo interno" in caplog.text             # ...mas o log guarda o traceback
    _remove_rota(app, "/api/v1/_boom")


def test_conflito_de_banco_vira_409(client):
    from app.main import app
    from app.database import get_conn

    def dup():
        c = get_conn()
        try:
            c.execute("INSERT INTO organizations(id, name) VALUES (1, 'duplicada')")   # id 1 já existe
        finally:
            c.close()

    _rota_temporaria(app, "/api/v1/_dup", dup)
    r = client.get("/api/v1/_dup")
    assert r.status_code == 409 and r.json()["code"] == "DATA_CONFLICT"
    _remove_rota(app, "/api/v1/_dup")