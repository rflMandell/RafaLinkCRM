"""IA simulada do RafaLink: regras e pesos 100% no backend (sem modelo de verdade).

Três cérebros, todos explicáveis (cada ponto tem um motivo em português):
  1) score_lead        -> nota de 0 a 100 + fatores
  2) churn_company     -> risco de perda de 0 a 100 + fatores
  3) *_actions         -> próxima melhor ação (lista priorizada)

Os pesos têm um valor padrão aqui em WEIGHTS e podem ser ajustados por organização
na tabela ai_weights (tela IA > Regras e pesos, só ADMIN/SALES_MANAGER).
"""
import json
from datetime import datetime, timedelta, timezone

from .database import now_iso
from .routers.sla import POLICIES, ensure_policies

# chave -> (valor padrão, rótulo, grupo, mínimo, máximo)
WEIGHTS: dict[str, tuple[float, str, str, float, float]] = {
    # ---- Lead ----
    "lead.base": (10, "Pontos iniciais de todo lead", "lead", 0, 40),
    "lead.has_email": (5, "Tem e-mail", "lead", 0, 30),
    "lead.has_phone": (5, "Tem telefone", "lead", 0, 30),
    "lead.has_company": (5, "Informou a empresa", "lead", 0, 30),
    "lead.channel_quality": (15, "Qualidade do canal (máx.)", "lead", 0, 40),
    "lead.recent_3d": (20, "Interação nos últimos 3 dias", "lead", 0, 40),
    "lead.recent_10d": (10, "Interação entre 4 e 10 dias", "lead", 0, 40),
    "lead.stale_30d": (-15, "Sem interação há mais de 30 dias", "lead", -40, 0),
    "lead.never_contacted": (-8, "Nunca foi contatado (há 2+ dias)", "lead", -40, 0),
    "lead.per_done_activity": (4, "Por atividade concluída (até 3)", "lead", 0, 15),
    "lead.status_step": (8, "Por etapa avançada no funil", "lead", 0, 20),
    "lead.has_campaign": (5, "Veio de uma campanha", "lead", 0, 30),
    "lead.fast_first_contact": (5, "Primeiro contato dentro do SLA", "lead", 0, 30),
    # ---- Churn (risco de perda do cliente) ----
    "churn.inactive_30d": (12, "Sem interação há mais de 30 dias", "churn", 0, 50),
    "churn.inactive_60d": (10, "Sem interação há mais de 60 dias (soma)", "churn", 0, 50),
    "churn.inactive_90d": (8, "Sem interação há mais de 90 dias (soma)", "churn", 0, 50),
    "churn.per_overdue_task": (6, "Por tarefa atrasada (até 3)", "churn", 0, 30),
    "churn.stale_opp": (10, "Oportunidade parada além do SLA", "churn", 0, 40),
    "churn.no_open_opp": (12, "Nenhuma oportunidade aberta", "churn", 0, 40),
    "churn.per_lost_recent": (8, "Por oportunidade perdida em 90 dias (até 2)", "churn", 0, 30),
    "churn.no_contact": (10, "Nenhum contato ativo cadastrado", "churn", 0, 40),
    "churn.no_next_activity": (10, "Nenhuma atividade futura agendada", "churn", 0, 40),
    "churn.recent_win": (-15, "Compra fechada nos últimos 90 dias", "churn", -50, 0),
}

# Qualidade de cada canal (multiplicada por lead.channel_quality)
CHANNEL_QUALITY = {
    "EVENTO": 1.0, "SITE": 0.8, "OUTROS": 0.8, "EMAIL": 0.6,
    "WHATSAPP": 0.6, "REDES_SOCIAIS": 0.5, "SMS": 0.3,
}
STATUS_STEPS = {"NOVO": 0, "EM_CONTATO": 1, "QUALIFICADO": 2, "OPORTUNIDADE": 3}
SCORED_STATUSES = tuple(STATUS_STEPS)

