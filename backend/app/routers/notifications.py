from math import ceil

from fastapi import APIRouter, Depends, Query, Response

from ..database import get_db, now_iso
from ..errors import AppError
from ..security import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notificações"])


def _dto(r) -> dict:
    return {"id": r["id"], "type": r["type"], "title": r["title"], "message": r["message"],
            "entity": r["entity"], "entityId": r["entity_id"], "read": r["read_at"] is not None,
            "createdAt": r["created_at"]}


def _get(db, user, notif_id: int):
    r = db.execute("SELECT * FROM notifications WHERE id = ? AND user_id = ?", (notif_id, user["id"])).fetchone()
    if r is None:
        raise AppError(404, "NOTIFICATION_NOT_FOUND", "Notificação não encontrada.")
    return r


@router.get("")
def list_notifications(unread: bool = False, page: int = Query(0, ge=0), size: int = Query(20, ge=1, le=100),
                       db=Depends(get_db), user=Depends(get_current_user)):
    where, args = "user_id = ?", [user["id"]]
    if unread:
        where += " AND read_at IS NULL"
    total = db.execute(f"SELECT COUNT(*) FROM notifications WHERE {where}", args).fetchone()[0]
    rows = db.execute(f"SELECT * FROM notifications WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                      args + [size, page * size]).fetchall()
    unread_total = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_at IS NULL",
                              (user["id"],)).fetchone()[0]
    return {"content": [_dto(r) for r in rows], "page": page, "size": size, "totalElements": total,
            "totalPages": ceil(total / size) if total else 0, "unread": unread_total}


@router.get("/unread-count")
def unread_count(db=Depends(get_db), user=Depends(get_current_user)):
    n = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_at IS NULL", (user["id"],)).fetchone()[0]
    return {"count": n}


@router.post("/read-all")
def read_all(db=Depends(get_db), user=Depends(get_current_user)):
    cur = db.execute("UPDATE notifications SET read_at = ? WHERE user_id = ? AND read_at IS NULL", (now_iso(), user["id"]))
    db.commit()
    return {"updated": cur.rowcount}


@router.post("/{notif_id}/read")
def mark_read(notif_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    _get(db, user, notif_id)
    db.execute("UPDATE notifications SET read_at = COALESCE(read_at, ?) WHERE id = ?", (now_iso(), notif_id))
    db.commit()
    return _dto(_get(db, user, notif_id))


@router.delete("/{notif_id}", status_code=204)
def delete_notification(notif_id: int, db=Depends(get_db), user=Depends(get_current_user)):
    _get(db, user, notif_id)
    db.execute("DELETE FROM notifications WHERE id = ?", (notif_id,))
    db.commit()
    return Response(status_code=204)