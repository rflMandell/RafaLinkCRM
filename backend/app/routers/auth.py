from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..database import get_db
from ..errors import AppError
from ..security import create_token, get_current_user, verify_password

router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


def _public_user(user) -> dict:
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "organizationId": user["organization_id"],
    }


@router.post("/login")
def login(data: LoginRequest, db=Depends(get_db)):
    user = db.execute(
        "SELECT * FROM users WHERE email = ?", (data.email.strip().lower(),)
    ).fetchone()
    if user is None or not verify_password(data.password, user["password_hash"]):
        raise AppError(401, "INVALID_CREDENTIALS", "E-mail ou senha inválidos.")
    if not user["active"]:
        raise AppError(403, "USER_INACTIVE", "Usuário desativado.")
    return {
        "accessToken": create_token(user),
        "tokenType": "Bearer",
        "user": _public_user(user),
    }


@router.get("/me")
def me(user=Depends(get_current_user)):
    return _public_user(user)