import json

from .database import now_iso


def publish(db, user, event_type: str, entity: str, entity_id: int, payload: dict | None = None) -> None:
    """Registra um evento de domínio na mesma transação da operação.
    Nas Etapas 8 e 9, notificações, auditoria e automações vão consumir esta tabela."""
    db.execute(
        "INSERT INTO domain_events(organization_id, user_id, type, entity, entity_id, payload, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            user["organization_id"],
            user["id"],
            event_type,
            entity,
            entity_id,
            json.dumps(payload or {}, ensure_ascii=False),
            now_iso(),
        ),
    )