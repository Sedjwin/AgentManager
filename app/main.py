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


_LOCAL_TOOLS = [
    {
        "name": "update-personal-context",
        "description": "Agent writes to its own PersonalContext.md (persistent memory across sessions).",
        "capabilities": ["filesystem_writes"],
    },
    {
        "name": "read-personal-context",
        "description": "Agent re-reads its own PersonalContext.md.",
        "capabilities": ["filesystem_reads"],
    },
    {
        "name": "read-history",
        "description": "Agent reads its own history event log (session starts/ends, tool calls).",
        "capabilities": ["filesystem_reads"],
    },
    {
        "name": "list-sessions",
        "description": "Agent lists its own past sessions with metadata.",
        "capabilities": ["filesystem_reads"],
    },
    {
        "name": "read-session",
        "description": "Agent reads the full conversation log of a specific past session.",
        "capabilities": ["filesystem_reads"],
    },
    {
        "name": "ask-agent",
        "description": "Agent sends a message to another agent and receives a response.",
        "capabilities": ["network_access"],
    },
]


async def _register_local_tools_in_tg() -> None:
    """Register built-in memory tools in ToolGateway if not already present."""
    key = settings.toolgateway_service_key
    if not key:
        return
    import logging
    logger = logging.getLogger(__name__)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{settings.toolgateway_url}/api/tools", headers=headers)
            if r.status_code != 200:
                logger.warning("ToolGateway /api/tools returned %d — skipping local tool registration", r.status_code)
                return
            existing_names = {t["name"] for t in r.json()}
            for tool_def in _LOCAL_TOOLS:
                if tool_def["name"] in existing_names:
                    continue
                payload = {
                    "name": tool_def["name"],
                    "description": tool_def["description"],
                    "category": "builtin",
                    "kind": "local",
                    "state": "active",
                    "enabled": True,
                    "capabilities": tool_def["capabilities"],
                }
                cr = await client.post(
                    f"{settings.toolgateway_url}/api/tools",
                    json=payload,
                    headers=headers,
                )
                if cr.status_code == 201:
                    logger.info("Registered local tool in ToolGateway: %s", tool_def["name"])
                else:
                    logger.warning("Failed to register %s in TG: %d", tool_def["name"], cr.status_code)
    except Exception as exc:
        logger.warning("Could not register local tools in ToolGateway: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await migrate_db()
    await seed_glados()
    await seed_tars()
    await backfill_um_principals()
    await _backfill_agent_data_dirs()
    await _register_local_tools_in_tg()
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
