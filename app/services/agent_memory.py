"""Agent-level persistent memory utilities.

File layout under data/agents/{agent_id}/:
  PersonalContext.md  — agent's self-maintained memory, injected into every system prompt
  TaskList.md         — HeartbeatService-managed task list (agent reads only, written by HeartbeatService)
  history.jsonl       — lightweight event index: session starts/ends, tool calls (no message content)
  sessions/           — per-session logs (managed by SessionLogger)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_BASE = Path("data")

_PERSONAL_CONTEXT_TEMPLATE = """# Personal Context

This is your persistent memory. Update it using the update-personal-context tool whenever you learn something worth remembering across sessions — who you've spoken with, important topics, ongoing tasks, or personal notes.

_Nothing recorded yet._
"""


def agent_data_dir(agent_id: str) -> Path:
    return _BASE / "agents" / agent_id


def ensure_agent_data_dir(agent_id: str) -> None:
    """Create the agent data directory and scaffold default files if missing."""
    d = agent_data_dir(agent_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "sessions").mkdir(exist_ok=True)

    pc = d / "PersonalContext.md"
    if not pc.exists():
        pc.write_text(_PERSONAL_CONTEXT_TEMPLATE, encoding="utf-8")

    hist = d / "history.jsonl"
    if not hist.exists():
        hist.touch()


def read_personal_context(agent_id: str) -> str | None:
    path = agent_data_dir(agent_id) / "PersonalContext.md"
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8").strip()
    return content if content else None


def write_personal_context(agent_id: str, content: str) -> None:
    path = agent_data_dir(agent_id) / "PersonalContext.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_task_list(agent_id: str) -> str | None:
    path = agent_data_dir(agent_id) / "TaskList.md"
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8").strip()
    return content if content else None


def append_history_event(agent_id: str, event_type: str, **kwargs: Any) -> None:
    path = agent_data_dir(agent_id) / "history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"ts": _now(), "type": event_type, **kwargs}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=str) + "\n")


def read_history(agent_id: str, limit: int = 50) -> list[dict]:
    path = agent_data_dir(agent_id) / "history.jsonl"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    events = []
    for line in lines:
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events[-limit:]


def read_session_conversation(agent_id: str, session_id: str) -> list[dict]:
    path = agent_data_dir(agent_id) / "sessions" / session_id / "conversation.jsonl"
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events


def list_sessions(agent_id: str) -> list[dict]:
    """Return session metadata dicts, newest first."""
    sessions_dir = agent_data_dir(agent_id) / "sessions"
    if not sessions_dir.exists():
        return []
    results = []
    for session_dir in sessions_dir.iterdir():
        meta_path = session_dir / "session.json"
        if meta_path.exists():
            try:
                results.append(json.loads(meta_path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                pass
    results.sort(key=lambda x: x.get("started_at", ""), reverse=True)
    return results


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
