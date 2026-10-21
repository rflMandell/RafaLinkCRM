from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import run_migrations
from .errors import register_error_handlers
from .routers import auth, leads
from .seed import seed

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    seed()
    yield


app = FastAPI(title="RafaLink CRM API", version="0.1.0", lifespan=lifespan)

# Permite abrir o front por outra porta (ex.: Live Server do VS Code na 5500).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

api_v1 = APIRouter(prefix="/api/v1")


@api_v1.get("/health", tags=["Health"])
def health():
    return {"status": "UP", "service": "rafalink-api", "version": app.version}


api_v1.include_router(auth.router)
api_v1.include_router(leads.router)
app.include_router(api_v1)

# O backend também serve o frontend: tudo em http://localhost:8000
# (precisa ficar DEPOIS das rotas da API)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")