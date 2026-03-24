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
from app.services.agent_memory import (
    append_history_event,
    read_personal_context,
    read_task_list,
)
from app.services.pipeline.local_tool_executor import execute_local_tool, is_local_tool
from app.services.pipeline.prompt_builder import build_messages
from app.services.pipeline.response_parser import parse_response
from app.services.pipeline.timeline_assembler import assemble_timeline
from app.services.pipeline.tool_executor import execute_tool_calls, format_tool_results_for_llm
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
    agent_id: str | None = None,
    um_api_key: str | None = None,
    tool_use_enabled: bool = False,
    tool_skill_mds: list[str] | None = None,
) -> AgentResponse:
    """Full pipeline for a text message. Returns a single assembled response."""
    session.clear_interrupt()

    # Log user input immediately so even interrupted turns are recorded
    turn = session.logger.next_turn()
    session.logger.log_user_text(turn, user_text)

    # Step 2: Build LLM messages (inject PersonalContext + TaskList)
    _agent_id = agent_id or session.agent_id
    personal_context = read_personal_context(_agent_id)
    task_list = read_task_list(_agent_id)
    messages = build_messages(
        agent_system_prompt, profile, session.history, user_text,
        tool_use_enabled=tool_use_enabled, tool_skill_mds=tool_skill_mds,
        personal_context=personal_context, task_list=task_list,
    )

    # Step 2b: Call AIGateway
    raw_llm, reasoning = await _call_llm(messages, ai_gateway_token)

    if session.interrupted:
        raise InterruptedError

    # Step 2c: Execute any tool calls and re-prompt with results
    raw_llm = await _resolve_tool_calls(raw_llm, messages, ai_gateway_token, um_api_key, session.session_id, _agent_id)

    if session.interrupted:
        raise InterruptedError

    # Step 3: Parse annotations
    clean_text, annotations, _ = parse_response(raw_llm, profile)

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
        total = max(len(clean_text), 1)
        for ann in annotations:
            t = int((ann.char / total) * 5000)
            timeline.append(TimelineEvent(t=t, type=ann.type, value=ann.value))

    # Update session history
    session.add_turn(user_text, clean_text)

    # Log assistant response
    session.logger.log_assistant(
        turn=turn,
        text=clean_text,
        raw_llm=raw_llm,
        audio_b64=audio_b64,
        duration_ms=duration_ms,
        timeline=[e.model_dump() for e in timeline],
    )

    return AgentResponse(
        session_id=session.session_id,
        text=clean_text,
        reasoning=reasoning,
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
    agent_id: str | None = None,
    um_api_key: str | None = None,
    tool_use_enabled: bool = False,
    tool_skill_mds: list[str] | None = None,
) -> AgentResponse:
    """Full pipeline for audio input — runs STT first, then same as process_text."""
    session.clear_interrupt()

    # Transcribe first so we have the text for logging
    transcript = await transcribe(audio_bytes)

    turn = session.logger.next_turn()
    session.logger.log_user_audio(turn, transcript, audio_bytes)

    _agent_id = agent_id or session.agent_id
    personal_context = read_personal_context(_agent_id)
    task_list = read_task_list(_agent_id)
    messages = build_messages(
        agent_system_prompt, profile, session.history, transcript,
        tool_use_enabled=tool_use_enabled, tool_skill_mds=tool_skill_mds,
        personal_context=personal_context, task_list=task_list,
    )
    raw_llm, reasoning = await _call_llm(messages, ai_gateway_token)

    if session.interrupted:
        raise InterruptedError

    raw_llm = await _resolve_tool_calls(raw_llm, messages, ai_gateway_token, um_api_key, session.session_id, _agent_id)

    if session.interrupted:
        raise InterruptedError

    clean_text, annotations, _ = parse_response(raw_llm, profile)

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
        total = max(len(clean_text), 1)
        for ann in annotations:
            t = int((ann.char / total) * 5000)
            timeline.append(TimelineEvent(t=t, type=ann.type, value=ann.value))

    session.add_turn(transcript, clean_text)

    session.logger.log_assistant(
        turn=turn,
        text=clean_text,
        raw_llm=raw_llm,
        audio_b64=audio_b64,
        duration_ms=duration_ms,
        timeline=[e.model_dump() for e in timeline],
    )

    return AgentResponse(
        session_id=session.session_id,
        text=clean_text,
        reasoning=reasoning,
        transcript=transcript,
        audio=audio_b64,
        duration_ms=duration_ms,
        sample_rate=sample_rate,
        buffer_bytes=buffer_bytes,
        timeline=timeline,
        is_final=True,
    )


