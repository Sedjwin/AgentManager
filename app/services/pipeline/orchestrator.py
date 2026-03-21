"""
MessagePipeline — orchestrates the full Steps 1-6 from the spec:
  Input → (STT) → LLM → Parse → (TTS) → Timeline → Payload
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from app.config import settings
from app.schemas import AgentResponse, TimelineEvent
from app.services.pipeline.prompt_builder import build_messages
from app.services.pipeline.response_parser import parse_response
from app.services.pipeline.timeline_assembler import assemble_timeline
from app.services.pipeline.voice_processor import synthesize, transcribe
from app.services.session_manager import Session


async def process_text(
    session: Session,
    user_text: str,
    agent_system_prompt: str,
    profile: dict[str, Any] | None,
    voice_enabled: bool,
    voice_config: dict[str, Any] | None,
    ai_gateway_token: str,
) -> AgentResponse:
    """Full pipeline for a text message. Returns a single assembled response."""
    session.clear_interrupt()

    # Step 2: Build LLM messages
    messages = build_messages(agent_system_prompt, profile, session.history, user_text)

    # Step 2b: Call AIGateway
    raw_llm = await _call_llm(messages, ai_gateway_token)

    if session.interrupted:
        raise InterruptedError

    # Step 3: Parse annotations
    clean_text, annotations = parse_response(raw_llm)

    # Step 4 & 5: TTS + Timeline (only if voice enabled)
    audio_b64 = None
    duration_ms = None
    sample_rate = None
    buffer_bytes = None
    timeline: list[TimelineEvent] = []

    if voice_enabled:
        tts = await synthesize(clean_text, voice_config)
        if session.interrupted:
            raise InterruptedError
        audio_b64 = tts.get("audio")
        duration_ms = tts.get("duration_ms")
        sample_rate = tts.get("sample_rate")
        buffer_bytes = tts.get("buffer_bytes")
        timeline = assemble_timeline(annotations, clean_text, tts)
    else:
        # No TTS — still emit emotion/action events at proportional positions
        # but with no audio timestamps, just use char-proportional ms (dummy)
        total = max(len(clean_text), 1)
        for ann in annotations:
            t = int((ann.char / total) * 5000)  # map to 0-5s range
            timeline.append(TimelineEvent(t=t, type=ann.type, value=ann.value))

    # Update session history
    session.add_turn(user_text, clean_text)

    return AgentResponse(
        session_id=session.session_id,
        text=clean_text,
        audio=audio_b64,
        duration_ms=duration_ms,
        sample_rate=sample_rate,
        buffer_bytes=buffer_bytes,
        timeline=timeline,
        is_final=True,
    )


async def process_audio(
    session: Session,
    audio_bytes: bytes,
    agent_system_prompt: str,
    profile: dict[str, Any] | None,
    voice_enabled: bool,
    voice_config: dict[str, Any] | None,
    ai_gateway_token: str,
) -> AgentResponse:
    """Full pipeline for audio input — runs STT first, then same as process_text."""
    transcript = await transcribe(audio_bytes)
    response = await process_text(
        session, transcript, agent_system_prompt, profile,
        voice_enabled, voice_config, ai_gateway_token,
    )
    response.transcript = transcript
    return response


async def process_text_streaming(
    session: Session,
    user_text: str,
    agent_system_prompt: str,
    profile: dict[str, Any] | None,
    voice_enabled: bool,
    voice_config: dict[str, Any] | None,
    ai_gateway_token: str,
) -> AsyncIterator[AgentResponse]:
    """
    Streaming pipeline: splits LLM output at sentence boundaries,
    synthesizes each chunk, yields AgentResponse per chunk.
    """
    session.clear_interrupt()
    messages = build_messages(agent_system_prompt, profile, session.history, user_text)
    raw_llm = await _call_llm(messages, ai_gateway_token)

    if session.interrupted:
        return

    clean_text, annotations = parse_response(raw_llm)
    sentences = _split_sentences(clean_text)

    char_offset = 0
    full_clean = ""

    for i, sentence in enumerate(sentences):
        if session.interrupted:
            break

        is_final = i == len(sentences) - 1
        sentence_end = char_offset + len(sentence)

        # Find annotations in this sentence's char range
        sentence_annotations = [
            a for a in annotations
            if char_offset <= a.char < sentence_end
        ]
        # Re-base char positions to be relative to this sentence
        for ann in sentence_annotations:
            ann.char -= char_offset

        audio_b64 = None
        duration_ms = None
        sample_rate = None
        buffer_bytes = None
        timeline: list[TimelineEvent] = []

        if voice_enabled and sentence.strip():
            tts = await synthesize(sentence, voice_config)
            if session.interrupted:
                break
            audio_b64 = tts.get("audio")
            duration_ms = tts.get("duration_ms")
            sample_rate = tts.get("sample_rate")
            buffer_bytes = tts.get("buffer_bytes")
            timeline = assemble_timeline(sentence_annotations, sentence, tts)

        full_clean += sentence
        char_offset = sentence_end

        yield AgentResponse(
            session_id=session.session_id,
            text=sentence,
            audio=audio_b64,
            duration_ms=duration_ms,
            sample_rate=sample_rate,
            buffer_bytes=buffer_bytes,
            timeline=timeline,
            chunk_index=i,
            is_final=is_final,
        )

    session.add_turn(user_text, full_clean)


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _call_llm(messages: list[dict[str, str]], token: str) -> str:
    payload = {"messages": messages, "stream": False}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.aigateway_url}/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def _split_sentences(text: str) -> list[str]:
    """Split text at sentence boundaries, preserving trailing spaces."""
    import re
    parts = re.split(r"(?<=[.!?])\s+", text)
    sentences = []
    for i, part in enumerate(parts):
        if i < len(parts) - 1:
            sentences.append(part + " ")
        else:
            sentences.append(part)
    return [s for s in sentences if s.strip()]
