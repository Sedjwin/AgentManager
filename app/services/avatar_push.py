"""Fire-and-forget push of utterance data to AvatarService.

Called after AgentResponse is built. Non-blocking — errors are logged, never raised.
No-ops if AVATAR_SERVICE_URL is unset or device has no avatar_device_id.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.schemas import AgentResponse

logger = logging.getLogger(__name__)


async def push_utterance(
    agent_id: str,
    device_capabilities: dict[str, Any],
    response: AgentResponse,
) -> None:
    if not settings.avatar_service_url:
        return

    # Support avatar_device_id at the top level OR nested under "capabilities"
    device_id = (
        device_capabilities.get("avatar_device_id")
        or device_capabilities.get("capabilities", {}).get("avatar_device_id")
    )
    if not device_id:
        return

    if not response.audio:
        return

    try:
        payload = {
            "agent_id": agent_id,
            "audio_b64": response.audio,
            "duration_ms": response.duration_ms or 0,
            "sample_rate": response.sample_rate or 22050,
            "timeline": [e.model_dump() for e in response.timeline],
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                f"{settings.avatar_service_url}/api/push/{device_id}",
                json=payload,
            )
            if r.status_code not in (200, 503):
                logger.warning("AvatarService push returned %d for device %s", r.status_code, device_id)
    except Exception as exc:
        logger.warning("AvatarService push failed for device %s: %s", device_id, exc)
