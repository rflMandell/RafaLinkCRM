import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .database import get_db
from .errors import AppError

# Em produção, defina a variável de ambiente JWT_SECRET. Aqui é só ambiente local.
JWT_SECRET = os.getenv("JWT_SECRET", "rafalink-dev-secret-troque-em-producao-0123456789")
JWT_ALGORITHM = "HS256"
TOKEN_HOURS = 8

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt, expected = stored.split("$", 1)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return hmac.compare_digest(digest.hex(), expected)


def create_token(user) -> str:
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "org": user["organization_id"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db=Depends(get_db),
):
    """RN01: recursos protegidos exigem usuário autenticado."""
    if creds is None:
        raise AppError(401, "NOT_AUTHENTICATED", "Faça login para continuar.")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise AppError(401, "TOKEN_EXPIRED", "Sua sessão expirou. Faça login novamente.")
    except jwt.PyJWTError:
        raise AppError(401, "INVALID_TOKEN", "Token inválido.")

    user = db.execute(
        "SELECT * FROM users WHERE id = ? AND active = 1", (int(payload["sub"]),)
    ).fetchone()
    if user is None:
        raise AppError(401, "USER_NOT_FOUND", "Usuário não encontrado ou inativo.")
    return user