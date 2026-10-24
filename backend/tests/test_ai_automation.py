"""IA simulada (Etapa 8) e automação (Etapa 9): regras de negócio sem depender do relógio real."""
from datetime import datetime, timedelta, timezone

from conftest import make_lead


def _iso(days_ago):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")


def test_lead_novo_recebe_nota_de_0_a_100_com_fatores(api, db):
    from app.scoring import rescore_lead
    lead = make_lead(api, name="Lead Quente", email="q@exemplo.com", phone="11999990000", company="Acme", channel="EMAIL")
    org = api.as_("admin").get("/auth/me").json()["organizationId"]
    rescore_lead(db, org, lead["id"])
    db.commit()
    got = api.as_("admin").get(f"/ai/leads/{lead['id']}")
    assert got.status_code == 200
    body = got.json()
    assert 0 <= body["score"] <= 100 and body["factors"]


def test_pesos_da_ia_so_para_quem_tem_permissao(api):
    assert api.as_("vendedor").put("/ai/weights", {"weights": {}}).status_code in (400, 403)
    assert api.as_("vendedor").delete("/ai/weights").status_code == 403
    assert api.as_("gerente").delete("/ai/weights").status_code == 200


def test_automacao_cria_tarefa_para_lead_novo_uma_unica_vez(api, db):
    from app.automation import run_all
    lead = make_lead(api, name="Lead Recém Chegado")
    titulo = "Fazer o primeiro contato com Lead Recém Chegado"
    conta = lambda: db.execute("SELECT COUNT(*) FROM activities WHERE title = ?", (titulo,)).fetchone()[0]
    assert conta() == 0
    first = run_all(db)
    assert first["executed"] >= 1 and conta() == 1
    second = run_all(db)                                   # mesma situação: não repete
    assert conta() == 1 and second["executed"] == 0
    assert lead["id"]


def test_violacao_de_sla_notifica_uma_vez_so(api, db):
    from app.automation import run_all
    admin = api.as_("admin")
    lead = make_lead(api, name="Lead Esquecido")
    antigo = _iso(30)
    db.execute("UPDATE leads SET created_at = ?, updated_at = ?, last_interaction_at = ? WHERE id = ?",
               (antigo, antigo, antigo, lead["id"]))
    db.commit()
    run_all(db)
    avisos = lambda: sum(1 for n in admin.get("/notifications?size=100").json()["content"] if "Lead Esquecido" in (n["message"] or n["title"]))
    depois_da_primeira = avisos()
    run_all(db)
    assert avisos() == depois_da_primeira


def test_regra_de_automacao_so_gerente_e_admin(api):
    body = {"name": "Minha regra", "trigger": "TASK_OVERDUE", "action": "NOTIFY", "config": {"recipients": "OWNER"}}
    assert api.as_("vendedor").post("/automations", body).status_code == 403
    cat = api.as_("admin").get("/automations").json()["catalog"]
    assert cat["triggers"] and cat["actions"]


def test_notificacoes_so_do_proprio_usuario(api, db):
    me_v = api.as_("vendedor").get("/auth/me").json()
    me_a = api.as_("admin").get("/auth/me").json()
    db.execute("INSERT INTO notifications(organization_id, user_id, type, title, message, created_at) VALUES (?, ?, 'TESTE', 'Só do admin', 'x', ?)",
               (me_a["organizationId"], me_a["id"], _iso(0)))
    db.commit()
    mine = api.as_("admin").get("/notifications").json()["content"]
    theirs = api.as_("vendedor").get("/notifications").json()["content"]
    assert any(n["title"] == "Só do admin" for n in mine)
    assert not any(n["title"] == "Só do admin" for n in theirs)
    assert me_v["id"] != me_a["id"]