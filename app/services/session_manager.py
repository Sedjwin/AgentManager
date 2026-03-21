"""In-memory session store. Sessions are ephemeral — not persisted across restarts."""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Session:
    session_id: str
    agent_id: str
    device_capabilities: dict[str, Any]
    history: list[dict[str, str]] = field(default_factory=list)
    interrupted: bool = False
    _interrupt_event: asyncio.Event = field(default_factory=asyncio.Event)

    def interrupt(self) -> None:
        self.interrupted = True
        self._interrupt_event.set()

    def clear_interrupt(self) -> None:
        self.interrupted = False
        self._interrupt_event.clear()

    def add_turn(self, user_text: str, assistant_text: str) -> None:
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": assistant_text})


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self, agent_id: str, device_capabilities: dict[str, Any]) -> Session:
        sid = str(uuid.uuid4())
        session = Session(
            session_id=sid,
            agent_id=agent_id,
            device_capabilities=device_capabilities,
        )
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


session_manager = SessionManager()