async def process_text_streaming(
    session: Session,
    user_text: str,
    agent_system_prompt: str,
    profile: dict[str, Any] | None,
    voice_enabled: bool,
    voice_config: dict[str, Any] | None,
    ai_gateway_token: str,
    agent_id: str | None = None,
    um_api_key: str | None = None,
    tool_use_enabled: bool = False,
    tool_skill_mds: list[str] | None = None,
) -> AsyncIterator[AgentResponse]:
    """
    Streaming pipeline: splits LLM output at sentence boundaries,
    synthesizes each chunk, yields AgentResponse per chunk.
    """
    session.clear_interrupt()

    turn = session.logger.next_turn()
    session.logger.log_user_text(turn, user_text)

    _agent_id = agent_id or session.agent_id
    personal_context = read_personal_context(_agent_id)
    task_list = read_task_list(_agent_id)
    messages = build_messages(
        agent_system_prompt, profile, session.history, user_text,
        tool_use_enabled=tool_use_enabled, tool_skill_mds=tool_skill_mds,
        personal_context=personal_context, task_list=task_list,
    )
    raw_llm, reasoning = await _call_llm(messages, ai_gateway_token)

    if session.interrupted:
        return

    raw_llm = await _resolve_tool_calls(raw_llm, messages, ai_gateway_token, um_api_key, session.session_id, _agent_id)

    if session.interrupted:
        return

    clean_text, annotations, _ = parse_response(raw_llm, profile)
    sentences = _split_sentences(clean_text)

    char_offset = 0
    full_clean = ""

    for i, sentence in enumerate(sentences):
        if session.interrupted:
            break

        is_final = i == len(sentences) - 1
        sentence_end = char_offset + len(sentence)

        sentence_annotations = [
            a for a in annotations
            if char_offset <= a.char < sentence_end
        ]
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

        # Log each chunk; only include raw_llm on first chunk
        session.logger.log_assistant(
            turn=turn,
            text=sentence,
            raw_llm=raw_llm if i == 0 else None,
            audio_b64=audio_b64,
            duration_ms=duration_ms,
            timeline=[e.model_dump() for e in timeline],
            chunk_index=i,
            is_final=is_final,
        )

        yield AgentResponse(
            session_id=session.session_id,
            text=sentence,
            # Attach reasoning only to the first chunk so the client receives it once
            reasoning=reasoning if i == 0 else None,
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

async def _call_llm(messages: list[dict[str, str]], token: str) -> tuple[str, str | None]:
    """Call AIGateway. Returns (content, reasoning) — reasoning may be None."""
    payload = {"messages": messages, "stream": False}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.aigateway_url}/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        data = resp.json()
        msg = data["choices"][0]["message"]
        content = msg.get("content") or ""
        # OpenRouter returns reasoning in "reasoning" (some models use "reasoning_content")
        reasoning = msg.get("reasoning") or msg.get("reasoning_content") or None
        return content, reasoning


async def _resolve_tool_calls(
    raw_llm: str,
    messages: list[dict],
    ai_gateway_token: str,
    um_api_key: str | None,
    session_id: str | None,
    agent_id: str | None = None,
) -> str:
    """
    Execute any {tool:name} tags in the LLM response, then re-prompt with results.
    Local memory tools are executed directly; gateway tools route through ToolGateway.
    Returns the final LLM response (with no tool tags).
    """
    _, _, tool_calls = parse_response(raw_llm)
    if not tool_calls:
        return raw_llm

    local_calls = [c for c in tool_calls if is_local_tool(c.name)]
    gateway_calls = [c for c in tool_calls if not is_local_tool(c.name)]

    results = []

    # Execute local memory tools (no API key required)
    for call in local_calls:
        result = execute_local_tool(call, agent_id or "", session_id)
        results.append(result)

    # Execute gateway tools via ToolGateway
    if gateway_calls:
        if um_api_key:
            gateway_results = await execute_tool_calls(gateway_calls, um_api_key, session_id)
            # Write history events for gateway tool calls
            if agent_id:
                for r in gateway_results:
                    append_history_event(
                        agent_id, "tool_call",
                        session_id=session_id,
                        tool=r.get("tool", "unknown"),
                        status=r.get("status", "unknown"),
                    )
            results.extend(gateway_results)
        else:
            for call in gateway_calls:
                results.append({
                    "tool": call.name,
                    "status": "error",
                    "reason": "No ToolGateway API key configured for this agent",
                })

    if not results:
        return raw_llm

    tool_msg = format_tool_results_for_llm(results)

    # Re-prompt: append the first response and the tool results, get final answer
    second_pass = messages + [
        {"role": "assistant", "content": raw_llm},
        {"role": "user", "content": tool_msg},
    ]
    content, _ = await _call_llm(second_pass, ai_gateway_token)
    return content


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
