import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..database import get_db, now_iso
from ..errors import AppError
from ..events import publish
from ..permissions import PERMISSIONS, ROLE_LABEL, ROLES, has_perm, require_perm, user_permissions
from ..security import get_current_user, hash_password

router = APIRouter(prefix="/settings", tags=["Configurações"])
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------- Eu ----------
@router.get("/me")
def my_permissions(db=Depends(get_db), user=Depends(get_current_user)):
    return {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"],
            "roleLabel": ROLE_LABEL[user["role"]], "permissions": user_permissions(db, user)}


# ---------- Organização ----------
class OrgUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=80)


@router.get("/organization")
def get_org(db=Depends(get_db), user=Depends(get_current_user)):
    org = db.execute("SELECT id, name, created_at FROM organizations WHERE id = ?", (user["organization_id"],)).fetchone()
    counts = {t: db.execute(f"SELECT COUNT(*) FROM {t} WHERE organization_id = ?", (user["organization_id"],)).fetchone()[0]
              for t in ("users", "leads", "companies", "contacts", "opportunities")}
    return {"id": org["id"], "name": org["name"], "createdAt": org["created_at"], "counts": counts,
            "canEdit": has_perm(db, user, "settings.org")}


@router.patch("/organization")
def update_org(data: OrgUpdate, db=Depends(get_db), user=Depends(require_perm("settings.org"))):
    db.execute("UPDATE organizations SET name = ? WHERE id = ?", (data.name.strip(), user["organization_id"]))
    publish(db, user, "OrganizationUpdated", "organization", user["organization_id"], {"name": data.name.strip()})
    db.commit()
    return get_org(db, user)


# ---------- Usuários ----------
class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(max_length=160)
    role: str
    password: str = Field(min_length=8, max_length=72)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    role: str | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)


def _user_dto(r) -> dict:
    return {"id": r["id"], "name": r["name"], "email": r["email"], "role": r["role"],
            "roleLabel": ROLE_LABEL.get(r["role"], r["role"]), "active": bool(r["active"]), "createdAt": r["created_at"]}


def _get_user(db, org: int, user_id: int):
    r = db.execute("SELECT * FROM users WHERE id = ? AND organization_id = ?", (user_id, org)).fetchone()
    if r is None:
        raise AppError(404, "USER_NOT_FOUND", "Usuário não encontrado.")
    return r


def _other_active_admins(db, org: int, except_id: int) -> int:
    return db.execute("SELECT COUNT(*) FROM users WHERE organization_id = ? AND role = 'ADMIN' AND active = 1 AND id != ?",
                      (org, except_id)).fetchone()[0]


@router.get("/users")
def list_users(db=Depends(get_db), user=Depends(require_perm("settings.users"))):
    rows = db.execute("SELECT * FROM users WHERE organization_id = ? ORDER BY active DESC, name", (user["organization_id"],)).fetchall()
    return {"content": [_user_dto(r) for r in rows], "roles": [{"value": r, "label": ROLE_LABEL[r]} for r in ROLES]}


@router.post("/users", status_code=201)
def create_user(data: UserCreate, db=Depends(get_db), user=Depends(require_perm("settings.users"))):
    email = data.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise AppError(400, "VALIDATION_ERROR", "Informe um e-mail válido.")
    if data.role not in ROLES:
        raise AppError(400, "INVALID_ROLE", "Papel inválido.")
    if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        raise AppError(409, "EMAIL_ALREADY_EXISTS", "Já existe um usuário com este e-mail.")
    cur = db.execute(
        "INSERT INTO users(organization_id, name, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
        (user["organization_id"], data.name.strip(), email, hash_password(data.password), data.role))
    publish(db, user, "UserCreated", "user", cur.lastrowid, {"name": data.name.strip(), "role": data.role})
    db.commit()
    return _user_dto(_get_user(db, user["organization_id"], cur.lastrowid))


