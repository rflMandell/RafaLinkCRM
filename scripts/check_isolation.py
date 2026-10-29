"""Etapa 10: verifica o isolamento entre organizações (multi-tenancy).

Com o servidor rodando (python -m uvicorn app.main:app --port 8000), execute na raiz do projeto:
    python scripts/check_isolation.py
Entra com o admin das duas organizações de demonstração e confere que uma NÃO enxerga dados da outra.
"""

# Resultado esperado: 6 linhas, 3 válidas, 1 repetida no arquivo (o Bruno, 2ª vez) e 2 com erro (e-mail inválido da Carla e linha sem nome).

import json
import sys
import urllib.error
import urllib.request

BASE = "http://localhost:8000/api/v1"
TENANTS = {"A": ("admin@rafalink.com", "admin123"), "B": ("admin@outraempresa.com", "admin123")}
LISTS = ["leads", "companies", "contacts", "opportunities", "campaigns", "activities"]


def call(path, token=None, body=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        # as linhas que estao comentadas abaixo, devem ser descomentadas se quiser ver o corpo do erro HTTP para melhor tratamento de erros
        #error_body = e.read().decode("utf-8", errors="replace")
        #print(f"\nERRO HTTP {e.code} em {path}: {error_body}")
        return e.code, None


def ids_of(payload):
    items = payload.get("content", payload) if isinstance(payload, dict) else payload
    return [x["id"] for x in items] if isinstance(items, list) else []


failures, checks = 0, 0
def check(ok, text):
    global failures, checks
    checks += 1
    print(("  ok    " if ok else "  FALHA ") + text)
    failures += 0 if ok else 1


tokens = {}
for key, (email, pwd) in TENANTS.items():
    status, data = call("/auth/login", body={"email": email, "password": pwd})
    if status != 200:
        sys.exit(f"Não consegui entrar como {email} (status {status}). O servidor está rodando?")
    tokens[key] = data["token"] if "token" in data else data["accessToken"]

for entity in LISTS:
    seen = {}
    for key in TENANTS:
        status, data = call(f"/{entity}?size=100", tokens[key])
        seen[key] = set(ids_of(data)) if status == 200 and data is not None else None
    if seen["A"] is None or seen["B"] is None:
        print(f"- {entity}: lista indisponível (pulado)")
        continue
    print(f"- {entity}: A tem {len(seen['A'])}, B tem {len(seen['B'])}")
    check(not (seen["A"] & seen["B"]), f"{entity}: nenhum id aparece nas duas organizações")
    for me, other in (("A", "B"), ("B", "A")):
        for rid in sorted(seen[other])[:3]:
            status, _ = call(f"/{entity}/{rid}", tokens[me])
            check(status in (403, 404), f"{entity}/{rid} (da org {other}) visto pela org {me} -> {status}")

for key, other in (("A", "B"), ("B", "A")):
    status, data = call("/settings/users", tokens[key])
    emails = {u["email"] for u in data["content"]} if status == 200 else set()
    check(TENANTS[other][0] not in emails, f"usuários: a org {key} não lista o admin da org {other}")
    status, data = call("/search?q=a", tokens[key])
    check(status == 200, f"busca global responde para a org {key}")

print(f"\n{checks - failures}/{checks} verificações passaram.")
sys.exit(1 if failures else 0)