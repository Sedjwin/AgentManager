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
    AgentResponse, DeviceCapabilities, HistoryLoad, InterruptRequest,
    SessionOut, TextMessage,
)
from app.services.pipeline.orchestrator import (
    process_audio, process_text, process_text_debug, process_text_streaming,
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


@router.post("/sessions/{session_id}/history", status_code=204)
async def load_history(session_id: str, body: HistoryLoad):
    """
    Pre-populate an existing session's in-memory history.
    Called by ChatPortal when resuming a stored conversation so the agent
    has context from previous exchanges without those turns being live-streamed.
    Replaces any existing history in the session.
    """
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    session.history = [{"role": m.role, "content": m.content} for m in body.messages]


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
    tool_skill_mds = _get_tool_skill_mds(agent)

    try:
        return await process_text(
            session=session,
            user_text=body.text,
            agent_system_prompt=agent.system_prompt,
            profile=profile,
            voice_enabled=agent.voice_enabled,
            voice_config=voice_config,
            ai_gateway_token=agent.ai_gateway_token,
            agent_id=agent.agent_id,
            um_api_key=agent.um_api_key,
            tool_use_enabled=agent.tool_use_enabled,
            tool_skill_mds=tool_skill_mds,
            memory_tools_enabled=bool(agent.memory_tools_enabled),
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
    tool_skill_mds = _get_tool_skill_mds(agent)

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
            agent_id=agent.agent_id,
            um_api_key=agent.um_api_key,
            tool_use_enabled=agent.tool_use_enabled,
            tool_skill_mds=tool_skill_mds,
            memory_tools_enabled=bool(agent.memory_tools_enabled),
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


@router.post("/sessions/{session_id}/debug")
async def debug_message(
    session_id: str,
    body: TextMessage,
    db: AsyncSession = Depends(get_db),
):
    """SSE endpoint — streams real pipeline events as they execute.
    Each event is a JSON object: {event, ts, ...fields}.
    Ends with 'data: [DONE]'.
    """
    session, agent = await _load_session_and_agent(session_id, db)
    profile      = json.loads(agent.profile)      if agent.profile      else None
    voice_config = json.loads(agent.voice_config) if agent.voice_config else None
    tool_skill_mds = _get_tool_skill_mds(agent)

    async def event_gen() -> AsyncIterator[str]:
        try:
            async for event in process_text_debug(
                session=session,
                user_text=body.text,
                agent_system_prompt=agent.system_prompt,
                profile=profile,
                voice_enabled=agent.voice_enabled,
                voice_config=voice_config,
                ai_gateway_token=agent.ai_gateway_token,
                agent_id=agent.agent_id,
                um_api_key=agent.um_api_key,
                tool_use_enabled=agent.tool_use_enabled,
                tool_skill_mds=tool_skill_mds,
                memory_tools_enabled=bool(agent.memory_tools_enabled),
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except InterruptedError:
            yield f"data: {json.dumps({'event': 'interrupted', 'ts': -1})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'event': 'error', 'ts': -1, 'message': str(exc)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


def _get_tool_skill_mds(agent) -> list[str]:
    """Extract ordered list of skill_md strings from the agent's enabled_tools JSON."""
    try:
        tools_data = json.loads(agent.enabled_tools or "[]")
        return [t["skill_md"] for t in tools_data if t.get("skill_md")]
    except Exception:
        return []


async def _do_stream(session_id: str, text: str, db: AsyncSession) -> StreamingResponse:
    session, agent = await _load_session_and_agent(session_id, db)
    profile = json.loads(agent.profile) if agent.profile else None
    voice_config = json.loads(agent.voice_config) if agent.voice_config else None
    tool_skill_mds = _get_tool_skill_mds(agent)

    async def event_generator() -> AsyncIterator[str]:
        async for chunk in process_text_streaming(
            session=session,
            user_text=text,
            agent_system_prompt=agent.system_prompt,
            profile=profile,
            voice_enabled=agent.voice_enabled,
            voice_config=voice_config,
            ai_gateway_token=agent.ai_gateway_token,
            agent_id=agent.agent_id,
            um_api_key=agent.um_api_key,
            tool_use_enabled=agent.tool_use_enabled,
            tool_skill_mds=tool_skill_mds,
            memory_tools_enabled=bool(agent.memory_tools_enabled),
        ):
            yield f"data: {chunk.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
