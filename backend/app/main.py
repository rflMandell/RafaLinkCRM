from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import run_migrations
from .errors import register_error_handlers
from .routers import (
    activities, auth, campaigns, companies, contacts, customers, forecast, goals, leads,
    opportunities, pipelines, reports, sla, ai, automations, audit, notifications, settings, search, importer, dedupe
)
from .seed import seed
from .worker import start_worker


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
api_v1.include_router(companies.router)
api_v1.include_router(contacts.router)
api_v1.include_router(pipelines.router)
api_v1.include_router(opportunities.router)
api_v1.include_router(activities.router)
api_v1.include_router(activities.agenda_router)
api_v1.include_router(activities.tasks_router)
api_v1.include_router(customers.router)
api_v1.include_router(campaigns.router)
api_v1.include_router(reports.router)
api_v1.include_router(forecast.router)
api_v1.include_router(goals.router)
api_v1.include_router(sla.router)
api_v1.include_router(ai.router)
api_v1.include_router(notifications.router)
api_v1.include_router(automations.router)
api_v1.include_router(audit.router)
api_v1.include_router(settings.router)
api_v1.include_router(search.router)
api_v1.include_router(importer.router)
api_v1.include_router(dedupe.router)
app.include_router(api_v1)

# O backend também serve o frontend: tudo em http://localhost:8000
# (precisa ficar DEPOIS das rotas da API)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

# toda a audt em segundo plano
start_worker()