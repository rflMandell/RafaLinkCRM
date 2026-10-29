# RafaLink CRM: guia de desenvolvimento

Simulação local do CRM descrito no `README.md`. Frontend em HTML puro, backend em Python (FastAPI) com banco SQLite.
Tudo roda no seu computador e os dados ficam em `backend/data/rafalink.db`.

## Começando (1 comando)

Pré-requisito: Python 3.10 ou mais novo.

```bash
python start.py          # Windows: py start.py   |   Mac: python3 start.py
```

Na primeira vez ele cria o ambiente virtual, instala as dependências, sobe o servidor e abre o navegador em
`http://localhost:8000/login.html`. Depois disso é só rodar o mesmo comando (Ctrl+C para parar).

| Comando | O que faz |
|---|---|
| `python start.py --demo` | gera dados de demonstração (empresas, leads, oportunidades, atividades) |
| `python start.py --dev` | reinicia o servidor sozinho quando você edita o código |
| `python start.py --test` | roda os testes automáticos |
| `python start.py --reset-db` | apaga o banco local e recomeça do zero (pede confirmação) |
| `python start.py --port 8001` | usa outra porta |
| `python start.py --no-browser` | não abre o navegador |

Os atalhos `scripts/start.bat` (Windows) e `scripts/start.sh` (Mac) chamam o mesmo `start.py`.

## Usuários de demonstração

| Papel | E-mail | Senha |
|---|---|---|
| Administrador | admin@rafalink.com | admin123 |
| Gerente comercial | gerente@rafalink.com | gerente123 |
| Vendedor | vendedor@rafalink.com | vendedor123 |
| Admin da 2ª empresa (teste de isolamento) | admin@outraempresa.com | admin123 |

## Estrutura

```text
rafalinkfront/
├── start.py                 ← inicia tudo
├── frontend/                ← páginas HTML, css/ e js/ (servidas pelo backend)
├── backend/
│   ├── app/                 ← API (main.py, database.py, routers/, regras)
│   ├── tests/               ← testes automáticos (pytest)
│   ├── data/                ← banco e log (não vai para o Git)
│   └── requirements*.txt
├── scripts/                 ← seed_demo.py, check_isolation.py, start.bat/.sh
└── docs/DESENVOLVIMENTO.md  ← este guia
```

## Documentação da API

Com o servidor rodando: `http://localhost:8000/docs` (para chamar rotas protegidas, faça `POST /api/v1/auth/login`
e use o `accessToken` no botão Authorize). Todos os erros seguem o mesmo formato:

```json
{ "timestamp": "...", "status": 409, "code": "EMAIL_ALREADY_EXISTS", "message": "Já existe um usuário com este e-mail.", "path": "/api/v1/settings/users" }
```

## Testes

```bash
python start.py --test                 # tudo
python start.py --test -k permissoes   # só os testes cujo nome contém "permissoes"
```

Os testes usam uma cópia temporária do banco e **nunca tocam** no seu `backend/data/rafalink.db`.
Cobrem login e erros, leads (funil e conversão), permissões, importação CSV, duplicados, isolamento entre
organizações, busca e automação. Ao criar uma funcionalidade nova, copie o estilo de um teste existente.

## Dados de demonstração

```bash
python start.py --demo
```

Cria 12 empresas, 30 contatos, ~50 leads, 22 oportunidades e 40 atividades com datas dos últimos 90 dias, mais
3 pares de leads duplicados para você testar **Configurações > Duplicados**. Rodar de novo não duplica nada
(`--force` no `scripts/seed_demo.py` cria mais

## Isolamento entre empresas

`python scripts/check_isolation.py` (com o servidor rodando) confere que a organização "RafaLink Demo" e a "Outra
Empresa (demo)" não enxergam os dados uma da outra.

## Logs e problemas comuns

- Erros inesperados aparecem no terminal e ficam em `backend/data/rafalink.log` (guarda os últimos ~4 MB).
- **"Porta ocupada"**: outro programa usa a 8000. Rode `python start.py --port 8001`.
- **Tela mostra "Não consegui falar com o servidor"**: o backend não está rodando. Rode `python start.py`.
- **"python não encontrado" (Windows)**: use `py start.py`.
- **Quero recomeçar do zero**: `python start.py --reset-db`.
- **Abri o front pelo Live Server (porta 5500)**: funciona, mas o backend precisa estar na 8000.
- **Segurança**: o projeto é para uso local. Para expor em rede, defina a variável `JWT_SECRET` e troque as senhas
  de demonstração.

## Etapas implementadas

0-1 base e login · 2 leads · 3 empresas e contatos · 4 pipeline/kanban · 5 atividades, agenda e Cliente 360 ·
6 campanhas e analytics · 7 forecast, metas e SLA · 8 IA simulada · 9 automação, notificações e auditoria ·
10 permissões, multi-empresa, busca global, importação CSV e duplicados · 11 polimento (testes, erros, demo, start único).