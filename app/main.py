"""AgentManager — agent lifecycle, orchestration, and personality management."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import init_db
from .routers import agents, chat, generate

_DIST = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="AgentManager",
    description="Create, configure, and orchestrate AI agents",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router)
app.include_router(chat.router)
app.include_router(generate.router)


@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok", "service": "AgentManager"}


# ── Serve React frontend ──────────────────────────────────────────────────────

if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str = ""):
        # API routes are matched first (above), so anything reaching here is a SPA route
        index = _DIST / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"service": "AgentManager", "note": "Frontend not built"}
