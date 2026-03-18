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

EMOTION_TTS_PARAMS: dict[str, dict | None] = {
    "ANGRY":     {"speed": 1.1,  "noise_scale": 0.8,  "noise_w": 0.6},
    "SAD":       {"speed": 0.85, "noise_scale": 0.4,  "noise_w": 0.3},
    "HAPPY":     {"speed": 1.05, "noise_scale": 0.5,  "noise_w": 0.4},
    "EXCITED":   {"speed": 1.15, "noise_scale": 0.7,  "noise_w": 0.5},
    "CALM":      {"speed": 0.95, "noise_scale": 0.3,  "noise_w": 0.3},
    "SARCASTIC": {"speed": 1.0,  "noise_scale": 0.6,  "noise_w": 0.5},
    "CONFUSED":  {"speed": 0.9,  "noise_scale": 0.5,  "noise_w": 0.4},
    "NEUTRAL":   None,
}

_TAG_RE = re.compile(r'\[([A-Z_]+(?::[a-z0-9]+)?)\]')

# Emotion tag names (upper-case base, no colon suffix)
_EMOTION_TAGS = frozenset(EMOTION_TTS_PARAMS.keys())


def extract_tags(text: str) -> tuple[list[str], str]:
    """Return (tags_list, clean_text) from a response string."""
    tags = _TAG_RE.findall(text)
    clean = _TAG_RE.sub("", text).strip()
    # Collapse multiple spaces
    clean = re.sub(r"  +", " ", clean)
    return tags, clean


def _resolve_emotion(tags: list[str]) -> str:
    """Return the first recognised emotion tag, defaulting to NEUTRAL."""
    for tag in tags:
        base = tag.split(":")[0].upper()
        if base in _EMOTION_TAGS:
            return base
    return "NEUTRAL"


def _tts_params_for_emotion(emotion: str, agent) -> dict:
    """Merge agent default voice settings with any emotion override."""
    override = EMOTION_TTS_PARAMS.get(emotion)
    if override:
        return {
            "speed":       override["speed"],
            "noise_scale": override["noise_scale"],
            "noise_w":     override.get("noise_w", agent.noise_w),
        }
    # Default: use agent's own settings
    return {
        "speed":       agent.voice_speed,
        "noise_scale": agent.noise_scale,
        "noise_w":     agent.noise_w,
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
    if agent.system_prompt:
        messages.append({"role": "system", "content": agent.system_prompt})

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
    emotion = _resolve_emotion(tags)
    actions = [t for t in tags if t.split(":")[0].upper() not in _EMOTION_TAGS]

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
    tts_params = _tts_params_for_emotion(emotion, agent)
    t0 = time.monotonic()
    tts_result = await voice_client.synthesize(
        text=clean_text,
        voice=agent.voice,
        **tts_params,
    )
    stats["t_tts_ms"] = round((time.monotonic() - t0) * 1000)
    stats["audio_duration_ms"] = tts_result.get("duration_ms", 0)

    return {
        "transcript":    transcript,
        "response_text": response_text,
        "clean_text":    clean_text,
        "audio_b64":     tts_result.get("audio_b64", ""),
        "visemes":       tts_result.get("visemes", []),
        "emotion":       emotion,
        "actions":       actions,
        "stats":         stats,
    }
