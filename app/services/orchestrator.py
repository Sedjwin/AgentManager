"""Orchestration logic: STT → LLM → tag extraction → TTS."""

import json
import re
import time

import httpx

from .aigateway import AIGatewayClient
from .voice import VoiceClient

_EPAPER_URL = "http://localhost:8004"


async def _push_display(agent_name: str, clean_text: str, color: str) -> None:
    """Fire-and-forget: send agent response to the e-ink display."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{_EPAPER_URL}/api/show",
                json={
                    "type": "message",
                    "agent": agent_name,
                    "title": "",
                    "body": clean_text,
                    "color": color,
                    "duration": 600,   # 10 min, then revert to idle
                },
            )
    except Exception:
        pass   # display is optional; never fail a chat because of it

# Fallback universal emotions (used if agent has no matching custom emotion)
_FALLBACK_EMOTION_PARAMS: dict[str, dict | None] = {
    "ANGRY":     {"energy": 0.85, "valence": -0.8},
    "SAD":       {"energy": 0.25, "valence": -0.7},
    "HAPPY":     {"energy": 0.7,  "valence": 0.8},
    "EXCITED":   {"energy": 0.95, "valence": 0.9},
    "CALM":      {"energy": 0.3,  "valence": 0.1},
    "SARCASTIC": {"energy": 0.5,  "valence": -0.3},
    "CONFUSED":  {"energy": 0.45, "valence": -0.2},
    "NEUTRAL":   {"energy": 0.5,  "valence": 0.0},
}

_TAG_RE = re.compile(r'\[([A-Z_]+(?::[a-z0-9]+)?)\]')


def extract_tags(text: str) -> tuple[list[str], str]:
    """Return (tags_list, clean_text) from a response string."""
    tags = _TAG_RE.findall(text)
    clean = _TAG_RE.sub("", text).strip()
    clean = re.sub(r"  +", " ", clean)
    return tags, clean


def _get_agent_emotions(agent) -> dict:
    """Parse agent.emotions JSON safely. Returns {} on failure."""
    import json as _json
    v = agent.emotions
    if not v:
        return {}
    if isinstance(v, dict):
        return v
    try:
        return _json.loads(v)
    except Exception:
        return {}


def _resolve_emotion(tags: list[str], agent_emotions: dict) -> tuple[str, dict]:
    """
    Find the first tag that matches an agent emotion or fallback emotion.
    Returns (emotion_name, params_dict).
    """
    emotions_lower = {k.lower(): (k, v) for k, v in agent_emotions.items()}
    for tag in tags:
        base = tag.split(":")[0].upper()
        # Check agent's custom emotions first (case-insensitive)
        match = emotions_lower.get(base.lower())
        if match:
            return base, match[1]
        # Check universal fallbacks
        if base in _FALLBACK_EMOTION_PARAMS:
            return base, _FALLBACK_EMOTION_PARAMS[base]
    return "NEUTRAL", _FALLBACK_EMOTION_PARAMS["NEUTRAL"]


def _tts_params_for_emotion(emotion_params: dict, agent) -> dict:
    """
    Derive TTS params from abstract emotion performance parameters.
    energy (0-1)   → speed multiplier applied on top of agent's base speed
    valence (-1,1) → noise_scale (more expressive at emotional extremes)
    """
    energy  = emotion_params.get("energy",  0.5)
    valence = emotion_params.get("valence", 0.0)

    # Speed: agent base speed scaled by energy (0.75× at energy=0, 1.25× at energy=1)
    speed_mult = 0.75 + energy * 0.5
    speed = round(agent.voice_speed * speed_mult, 2)

    # Noise: more expressive the further from neutral (0.15 base, up to 0.6 at extremes)
    noise_scale = round(0.15 + abs(valence) * 0.3 + energy * 0.15, 3)
    noise_w     = round(agent.noise_w * (0.8 + energy * 0.4), 3)

    return {
        "speed":       max(0.5, min(2.5, speed)),
        "noise_scale": max(0.0, min(1.0, noise_scale)),
        "noise_w":     max(0.0, min(1.0, noise_w)),
    }


async def orchestrate(
    agent,
    text_input: str | None = None,
    audio_bytes: bytes | None = None,
    history: list | None = None,
) -> dict:
    """
    Full pipeline: (optional STT) → LLM → tag extraction → TTS.

    Returns a dict with all response fields + stats.
    """
    stats: dict = {
        "t_stt_ms": 0,
        "t_llm_ms": 0,
        "t_tts_ms": 0,
        "model_used": None,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "audio_duration_ms": 0,
    }

    voice_client = VoiceClient()
    gw_client = AIGatewayClient(agent.gateway_token or "")

    # ── 1. STT ─────────────────────────────────────────────────────────────────
    transcript = text_input or ""
    if audio_bytes:
        t0 = time.monotonic()
        transcript = await voice_client.transcribe(audio_bytes)
        stats["t_stt_ms"] = round((time.monotonic() - t0) * 1000)

    # ── 2. Build messages ──────────────────────────────────────────────────────
    messages: list[dict] = []
    agent_emotions = _get_agent_emotions(agent)
    system_content = agent.system_prompt or ""
    if agent_emotions and system_content:
        # Inject emotion tag list so LLM knows available emotions
        tag_list = " ".join(f"[{k.upper()}]" for k in agent_emotions)
        if "[" not in system_content:   # avoid double-injection
            system_content += f"\n\nAvailable emotion tags (use inline in responses): {tag_list}"
    if system_content:
        messages.append({"role": "system", "content": system_content})

    if history:
        messages.extend(history)

    if transcript:
        messages.append({"role": "user", "content": transcript})

    # ── 3. LLM completion ─────────────────────────────────────────────────────
    t0 = time.monotonic()
    gw_response = await gw_client.complete(
        messages=messages,
        model=agent.default_model or None,
    )
    stats["t_llm_ms"] = round((time.monotonic() - t0) * 1000)

    # Extract text + usage
    choice = gw_response.get("choices", [{}])[0]
    response_text: str = choice.get("message", {}).get("content", "")
    usage = gw_response.get("usage", {})
    stats["prompt_tokens"] = usage.get("prompt_tokens", 0)
    stats["completion_tokens"] = usage.get("completion_tokens", 0)
    stats["model_used"] = gw_response.get("model")

    # ── 4. Tag extraction ─────────────────────────────────────────────────────
    tags, clean_text = extract_tags(response_text)
    emotion, emotion_params = _resolve_emotion(tags, agent_emotions)
    actions = [t for t in tags if t.split(":")[0].upper() not in {k.upper() for k in {**agent_emotions, **_FALLBACK_EMOTION_PARAMS}}]

    # ── 4a. E-ink display action ───────────────────────────────────────────────
    # Agent includes [DISPLAY] or [DISPLAY:color] to push its response to the screen.
    for action in actions:
        base, _, param = action.partition(":")
        if base.upper() == "DISPLAY":
            color = param.lower() if param in ("blue", "green", "red", "yellow", "black") else "blue"
            import asyncio
            asyncio.create_task(_push_display(agent.name, clean_text, color))
            break

    # ── 5. TTS ─────────────────────────────────────────────────────────────────
    tts_params = _tts_params_for_emotion(emotion_params, agent)
    t0 = time.monotonic()
    try:
        tts_result = await voice_client.synthesize(
            text=clean_text,
            voice=agent.voice,
            **tts_params,
        )
    except Exception as tts_err:
        from fastapi import HTTPException as _HTTPException
        raise _HTTPException(
            status_code=502,
            detail=f"TTS failed (voice={agent.voice!r}): {tts_err}"
        ) from tts_err
    stats["t_tts_ms"] = round((time.monotonic() - t0) * 1000)
    stats["audio_duration_ms"] = tts_result.get("duration_ms", 0)

    return {
        "transcript":    transcript,
        "response_text": response_text,
        "clean_text":    clean_text,
        "audio_b64":     tts_result.get("audio_b64", ""),
        "visemes":       tts_result.get("visemes", []),
        "emotion":       emotion,
        "emotion_params": emotion_params,
        "actions":       actions,
        "stats":         stats,
    }
