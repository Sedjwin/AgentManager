"""Calls VoiceService for STT and TTS."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


async def transcribe(audio_bytes: bytes) -> str:
    """Send raw WAV bytes to VoiceService STT. Returns transcript string."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.voiceservice_url}/stt",
            content=audio_bytes,
            headers={"Content-Type": "audio/wav"},
        )
        resp.raise_for_status()
        return resp.json()["text"]


async def synthesize(text: str, voice_config: dict[str, Any] | None) -> dict[str, Any]:
    """
    Send text to VoiceService TTS.
    Returns the full response dict: audio (base64), visemes, duration_ms, etc.
    """
    voice_id = "glados"  # default
    speed = 1.0

    if voice_config:
        voice_id = voice_config.get("voice_id", voice_id)
        # Map normalized base_speed (0–1) to TTS speed multiplier (0.5–2.0)
        base_speed = voice_config.get("base_speed")
        if base_speed is not None:
            speed = 0.5 + base_speed * 1.5

    payload: dict[str, Any] = {"text": text, "voice": voice_id, "speed": speed}

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.voiceservice_url}/tts",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()