HOT_MIN, WARM_MIN = 70, 40          # QUENTE / MORNO / FRIO
CHURN_HIGH, CHURN_MID = 60, 30      # ALTO / MEDIO / BAIXO
LEVEL_LABEL = {"QUENTE": "Quente", "MORNO": "Morno", "FRIO": "Frio"}
CHURN_LABEL = {"ALTO": "Alto", "MEDIO": "Médio", "BAIXO": "Baixo"}
PRIORITY_LABEL = {1: "Alta", 2: "Média", 3: "Baixa"}


# ---------- Pesos ----------
def load_weights(db, org: int) -> dict[str, float]:
    w = {k: v[0] for k, v in WEIGHTS.items()}
    for r in db.execute("SELECT key, value FROM ai_weights WHERE organization_id = ?", (org,)):
        if r["key"] in w:
            w[r["key"]] = r["value"]
    return w


def sla_limits(db, org: int) -> dict:
    """Usa os prazos da Etapa 7 para a IA falar a mesma língua do SLA."""
    ensure_policies(db, org)
    rows = {r["kind"]: r["threshold"] for r in db.execute(
        "SELECT kind, threshold FROM sla_policies WHERE organization_id = ?", (org,))}
    return {k: rows.get(k, POLICIES[k][2]) for k in POLICIES}


def _age_days(ts: str | None, now: datetime) -> float | None:
    if not ts:
        return None
    return (now - datetime.fromisoformat(ts)).total_seconds() / 86400


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _level(score: float) -> str:
    return "QUENTE" if score >= HOT_MIN else "MORNO" if score >= WARM_MIN else "FRIO"


def _churn_level(risk: float) -> str:
    return "ALTO" if risk >= CHURN_HIGH else "MEDIO" if risk >= CHURN_MID else "BAIXO"


# ---------- 1) Score do lead ----------
LEAD_CTX_SQL = (
    "SELECT l.*, u.name AS owner_name, "
    " (SELECT COUNT(*) FROM activities a WHERE a.lead_id = l.id AND a.completed_at IS NOT NULL) AS done_count, "
    " (SELECT COUNT(*) FROM activities a WHERE a.lead_id = l.id AND a.status = 'PENDENTE') AS pending_count, "
    " (SELECT COUNT(*) FROM activities a WHERE a.lead_id = l.id AND a.status = 'PENDENTE' AND a.due_at < ?) AS overdue_count "
    "FROM leads l LEFT JOIN users u ON u.id = l.owner_id "
)


def lead_rows(db, org: int, now: datetime, lead_id: int | None = None, owner: int | None = None):
    sql = LEAD_CTX_SQL + "WHERE l.organization_id = ? "
    args: list = [now.isoformat(timespec="seconds"), org]
    if lead_id is not None:
        sql += "AND l.id = ? "
        args.append(lead_id)
    else:
        sql += "AND l.status IN (%s) " % ",".join("?" * len(SCORED_STATUSES))
        args += list(SCORED_STATUSES)
    if owner is not None:
        sql += "AND l.owner_id = ? "
        args.append(owner)
    return db.execute(sql, args).fetchall()


