"""Session management and interaction endpoints."""
from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Agent
from app.schemas import (
    AgentResponse, DeviceCapabilities, InterruptRequest,
    SessionOut, TextMessage,
)
from app.services.pipeline.orchestrator import (
    process_audio, process_text, process_text_streaming,
)
from app.services.session_manager import session_manager

router = APIRouter(tags=["sessions"])


# ── Session lifecycle ────────────────────────────────────────────────────────

@router.post("/agents/{agent_id}/session", response_model=SessionOut)
async def start_session(
    agent_id: str,
    request: Request,
    body: DeviceCapabilities | None = None,
    db: AsyncSession = Depends(get_db),
):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    caps = body.model_dump() if body else {}
    user_id  = request.headers.get("X-User-Id")
    username = request.headers.get("X-Username")
    session = session_manager.create(agent_id, caps, user_id=user_id, username=username)

    profile = json.loads(agent.profile) if agent.profile else None
    return SessionOut(
        session_id=session.session_id,
        agent_id=agent_id,
        type="interaction" if profile else "functional",
        profile=profile,
    )


@router.delete("/sessions/{session_id}", status_code=204)
async def end_session(session_id: str):
    session_manager.delete(session_id)


# ── Interaction ──────────────────────────────────────────────────────────────

async def _load_session_and_agent(session_id: str, db: AsyncSession):
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    agent = await db.get(Agent, session.agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return session, agent


@router.post("/sessions/{session_id}/message", response_model=AgentResponse)
async def send_message(
    session_id: str,
    body: TextMessage,
    db: AsyncSession = Depends(get_db),
):
    session, agent = await _load_session_and_agent(session_id, db)
    profile = json.loads(agent.profile) if agent.profile else None
    voice_config = json.loads(agent.voice_config) if agent.voice_config else None

    try:
        return await process_text(
            session=session,
            user_text=body.text,
            agent_system_prompt=agent.system_prompt,
            profile=profile,
            voice_enabled=agent.voice_enabled,
            voice_config=voice_config,
            ai_gateway_token=agent.ai_gateway_token,
            um_api_key=agent.um_api_key,
        )
    except InterruptedError:
        raise HTTPException(409, "Request interrupted")


@router.post("/sessions/{session_id}/audio", response_model=AgentResponse)
async def send_audio(
    session_id: str,
    audio: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    session, agent = await _load_session_and_agent(session_id, db)
    profile = json.loads(agent.profile) if agent.profile else None
    voice_config = json.loads(agent.voice_config) if agent.voice_config else None

    audio_bytes = await audio.read()
    try:
        return await process_audio(
            session=session,
            audio_bytes=audio_bytes,
            agent_system_prompt=agent.system_prompt,
            profile=profile,
            voice_enabled=agent.voice_enabled,
            voice_config=voice_config,
            ai_gateway_token=agent.ai_gateway_token,
            um_api_key=agent.um_api_key,
        )
    except InterruptedError:
        raise HTTPException(409, "Request interrupted")


@router.post("/sessions/{session_id}/interrupt", status_code=204)
async def interrupt_session(session_id: str):
    session = session_manager.get(session_id)
    if session:
        session.interrupt()


@router.get("/sessions/{session_id}/stream")
async def stream_response_get(
    session_id: str,
    text: str,
    db: AsyncSession = Depends(get_db),
):
    """SSE endpoint (GET) — streams response chunks."""
    return await _do_stream(session_id, text, db)


@router.post("/sessions/{session_id}/stream")
async def stream_response_post(
    session_id: str,
    body: TextMessage,
    db: AsyncSession = Depends(get_db),
):
    """SSE endpoint (POST) — streams response chunks."""
    return await _do_stream(session_id, body.text, db)


async def _do_stream(session_id: str, text: str, db: AsyncSession) -> StreamingResponse:
    session, agent = await _load_session_and_agent(session_id, db)
    profile = json.loads(agent.profile) if agent.profile else None
    voice_config = json.loads(agent.voice_config) if agent.voice_config else None

    async def event_generator() -> AsyncIterator[str]:
        async for chunk in process_text_streaming(
            session=session,
            user_text=text,
            agent_system_prompt=agent.system_prompt,
            profile=profile,
            voice_enabled=agent.voice_enabled,
            voice_config=voice_config,
            ai_gateway_token=agent.ai_gateway_token,
            um_api_key=agent.um_api_key,
        ):
            yield f"data: {chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
