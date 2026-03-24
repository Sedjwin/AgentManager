import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db, migrate_db
from app.routers import agents, sessions
from app.seed import seed_glados, seed_tars, backfill_um_principals
from app.services.agent_memory import ensure_agent_data_dir

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")


async def _backfill_agent_data_dirs() -> None:
    """Ensure every existing agent has its data directory scaffolded."""
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models import Agent
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Agent.agent_id))
        for (agent_id,) in result.all():
            ensure_agent_data_dir(agent_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await migrate_db()
    await seed_glados()
    await seed_tars()
    await backfill_um_principals()
    await _backfill_agent_data_dirs()
    yield


app = FastAPI(title="AgentManager", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router)
app.include_router(sessions.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "AgentManager"}


@app.get("/voices")
async def list_voices():
    """Proxy VoiceService /voices so the frontend always reflects what's actually available."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{settings.voiceservice_url}/voices", timeout=5.0)
        r.raise_for_status()
    return r.json()


# Serve admin UI at / — must come after API routes
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="ui")
