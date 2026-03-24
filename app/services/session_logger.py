"""File-based session logger.

Folder layout:
  data/agents/{agent_id}/sessions/{session_id}/
    session.json          — metadata (who, when, device caps)
    conversation.jsonl    — one JSON line per event (user in / assistant out)
    audio_in/             — user audio uploads  (turn_NNNN_user.wav)
    audio_out/            — TTS output per chunk (turn_NNNN_chunk_NNN.wav)
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_BASE = Path("data")


class SessionLogger:
    def __init__(self, agent_id: str, session_id: str) -> None:
        self.agent_id = agent_id
        self.session_id = session_id
        self.session_dir = _BASE / "agents" / agent_id / "sessions" / session_id
        self.audio_in_dir  = self.session_dir / "audio_in"
        self.audio_out_dir = self.session_dir / "audio_out"
        self.convo_path    = self.session_dir / "conversation.jsonl"
        self._turn = 0

    def init(
        self,
        user_id: str | None,
        username: str | None,
        device_caps: dict[str, Any],
    ) -> None:
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.audio_in_dir.mkdir(exist_ok=True)
        self.audio_out_dir.mkdir(exist_ok=True)
        meta = {
            "session_id":        self.session_id,
            "agent_id":          self.agent_id,
            "started_at":        _now(),
            "user_id":           user_id,
            "username":          username,
            "device_capabilities": device_caps,
        }
        (self.session_dir / "session.json").write_text(json.dumps(meta, indent=2))

    # ── Turn counter ─────────────────────────────────────────────────────────

    def next_turn(self) -> int:
        self._turn += 1
        return self._turn

    # ── User input events ────────────────────────────────────────────────────

    def log_user_text(self, turn: int, text: str) -> None:
        self._append({
            "ts": _now(), "turn": turn, "role": "user",
            "source": "text", "text": text,
        })

    def log_user_audio(self, turn: int, transcript: str, audio_bytes: bytes) -> None:
        filename = f"turn_{turn:04d}_user.wav"
        (self.audio_in_dir / filename).write_bytes(audio_bytes)
        self._append({
            "ts": _now(), "turn": turn, "role": "user",
            "source": "audio", "text": transcript,
            "audio_file": f"audio_in/{filename}",
        })

    # ── Assistant output events ──────────────────────────────────────────────

    def log_assistant(
        self,
        turn: int,
        text: str,
        raw_llm: str | None,
        audio_b64: str | None,
        duration_ms: int | None,
        timeline: list[dict],
        chunk_index: int = 0,
        is_final: bool = True,
    ) -> None:
        audio_file = None
        if audio_b64:
            filename = f"turn_{turn:04d}_chunk_{chunk_index:03d}.wav"
            (self.audio_out_dir / filename).write_bytes(base64.b64decode(audio_b64))
            audio_file = f"audio_out/{filename}"

        entry: dict[str, Any] = {
            "ts":          _now(),
            "turn":        turn,
            "role":        "assistant",
            "text":        text,
            "chunk_index": chunk_index,
            "is_final":    is_final,
            "duration_ms": duration_ms,
            "audio_file":  audio_file,
            "timeline":    timeline,
        }
        # Only store raw LLM output on the first chunk (it covers the whole response)
        if chunk_index == 0 and raw_llm is not None:
            entry["raw_llm"] = raw_llm

        self._append(entry)

    def close(self, turn_count: int) -> None:
        """Update session.json with ended_at and turn_count."""
        meta_path = self.session_dir / "session.json"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
        meta["ended_at"] = _now()
        meta["turn_count"] = turn_count
        meta_path.write_text(json.dumps(meta, indent=2))

    # ── Internal ─────────────────────────────────────────────────────────────

    def _append(self, obj: dict) -> None:
        with self.convo_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, default=str) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