def score_lead(r, w: dict, now: datetime, limits: dict) -> dict:
    factors: list[dict] = []

    def add(key: str, points: float, detail: str):
        if points:
            factors.append({"key": key, "label": WEIGHTS[key][1], "points": round(points, 1), "detail": detail})

    add("lead.base", w["lead.base"], "ponto de partida")
    if r["email"]:
        add("lead.has_email", w["lead.has_email"], r["email"])
    if r["phone"]:
        add("lead.has_phone", w["lead.has_phone"], r["phone"])
    if r["company"]:
        add("lead.has_company", w["lead.has_company"], r["company"])
    q = CHANNEL_QUALITY.get(r["channel"] or "", 0)
    if q:
        add("lead.channel_quality", w["lead.channel_quality"] * q, f"canal {r['channel']} (qualidade {int(q * 100)}%)")

    idle = _age_days(r["last_interaction_at"], now)
    if idle is None:
        created_age = _age_days(r["created_at"], now) or 0
        if created_age >= 2:
            add("lead.never_contacted", w["lead.never_contacted"], f"cadastrado há {int(created_age)} dias sem contato")
    elif idle <= 3:
        add("lead.recent_3d", w["lead.recent_3d"], f"última interação há {max(int(idle), 0)} dia(s)")
    elif idle <= 10:
        add("lead.recent_10d", w["lead.recent_10d"], f"última interação há {int(idle)} dias")
    elif idle > 30:
        add("lead.stale_30d", w["lead.stale_30d"], f"última interação há {int(idle)} dias")

    done = min(r["done_count"], 3)
    if done:
        add("lead.per_done_activity", w["lead.per_done_activity"] * done,
            _plural(r["done_count"], "atividade concluída", "atividades concluídas"))
    step = STATUS_STEPS.get(r["status"], 0)
    if step:
        add("lead.status_step", w["lead.status_step"] * step, f"status {r['status']}")
    if r["campaign_id"]:
        add("lead.has_campaign", w["lead.has_campaign"], "atribuído a uma campanha")
    if r["first_contact_at"]:
        delay_h = (datetime.fromisoformat(r["first_contact_at"]) - datetime.fromisoformat(r["created_at"])).total_seconds() / 3600
        if delay_h <= limits["FIRST_CONTACT"]:
            add("lead.fast_first_contact", w["lead.fast_first_contact"], f"contatado em {max(round(delay_h), 0)}h")

    raw = sum(f["points"] for f in factors)
    score = int(max(0, min(100, round(raw))))
    return {"score": score, "level": _level(score), "levelLabel": LEVEL_LABEL[_level(score)],
            "raw": round(raw, 1), "factors": sorted(factors, key=lambda f: -abs(f["points"]))}


def lead_actions(r, sc: dict, now: datetime, limits: dict) -> list[dict]:
    out: list[dict] = []
    status = r["status"]

    def act(code, priority, title, reason, kind="TAREFA"):
        out.append({"code": code, "priority": priority, "priorityLabel": PRIORITY_LABEL[priority],
                    "title": title, "reason": reason, "suggestedType": kind})

    age_h = (_age_days(r["created_at"], now) or 0) * 24
    idle_d = _age_days(r["last_interaction_at"] or r["created_at"], now) or 0
    lim_fc, lim_idle = limits["FIRST_CONTACT"], limits["LEAD_IDLE"]

    if status == "NOVO" and not r["first_contact_at"]:
        if age_h > lim_fc:
            act("FIRST_CONTACT_LATE", 1, "Fazer o primeiro contato agora",
                f"O prazo de {lim_fc:g}h para o primeiro contato estourou há {round(age_h - lim_fc)}h.", "LIGACAO")
        elif age_h >= lim_fc * 0.75:
            act("FIRST_CONTACT_SOON", 1, "Fazer o primeiro contato hoje",
                f"Faltam {max(round(lim_fc - age_h), 0)}h para estourar o SLA de primeiro contato.", "LIGACAO")
        else:
            act("FIRST_CONTACT", 1 if sc["level"] == "QUENTE" else 2, "Fazer o primeiro contato",
                "Lead novo ainda sem contato." + (" Nota alta: priorize." if sc["level"] == "QUENTE" else ""), "LIGACAO")
    if status in ("EM_CONTATO", "QUALIFICADO", "OPORTUNIDADE") and idle_d > lim_idle:
        act("RESUME_CONTACT", 1, "Retomar o contato",
            f"Sem interação há {int(idle_d)} dias (limite do SLA: {lim_idle:g}).", "LIGACAO")
    if status == "QUALIFICADO" and not r["opportunity_id"] and sc["score"] >= WARM_MIN:
        act("CONVERT", 1 if sc["level"] == "QUENTE" else 2, "Converter em oportunidade",
            f"Lead qualificado com nota {sc['score']} e nenhuma oportunidade aberta.")
    if sc["level"] == "QUENTE" and r["pending_count"] == 0 and status != "NOVO":
        act("MEETING", 1, "Agendar reunião ou demonstração",
            f"Lead quente (nota {sc['score']}) sem nenhuma tarefa pendente.", "REUNIAO")
    if status == "EM_CONTATO" and r["done_count"] >= 2 and sc["score"] >= WARM_MIN:
        act("QUALIFY", 2, "Qualificar o lead",
            f"{r['done_count']} atividades concluídas e nota {sc['score']}: hora de confirmar interesse e orçamento.")
    if r["overdue_count"] > 0:
        act("OVERDUE", 2, "Resolver tarefa atrasada",
            _plural(r["overdue_count"], "tarefa atrasada", "tarefas atrasadas") + " neste lead.")
    if r["pending_count"] == 0 and status in SCORED_STATUSES:
        act("FOLLOW_UP", 2, "Agendar o próximo follow-up", "Nenhuma tarefa pendente neste lead.")
    if not r["email"] and not r["phone"]:
        act("COMPLETE_DATA", 3, "Completar dados de contato", "Sem e-mail e sem telefone cadastrados.")

    if not out:
        act("WATCH", 3, "Acompanhar", "Nada urgente: existe tarefa pendente e o lead está no ritmo.")
    seen, uniq = set(), []
    for a in sorted(out, key=lambda a: a["priority"]):
        if a["code"] not in seen:
            seen.add(a["code"])
            uniq.append(a)
    return uniq


