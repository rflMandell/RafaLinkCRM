"""Configuração dos testes.

Ideia: o banco de demonstração é criado UMA vez (migrations + seed) e depois copiado para cada teste.
Assim cada teste começa do mesmo ponto, não interfere nos outros e o seu banco real
(backend/data/rafalink.db) nunca é tocado.
"""
import os
import shutil
import sqlite3

import pytest

os.environ["RAFALINK_NO_WORKER"] = "1"          # desliga a automação em segundo plano durante os testes

from fastapi.testclient import TestClient       # noqa: E402

from app import database                         # noqa: E402

USERS = {
    "admin": ("admin@rafalink.com", "admin123"),
    "gerente": ("gerente@rafalink.com", "gerente123"),
    "vendedor": ("vendedor@rafalink.com", "vendedor123"),
    "admin2": ("admin@outraempresa.com", "admin123"),     # organização de demonstração 2 (Etapa 10)
}


@pytest.fixture(scope="session")
def template_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("template") / "template.db"
    database.DB_PATH = path
    from app.main import app
    with TestClient(app):                          # executa o lifespan: migrations + seed
        pass
    conn = sqlite3.connect(path)                   # junta o arquivo -wal no arquivo principal antes de copiar
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    return path


@pytest.fixture(scope="session")
def tokens(template_db):
    """Faz login uma vez por usuário (o hash de senha é lento de propósito)."""
    from app.main import app
    out = {}
    with TestClient(app) as c:
        for key, (email, password) in USERS.items():
            r = c.post("/api/v1/auth/login", json={"email": email, "password": password})
            assert r.status_code == 200, f"login de {email} falhou: {r.text}"
            out[key] = r.json()["accessToken"]
    return out


@pytest.fixture()
def db_path(template_db, tmp_path):
    path = tmp_path / "test.db"
    shutil.copy(template_db, path)
    database.DB_PATH = path
    return path


@pytest.fixture()
def client(db_path):
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)   # sem "with": não repete o seed


class Api:
    """Cliente com atalhos: api.as_("admin").get("/leads")."""

    def __init__(self, client, tokens):
        self._c, self._t = client, tokens

    def as_(self, who):
        c = self._c
        headers = {"Authorization": f"Bearer {self._t[who]}"} if who else {}

        class _Bound:
            def get(_, path, **kw): return c.get("/api/v1" + path, headers=headers, **kw)
            def post(_, path, json=None, **kw): return c.post("/api/v1" + path, json=json, headers=headers, **kw)
            def put(_, path, json=None, **kw): return c.put("/api/v1" + path, json=json, headers=headers, **kw)
            def patch(_, path, json=None, **kw): return c.patch("/api/v1" + path, json=json, headers=headers, **kw)
            def delete(_, path, **kw): return c.delete("/api/v1" + path, headers=headers, **kw)

        return _Bound()


@pytest.fixture()
def api(client, tokens):
    return Api(client, tokens)


@pytest.fixture()
def db(db_path):
    conn = database.get_conn()
    yield conn
    conn.close()


def make_lead(api, who="admin", **over):
    body = {"name": "Lead de Teste", "email": "teste@exemplo.com", **over}
    r = api.as_(who).post("/leads", body)
    assert r.status_code == 201, r.text
    return r.json()