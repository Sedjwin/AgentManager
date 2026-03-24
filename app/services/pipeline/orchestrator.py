"""
MessagePipeline — orchestrates the full Steps 1-6 from the spec:
  Input → (STT) → LLM → Parse → (TTS) → Timeline → Payload
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncIterator

import httpx

logger = logging.getLogger(__name__)

from app.config import settings
from app.schemas import AgentResponse, TimelineEvent
from app.services.agent_memory import (
    append_history_event,
    read_personal_context,
    read_task_list,
)
from app.services.pipeline.local_tool_executor import execute_local_tool_async, is_local_tool
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
    memory_tools_enabled: bool = True,
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
        memory_tools_enabled=memory_tools_enabled,
        current_session_id=session.session_id,
    )

    # Step 2b: Call AIGateway
    raw_llm, reasoning = await _call_llm(messages, ai_gateway_token)

    if session.interrupted:
        raise InterruptedError

    # Step 2c: Execute any tool calls and re-prompt with results
    raw_llm = await _resolve_tool_calls(
        raw_llm, messages, ai_gateway_token, um_api_key, session.session_id, _agent_id,
        memory_tools_enabled=memory_tools_enabled,
    )

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
    memory_tools_enabled: bool = True,
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
        memory_tools_enabled=memory_tools_enabled,
        current_session_id=session.session_id,
    )
    raw_llm, reasoning = await _call_llm(messages, ai_gateway_token)

    if session.interrupted:
        raise InterruptedError

    raw_llm = await _resolve_tool_calls(
        raw_llm, messages, ai_gateway_token, um_api_key, session.session_id, _agent_id,
        memory_tools_enabled=memory_tools_enabled,
    )

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
    memory_tools_enabled: bool = True,
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
        memory_tools_enabled=memory_tools_enabled,
        current_session_id=session.session_id,
    )
    raw_llm, reasoning = await _call_llm(messages, ai_gateway_token)

    if session.interrupted:
        return

    raw_llm = await _resolve_tool_calls(
        raw_llm, messages, ai_gateway_token, um_api_key, session.session_id, _agent_id,
        memory_tools_enabled=memory_tools_enabled,
    )

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
    async with httpx.AsyncClient(timeout=120.0) as client:
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


_MAX_TOOL_ROUNDS = 5


async def _resolve_tool_calls(
    raw_llm: str,
    messages: list[dict],
    ai_gateway_token: str,
    um_api_key: str | None,
    session_id: str | None,
    agent_id: str | None = None,
    memory_tools_enabled: bool = True,
) -> str:
    """
    Agentic tool loop: execute any {tool:name} tags in the LLM response, re-prompt
    with results, and repeat until the response contains no tool tags or _MAX_TOOL_ROUNDS
    is reached. Local memory tools execute directly; gateway tools route through ToolGateway.
    Returns the final LLM response (with no tool tags).
    """
    current = raw_llm
    conversation = list(messages)

    for round_num in range(_MAX_TOOL_ROUNDS):
        _, _, tool_calls = parse_response(current)
        if not tool_calls:
            return current  # clean response — done

        local_calls = [c for c in tool_calls if is_local_tool(c.name)] if memory_tools_enabled else []
        gateway_calls = [c for c in tool_calls if not is_local_tool(c.name)]

        results = []

        for call in local_calls:
            result = await execute_local_tool_async(call, agent_id or "", session_id)
            results.append(result)

        if gateway_calls:
            if um_api_key:
                gateway_results = await execute_tool_calls(gateway_calls, um_api_key, session_id)
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
            return current

        tool_msg = format_tool_results_for_llm(results)
        logger.debug("Tool round %d/%d: executed %d tool(s)", round_num + 1, _MAX_TOOL_ROUNDS, len(results))

        conversation = conversation + [
            {"role": "assistant", "content": current},
            {"role": "user", "content": tool_msg},
        ]
        current, _ = await _call_llm(conversation, ai_gateway_token)

    logger.warning("Tool resolution reached max rounds (%d) — returning last response", _MAX_TOOL_ROUNDS)
    return current


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


async def process_text_debug(
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
    memory_tools_enabled: bool = True,
) -> AsyncIterator[dict]:
    """
    Async generator that runs the full pipeline and yields a debug event dict
    at every meaningful step (LLM call, tool call, tool result, TTS, done).
    Timestamps are milliseconds from the start of this call.
    Audio is excluded from events to keep payloads small — use the normal
    /message endpoint if audio playback is needed.
    """
    t0 = time.monotonic()
    def ms() -> int:
        return int((time.monotonic() - t0) * 1000)

    session.clear_interrupt()
    turn = session.logger.next_turn()
    session.logger.log_user_text(turn, user_text)

    yield {"event": "start", "ts": 0, "user_text": user_text}

    _agent_id = agent_id or session.agent_id
    personal_context = read_personal_context(_agent_id)
    task_list = read_task_list(_agent_id)
    messages = build_messages(
        agent_system_prompt, profile, session.history, user_text,
        tool_use_enabled=tool_use_enabled, tool_skill_mds=tool_skill_mds,
        personal_context=personal_context, task_list=task_list,
        memory_tools_enabled=memory_tools_enabled,
        current_session_id=session.session_id,
    )

    # ── Round 0: initial LLM call ────────────────────────────────────────────
    yield {"event": "llm_start", "ts": ms(), "round": 0, "message_count": len(messages)}
    try:
        t_llm = time.monotonic()
        raw_llm, reasoning = await _call_llm(messages, ai_gateway_token)
        llm_elapsed = int((time.monotonic() - t_llm) * 1000)
    except Exception as exc:
        yield {"event": "error", "ts": ms(), "message": str(exc)}
        return

    _, _, tc = parse_response(raw_llm)
    yield {
        "event": "llm_done", "ts": ms(), "round": 0,
        "elapsed_ms": llm_elapsed, "raw_llm": raw_llm,
        "reasoning": reasoning, "has_tool_calls": bool(tc),
    }

    if session.interrupted:
        yield {"event": "interrupted", "ts": ms()}
        return

    # ── Agentic tool loop ────────────────────────────────────────────────────
    current = raw_llm
    conversation = list(messages)

    for round_num in range(_MAX_TOOL_ROUNDS):
        _, _, tool_calls = parse_response(current)
        if not tool_calls:
            break

        local_calls   = [c for c in tool_calls if is_local_tool(c.name)] if memory_tools_enabled else []
        gateway_calls = [c for c in tool_calls if not is_local_tool(c.name)]
        results: list[dict] = []

        for call in local_calls:
            yield {"event": "tool_call", "ts": ms(), "round": round_num + 1,
                   "tool": call.name, "params": call.params, "kind": "local"}
            t_tool = time.monotonic()
            result = await execute_local_tool_async(call, _agent_id or "", session.session_id)
            tool_elapsed = int((time.monotonic() - t_tool) * 1000)
            yield {"event": "tool_result", "ts": ms(), "round": round_num + 1,
                   "tool": call.name, "status": result.get("status"),
                   "data": result.get("data"), "reason": result.get("reason"),
                   "elapsed_ms": tool_elapsed}
            results.append(result)

        if gateway_calls:
            if um_api_key:
                for call in gateway_calls:
                    yield {"event": "tool_call", "ts": ms(), "round": round_num + 1,
                           "tool": call.name, "params": call.params, "kind": "gateway"}
                t_tool = time.monotonic()
                gw_results = await execute_tool_calls(gateway_calls, um_api_key, session.session_id)
                tool_elapsed = int((time.monotonic() - t_tool) * 1000)
                per_tool_ms = tool_elapsed // max(len(gw_results), 1)
                for i, r in enumerate(gw_results):
                    if _agent_id:
                        append_history_event(
                            _agent_id, "tool_call", session_id=session.session_id,
                            tool=r.get("tool", "unknown"), status=r.get("status", "unknown"),
                        )
                    yield {"event": "tool_result", "ts": ms(), "round": round_num + 1,
                           "tool": gateway_calls[i].name, "status": r.get("status"),
                           "data": r.get("data"), "reason": r.get("reason"),
                           "elapsed_ms": per_tool_ms}
                results.extend(gw_results)
            else:
                for call in gateway_calls:
                    yield {"event": "tool_call", "ts": ms(), "round": round_num + 1,
                           "tool": call.name, "params": call.params, "kind": "gateway"}
                    yield {"event": "tool_result", "ts": ms(), "round": round_num + 1,
                           "tool": call.name, "status": "error",
                           "reason": "No ToolGateway API key configured for this agent",
                           "data": None, "elapsed_ms": 0}
                    results.append({"tool": call.name, "status": "error",
                                    "reason": "No ToolGateway API key configured"})

        if not results:
            break

        tool_msg = format_tool_results_for_llm(results)
        conversation = conversation + [
            {"role": "assistant", "content": current},
            {"role": "user", "content": tool_msg},
        ]

        yield {"event": "llm_start", "ts": ms(), "round": round_num + 1,
               "message_count": len(conversation)}
        try:
            t_llm = time.monotonic()
            current, _ = await _call_llm(conversation, ai_gateway_token)
            llm_elapsed = int((time.monotonic() - t_llm) * 1000)
        except Exception as exc:
            yield {"event": "error", "ts": ms(), "message": str(exc)}
            return

        _, _, tc = parse_response(current)
        yield {"event": "llm_done", "ts": ms(), "round": round_num + 1,
               "elapsed_ms": llm_elapsed, "raw_llm": current, "has_tool_calls": bool(tc)}

        if session.interrupted:
            yield {"event": "interrupted", "ts": ms()}
            return

    # ── Parse annotations ────────────────────────────────────────────────────
    clean_text, annotations, _ = parse_response(current)
    yield {"event": "parse", "ts": ms(),
           "clean_text": clean_text, "annotation_count": len(annotations)}

    # ── TTS ──────────────────────────────────────────────────────────────────
    duration_ms = None
    sample_rate = None
    timeline: list[TimelineEvent] = []

    if voice_enabled:
        yield {"event": "tts_start", "ts": ms()}
        try:
            t_tts = time.monotonic()
            tts = await synthesize(clean_text, voice_config)
            tts_elapsed = int((time.monotonic() - t_tts) * 1000)
            audio_b64   = tts.get("audio")
            duration_ms = tts.get("duration_ms")
            sample_rate = tts.get("sample_rate")
            buffer_bytes = tts.get("buffer_bytes")
            timeline    = assemble_timeline(annotations, clean_text, tts)
            viseme_count = sum(1 for e in timeline if e.type == "viseme")
            yield {"event": "tts_done", "ts": ms(), "elapsed_ms": tts_elapsed,
                   "duration_ms": duration_ms, "sample_rate": sample_rate,
                   "viseme_count": viseme_count}
        except Exception as exc:
            yield {"event": "tts_error", "ts": ms(), "message": str(exc)}
            audio_b64 = None
            buffer_bytes = None
    else:
        audio_b64 = None
        buffer_bytes = None

    # ── Session bookkeeping (same as process_text) ───────────────────────────
    session.add_turn(user_text, clean_text)
    session.logger.log_assistant(
        turn=turn, text=clean_text, raw_llm=current,
        audio_b64=audio_b64, duration_ms=duration_ms,
        timeline=[e.model_dump() for e in timeline],
    )

    yield {
        "event": "done",
        "ts": ms(),
        "total_ms": ms(),
        "text": clean_text,
        "reasoning": reasoning,
        "timeline": [e.model_dump() for e in timeline],
        "duration_ms": duration_ms,
        "sample_rate": sample_rate,
    }
