"""Etapa 10: permissões por papel (RBAC).

Cada permissão tem um padrão por papel (definido aqui). O ADMIN pode mudar os padrões de
SALES_MANAGER e SALES na tela Configurações > Permissões; as mudanças ficam na tabela
role_permissions, por organização. O ADMIN sempre pode tudo, e as permissões marcadas como
"travadas" (settings.*) são só do ADMIN, para ninguém se trancar fora do sistema.
"""
from fastapi import Depends

from .database import get_db
from .errors import AppError
from .security import get_current_user

ROLES = ["ADMIN", "SALES_MANAGER", "SALES"]
ROLE_LABEL = {"ADMIN": "Administrador", "SALES_MANAGER": "Gerente comercial", "SALES": "Vendedor"}
MANAGERS = ("ADMIN", "SALES_MANAGER")

# chave -> (rótulo, grupo, papéis com acesso por padrão, travada só para ADMIN?)
PERMISSIONS: dict[str, tuple[str, str, tuple[str, ...], bool]] = {
    "data.import": ("Importar dados por CSV", "Dados", MANAGERS, False),
    "data.dedupe": ("Ver registros duplicados", "Dados", MANAGERS, False),
    "data.merge": ("Mesclar registros duplicados", "Dados", MANAGERS, False),
    "audit.read": ("Consultar a auditoria", "Gestão", MANAGERS, False),
    "automation.manage": ("Criar e editar automações", "Gestão", MANAGERS, False),
    "goals.manage": ("Definir metas e prazos de SLA", "Gestão", MANAGERS, False),
    "ai.weights": ("Ajustar os pesos da IA", "Gestão", MANAGERS, False),
    "settings.users": ("Gerenciar usuários", "Configurações", ("ADMIN",), True),
    "settings.org": ("Editar dados da organização", "Configurações", ("ADMIN",), True),
    "settings.permissions": ("Alterar permissões dos papéis", "Configurações", ("ADMIN",), True),
}


def has_perm(db, user, key: str) -> bool:
    label, group, default_roles, locked = PERMISSIONS[key]
    if user["role"] == "ADMIN":
        return True
    if locked:
        return False
    row = db.execute(
        "SELECT allowed FROM role_permissions WHERE organization_id = ? AND role = ? AND permission = ?",
        (user["organization_id"], user["role"], key),
    ).fetchone()
    if row is not None:
        return bool(row["allowed"])
    return user["role"] in default_roles


def user_permissions(db, user) -> list[str]:
    return [k for k in PERMISSIONS if has_perm(db, user, k)]


def require_perm(key: str):
    """Dependência do FastAPI: Depends(require_perm("data.import"))."""
    def dependency(user=Depends(get_current_user), db=Depends(get_db)):
        if not has_perm(db, user, key):
            raise AppError(403, "FORBIDDEN", "Você não tem permissão para esta ação.")
        return user
    return dependency