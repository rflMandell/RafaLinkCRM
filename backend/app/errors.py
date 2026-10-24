import logging
import sqlite3
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("rafalink")


class AppError(Exception):
    """Erro de negócio com o formato padronizado do README."""

    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message


def _body(status: int, code: str, message: str, path: str) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "code": code,
        "message": message,
        "path": path,
    }


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status,
            content=_body(exc.status, exc.code, exc.message, request.url.path),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(exc.status_code, code, str(exc.detail), request.url.path),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'][1:]) or 'corpo'}: {e['msg']}"
            for e in exc.errors()
        )
        return JSONResponse(
            status_code=400,
            content=_body(400, "VALIDATION_ERROR", f"Requisição inválida ({details}).", request.url.path),
        )

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_error(request: Request, exc: sqlite3.IntegrityError):
        log.warning("Conflito de integridade em %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=409,
            content=_body(409, "DATA_CONFLICT",
                          "Esses dados entram em conflito com algo que já existe ou que está em uso.",
                          request.url.path),
        )

    @app.exception_handler(sqlite3.OperationalError)
    async def database_busy(request: Request, exc: sqlite3.OperationalError):
        log.error("Erro de banco em %s %s: %s", request.method, request.url.path, exc)
        if "locked" in str(exc).lower() or "busy" in str(exc).lower():
            return JSONResponse(
                status_code=503,
                content=_body(503, "DATABASE_BUSY", "O banco está ocupado. Tente de novo em instantes.", request.url.path),
            )
        return JSONResponse(
            status_code=500,
            content=_body(500, "INTERNAL_ERROR", "Erro inesperado.", request.url.path),
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        # Antes o erro sumia; agora o traceback completo vai para o terminal e para backend/data/rafalink.log.
        log.error("Erro inesperado em %s %s", request.method, request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=_body(500, "INTERNAL_ERROR", "Erro inesperado.", request.url.path),
        )