"""HTTP client for VoiceService (http://localhost:8002)."""

import httpx
from app.config import settings


class VoiceClient:
    def __init__(self):
        self.base_url = settings.voiceservice_url

    async def transcribe(self, wav_bytes: bytes) -> str:
        """POST /stt with raw WAV bytes — returns transcript text."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{self.base_url}/stt",
                content=wav_bytes,
                headers={"Content-Type": "audio/wav"},
            )
            r.raise_for_status()
            data = r.json()
            # VoiceService returns {"text": "..."} or similar
            if isinstance(data, dict):
                return data.get("text", data.get("transcript", ""))
            return str(data)

    async def synthesize(
        self,
        text: str,
        voice: str,
        speed: float,
        noise_scale: float,
        noise_w: float,
    ) -> dict:
        """POST /tts — returns {audio_b64, visemes, duration_ms}."""
        payload = {
            "text": text,
            "voice": voice,
            "speed": speed,
            "noise_scale": noise_scale,
            "noise_w": noise_w,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                f"{self.base_url}/tts",
                json=payload,
            )
            if not r.is_success:
                raise RuntimeError(f"TTS error {r.status_code} (voice={voice!r}): {r.text[:200]}")
            r.raise_for_status()
            data = r.json()
            return {
                "audio_b64": data.get("audio_b64", data.get("audio", "")),
                "visemes": data.get("visemes", []),
                "duration_ms": data.get("duration_ms", data.get("duration", 0)),
            }