# ---------- 2) Risco de churn do cliente ----------
def customer_contexts(db, org: int, now: datetime, company_id: int | None = None, owner: int | None = None):
    """Um dicionário por cliente (empresa tipo CLIENTE ou com venda ganha) com os números que a IA precisa."""
    iso = now.isoformat(timespec="seconds")
    cond, args = "", [org]
    if company_id is not None:
        cond += " AND c.id = ?"
        args.append(company_id)
    if owner is not None:
        cond += " AND c.owner_id = ?"
        args.append(owner)
    companies = db.execute(
        "SELECT c.*, u.name AS owner_name FROM companies c LEFT JOIN users u ON u.id = c.owner_id "
        "WHERE c.organization_id = ?" + cond +
        " AND (c.type = 'CLIENTE' OR EXISTS (SELECT 1 FROM opportunities o WHERE o.company_id = c.id AND o.status = 'GANHA'))",
        args,
    ).fetchall()

    act = {r["cid"]: r for r in db.execute(
        "SELECT COALESCE(a.company_id, ct.company_id, o.company_id) AS cid, "
        " MAX(a.completed_at) AS last_done, "
        " SUM(CASE WHEN a.status = 'PENDENTE' AND a.due_at < ? THEN 1 ELSE 0 END) AS overdue, "
        " SUM(CASE WHEN a.status = 'PENDENTE' AND a.due_at >= ? THEN 1 ELSE 0 END) AS upcoming "
        "FROM activities a LEFT JOIN contacts ct ON ct.id = a.contact_id "
        "LEFT JOIN opportunities o ON o.id = a.opportunity_id "
        "WHERE a.organization_id = ? GROUP BY cid", (iso, iso, org))}
    opp = {r["company_id"]: r for r in db.execute(
        "SELECT company_id, "
        " SUM(CASE WHEN status = 'ABERTA' THEN 1 ELSE 0 END) AS open_count, "
        " MAX(CASE WHEN status = 'GANHA' THEN closed_at END) AS last_win, "
        " SUM(CASE WHEN status = 'PERDIDA' AND closed_at >= ? THEN 1 ELSE 0 END) AS lost_recent "
        "FROM opportunities WHERE organization_id = ? AND company_id IS NOT NULL GROUP BY company_id",
        ((now.replace(microsecond=0) - timedelta(days=90)).isoformat(), org))}
    stale = {r["company_id"]: r["n"] for r in db.execute(
        "SELECT company_id, COUNT(*) AS n FROM opportunities WHERE organization_id = ? AND status = 'ABERTA' "
        "AND stage_changed_at < ? GROUP BY company_id",
        (org, (now - timedelta(days=sla_limits(db, org)["OPP_STALE"])).isoformat(timespec="seconds")))}
    contacts = {r["company_id"]: r["n"] for r in db.execute(
        "SELECT company_id, COUNT(*) AS n FROM contacts WHERE organization_id = ? AND status = 'ATIVO' GROUP BY company_id",
        (org,))}

    out = []
    for c in companies:
        a, o = act.get(c["id"]), opp.get(c["id"])
        out.append({
            "company": c,
            "last_done": a["last_done"] if a else None,
            "overdue": (a["overdue"] or 0) if a else 0,
            "upcoming": (a["upcoming"] or 0) if a else 0,
            "open_count": (o["open_count"] or 0) if o else 0,
            "last_win": o["last_win"] if o else None,
            "lost_recent": (o["lost_recent"] or 0) if o else 0,
            "stale": stale.get(c["id"], 0),
            "contacts": contacts.get(c["id"], 0),
        })
    return out