@router.patch("/users/{user_id}")
def update_user(user_id: int, data: UserUpdate, db=Depends(get_db), user=Depends(require_perm("settings.users"))):
    org = user["organization_id"]
    target = _get_user(db, org, user_id)
    changes = data.model_dump(exclude_unset=True)
    if "role" in changes and changes["role"] not in ROLES:
        raise AppError(400, "INVALID_ROLE", "Papel inválido.")
    is_self = target["id"] == user["id"]
    if is_self and (changes.get("active") is False or ("role" in changes and changes["role"] != target["role"])):
        raise AppError(409, "CANNOT_MODIFY_SELF", "Você não pode alterar o seu próprio papel nem desativar a si mesmo.")
    losing_admin = target["role"] == "ADMIN" and target["active"] and (
        changes.get("active") is False or ("role" in changes and changes["role"] != "ADMIN"))
    if losing_admin and _other_active_admins(db, org, target["id"]) == 0:
        raise AppError(409, "LAST_ADMIN", "A organização precisa de pelo menos um administrador ativo.")

    sets, args = [], []
    if "name" in changes:
        sets.append("name = ?"); args.append(changes["name"].strip())
    if "role" in changes:
        sets.append("role = ?"); args.append(changes["role"])
    if "active" in changes:
        sets.append("active = ?"); args.append(1 if changes["active"] else 0)
    if "password" in changes:
        sets.append("password_hash = ?"); args.append(hash_password(changes["password"]))
    if sets:
        db.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", args + [user_id])
        publish(db, user, "UserUpdated", "user", user_id,
                {"name": target["name"], "fields": [k for k in changes if k != "password"] + (["password"] if "password" in changes else [])})
        db.commit()
    return _user_dto(_get_user(db, org, user_id))


# ---------- Permissões ----------
class PermissionChange(BaseModel):
    role: str
    permission: str
    allowed: bool


def _matrix(db, org: int) -> dict:
    overrides = {(r["role"], r["permission"]): bool(r["allowed"]) for r in db.execute(
        "SELECT role, permission, allowed FROM role_permissions WHERE organization_id = ?", (org,))}
    rows = []
    for key, (label, group, defaults, locked) in PERMISSIONS.items():
        values = {}
        for role in ROLES:
            default = role in defaults
            if role == "ADMIN" or locked:
                values[role] = {"allowed": role == "ADMIN", "custom": False, "fixed": True}
            else:
                allowed = overrides.get((role, key), default)
                values[role] = {"allowed": allowed, "custom": (role, key) in overrides, "fixed": False}
        rows.append({"key": key, "label": label, "group": group, "locked": locked, "values": values})
    return {"roles": [{"value": r, "label": ROLE_LABEL[r]} for r in ROLES], "permissions": rows}


@router.get("/permissions")
def get_permissions(db=Depends(get_db), user=Depends(get_current_user)):
    return {**_matrix(db, user["organization_id"]), "canEdit": has_perm(db, user, "settings.permissions")}


@router.put("/permissions")
def change_permission(data: PermissionChange, db=Depends(get_db), user=Depends(require_perm("settings.permissions"))):
    if data.permission not in PERMISSIONS:
        raise AppError(400, "UNKNOWN_PERMISSION", "Permissão desconhecida.")
    label, group, defaults, locked = PERMISSIONS[data.permission]
    if data.role not in ROLES or data.role == "ADMIN":
        raise AppError(400, "INVALID_ROLE", "Escolha Gerente comercial ou Vendedor. O administrador sempre pode tudo.")
    if locked:
        raise AppError(409, "PERMISSION_LOCKED", "Esta permissão é exclusiva do administrador.")
    org = user["organization_id"]
    if data.allowed == (data.role in defaults):      # voltou ao padrão: apaga a exceção
        db.execute("DELETE FROM role_permissions WHERE organization_id = ? AND role = ? AND permission = ?",
                   (org, data.role, data.permission))
    else:
        db.execute(
            "INSERT INTO role_permissions(organization_id, role, permission, allowed, updated_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(organization_id, role, permission) DO UPDATE SET allowed = excluded.allowed, updated_at = excluded.updated_at",
            (org, data.role, data.permission, 1 if data.allowed else 0, now_iso()))
    publish(db, user, "PermissionChanged", "role_permission", None,
            {"role": data.role, "permission": data.permission, "allowed": data.allowed})
    db.commit()
    return {**_matrix(db, org), "canEdit": True}


@router.delete("/permissions")
def reset_permissions(db=Depends(get_db), user=Depends(require_perm("settings.permissions"))):
    db.execute("DELETE FROM role_permissions WHERE organization_id = ?", (user["organization_id"],))
    publish(db, user, "PermissionsReset", "role_permission", None, {})
    db.commit()
    return {**_matrix(db, user["organization_id"]), "canEdit": True}