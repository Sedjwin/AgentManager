"""Calls VoiceService for STT and TTS."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


async def transcribe(audio_bytes: bytes) -> str:
    """Send raw WAV bytes to VoiceService STT. Returns transcript string."""
    timeout = httpx.Timeout(
        connect=10.0,
        read=settings.voiceservice_stt_timeout_s,
        write=settings.voiceservice_stt_timeout_s,
        pool=10.0,
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
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
    Speed and other synthesis params are controlled by per-voice settings stored
    in VoiceService (tunable via the VoiceService admin UI). Agents supply only
    the voice_id — no speed overrides.
    Returns the full response dict: audio (base64), visemes, duration_ms, etc.
    """
    voice_id = "glados"
    if voice_config:
        voice_id = voice_config.get("voice_id", voice_id)

    payload: dict[str, Any] = {"text": text, "voice": voice_id}

    timeout = httpx.Timeout(
        connect=10.0,
        read=settings.voiceservice_tts_timeout_s,
        write=settings.voiceservice_tts_timeout_s,
        pool=10.0,
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{settings.voiceservice_url}/tts",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()