def churn_company(ctx: dict, w: dict, now: datetime) -> dict:
    factors: list[dict] = []

    def add(key, points, detail):
        if points:
            factors.append({"key": key, "label": WEIGHTS[key][1], "points": round(points, 1), "detail": detail})

    c = ctx["company"]
    last = ctx["last_done"] or ctx["last_win"] or c["created_at"]
    idle = _age_days(last, now) or 0
    for days, key in ((30, "churn.inactive_30d"), (60, "churn.inactive_60d"), (90, "churn.inactive_90d")):
        if idle > days:
            add(key, w[key], f"última interação há {int(idle)} dias")
    if ctx["overdue"]:
        add("churn.per_overdue_task", w["churn.per_overdue_task"] * min(ctx["overdue"], 3),
            _plural(ctx["overdue"], "tarefa atrasada", "tarefas atrasadas"))
    if ctx["stale"]:
        add("churn.stale_opp", w["churn.stale_opp"], _plural(ctx["stale"], "oportunidade parada", "oportunidades paradas"))
    if ctx["open_count"] == 0:
        add("churn.no_open_opp", w["churn.no_open_opp"], "nada em negociação")
    if ctx["lost_recent"]:
        add("churn.per_lost_recent", w["churn.per_lost_recent"] * min(ctx["lost_recent"], 2),
            _plural(ctx["lost_recent"], "oportunidade perdida", "oportunidades perdidas"))
    if ctx["contacts"] == 0:
        add("churn.no_contact", w["churn.no_contact"], "ninguém para falar na empresa")
    if ctx["upcoming"] == 0:
        add("churn.no_next_activity", w["churn.no_next_activity"], "nenhuma tarefa futura")
    win_age = _age_days(ctx["last_win"], now)
    if win_age is not None and win_age <= 90:
        add("churn.recent_win", w["churn.recent_win"], f"compra há {int(win_age)} dias")

    raw = sum(f["points"] for f in factors)
    risk = int(max(0, min(100, round(raw))))
    lvl = _churn_level(risk)
    return {"risk": risk, "level": lvl, "levelLabel": CHURN_LABEL[lvl], "idleDays": int(idle),
            "factors": sorted(factors, key=lambda f: -abs(f["points"]))}


def company_actions(ctx: dict, ch: dict) -> list[dict]:
    out: list[dict] = []

    def act(code, priority, title, reason, kind="TAREFA"):
        out.append({"code": code, "priority": priority, "priorityLabel": PRIORITY_LABEL[priority],
                    "title": title, "reason": reason, "suggestedType": kind})

    if ch["level"] == "ALTO":
        act("REACTIVATE", 1, "Reativar o cliente", f"Risco de perda {ch['risk']}/100. Ligue para o contato principal.", "LIGACAO")
    elif ch["level"] == "MEDIO":
        act("CHECK_IN", 2, "Agendar um check-in", f"Risco de perda {ch['risk']}/100. Mostre que você está por perto.", "REUNIAO")
    if ctx["overdue"]:
        act("OVERDUE", 2, "Resolver tarefas atrasadas", _plural(ctx["overdue"], "tarefa atrasada", "tarefas atrasadas") + " com este cliente.")
    if ctx["open_count"] == 0:
        act("UPSELL", 2, "Apresentar uma nova oferta", "Cliente sem nenhuma oportunidade em andamento.", "REUNIAO")
    if ctx["contacts"] == 0:
        act("ADD_CONTACT", 2, "Cadastrar um contato", "A empresa não tem contato ativo.")
    if not out:
        act("WATCH", 3, "Manter o relacionamento", "Cliente saudável: continue acompanhando.")
    return sorted(out, key=lambda a: a["priority"])


