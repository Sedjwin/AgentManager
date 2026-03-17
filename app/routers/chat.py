"""Chat endpoint: multipart text + optional audio → full orchestrated response."""

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Agent
from app.services.orchestrator import orchestrate

router = APIRouter(prefix="/agents", tags=["Chat"])


@router.post("/{agent_id}/chat")
async def chat(
    agent_id: int,
    text: str | None = Form(None),
    audio: UploadFile | None = File(None),
    history: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Multipart chat endpoint.

    - text: optional text input
    - audio: optional WAV file for STT
    - history: optional JSON array of {role, content} message objects
    """
    # Load agent
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    if not agent.enabled:
        raise HTTPException(status_code=403, detail="Agent is disabled")
    if not agent.gateway_token:
        raise HTTPException(status_code=422, detail="Agent has no gateway_token configured")

    # Parse optional history
    parsed_history: list | None = None
    if history:
        try:
            parsed_history = json.loads(history)
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="history must be valid JSON")

    # Read audio bytes if provided
    audio_bytes: bytes | None = None
    if audio is not None:
        audio_bytes = await audio.read()

    if not text and not audio_bytes:
        raise HTTPException(status_code=422, detail="Provide at least text or audio")

    result_dict = await orchestrate(
        agent=agent,
        text_input=text,
        audio_bytes=audio_bytes,
        history=parsed_history,
    )

    return result_dict
