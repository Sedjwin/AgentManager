"""Merges annotations (char positions) + VoiceService response into a unified timeline."""
from __future__ import annotations

from typing import Any

from app.services.pipeline.response_parser import Annotation
from app.schemas import TimelineEvent


def assemble_timeline(
    annotations: list[Annotation],
    clean_text: str,
    tts_response: dict[str, Any],
) -> list[TimelineEvent]:
    """
    Build a unified timeline of emotion, action, and viseme events.

    Emotion/action positions are mapped to timestamps proportionally:
        timestamp = (char_pos / total_chars) * duration_ms

    Viseme events come directly from VoiceService with their offset_ms.
    """
    events: list[TimelineEvent] = []
    duration_ms: int = tts_response.get("duration_ms", 0)
    total_chars = max(len(clean_text), 1)

    # Map annotations (char pos) → timestamps
    for ann in annotations:
        t = int((ann.char / total_chars) * duration_ms)
        events.append(TimelineEvent(t=t, type=ann.type, value=ann.value))

    # Viseme events from VoiceService
    for v in tts_response.get("visemes", []):
        offset = v.get("offset_ms", v.get("viseme_id", 0))  # offset_ms is the timestamp
        viseme_id = v.get("viseme_id", 0)
        # offset_ms is the time, viseme_id is the shape
        t_ms = v.get("offset_ms", 0)
        events.append(TimelineEvent(t=t_ms, type="viseme", value=viseme_id))

    # Sort by time
    events.sort(key=lambda e: e.t)
    return events