# ---------- 3) Oportunidades ----------
def opportunity_rows(db, org: int, now: datetime, opp_id: int | None = None, owner: int | None = None):
    sql = (
        "SELECT o.*, u.name AS owner_name, "
        " (SELECT COUNT(*) FROM activities a WHERE a.opportunity_id = o.id AND a.status = 'PENDENTE') AS pending_count, "
        " (SELECT COUNT(*) FROM activities a WHERE a.opportunity_id = o.id AND a.status = 'PENDENTE' AND a.due_at < ?) AS overdue_count "
        "FROM opportunities o LEFT JOIN users u ON u.id = o.owner_id "
        "WHERE o.organization_id = ? AND o.status = 'ABERTA' "
    )
    args: list = [now.isoformat(timespec="seconds"), org]
    if opp_id is not None:
        sql += "AND o.id = ? "
        args.append(opp_id)
    if owner is not None:
        sql += "AND o.owner_id = ? "
        args.append(owner)
    return db.execute(sql, args).fetchall()


def opportunity_actions(o, now: datetime, limits: dict) -> list[dict]:
    out: list[dict] = []

    def act(code, priority, title, reason, kind="TAREFA"):
        out.append({"code": code, "priority": priority, "priorityLabel": PRIORITY_LABEL[priority],
                    "title": title, "reason": reason, "suggestedType": kind})

    stale = _age_days(o["stage_changed_at"], now) or 0
    today = now.date().isoformat()
    lim = limits["OPP_STALE"]
    if stale > lim:
        act("UNBLOCK", 1, "Destravar a negociação", f"Parada na mesma etapa há {int(stale)} dias (limite do SLA: {lim:g}).", "LIGACAO")
    if o["expected_close_date"] and o["expected_close_date"] < today:
        act("UPDATE_DATE", 1, "Atualizar a data de fechamento", f"A data prevista ({o['expected_close_date'][8:10]}/{o['expected_close_date'][5:7]}) já passou.")
    if o["probability"] >= 80:
        act("CLOSE", 1, "Fechar o negócio", f"Probabilidade de {o['probability']}%: leve a proposta final para assinatura.", "REUNIAO")
    elif o["probability"] >= 40 and o["pending_count"] == 0:
        act("PROPOSAL", 2, "Enviar ou revisar a proposta", f"Probabilidade de {o['probability']}% e nenhuma tarefa pendente.")
    if o["overdue_count"]:
        act("OVERDUE", 2, "Resolver tarefa atrasada", _plural(o["overdue_count"], "tarefa atrasada", "tarefas atrasadas") + " nesta oportunidade.")
    if not o["expected_close_date"]:
        act("SET_DATE", 2, "Definir a data prevista de fechamento", "Sem data, a oportunidade não entra na previsão (Forecast).")
    if o["pending_count"] == 0:
        act("NEXT_STEP", 2, "Agendar o próximo passo", "Nenhuma tarefa pendente nesta oportunidade.")
    if o["value"] >= 50000 and o["probability"] < 40:
        act("ESCALATE", 3, "Envolver o gerente", f"Negócio grande ({o['value']:,.0f}) com probabilidade baixa.".replace(",", "."))
    if not out:
        act("WATCH", 3, "Acompanhar", "Negociação em dia.")
    seen, uniq = set(), []
    for a in sorted(out, key=lambda a: a["priority"]):
        if a["code"] not in seen:
            seen.add(a["code"])
            uniq.append(a)
    return uniq


# ---------- Persistência do score ----------
def apply_score(db, lead_id: int, sc: dict) -> None:
    db.execute(
        "UPDATE leads SET score = ?, score_factors = ?, scored_at = ? WHERE id = ?",
        (sc["score"], json.dumps(sc["factors"], ensure_ascii=False), now_iso(), lead_id),
    )


def rescore_lead(db, org: int, lead_id: int) -> dict | None:
    """Use este helper nos pontos onde o lead muda (criar, mudar status, nova atividade)."""
    now = datetime.now(timezone.utc)
    rows = lead_rows(db, org, now, lead_id=lead_id)
    if not rows or rows[0]["status"] not in SCORED_STATUSES:
        return None
    sc = score_lead(rows[0], load_weights(db, org), now, sla_limits(db, org))
    apply_score(db, lead_id, sc)
    return sc