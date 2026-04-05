from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


# ── Agent schemas ────────────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str
    ai_gateway_token: str
    system_prompt: str = ""
    voice_enabled: bool = False
    voice_config: dict[str, Any] | None = None
    profile: dict[str, Any] | None = None


class AgentUpdate(BaseModel):
    name: str | None = None
    ai_gateway_token: str | None = None
    system_prompt: str | None = None
    voice_enabled: bool | None = None
    voice_config: dict[str, Any] | None = None
    profile: dict[str, Any] | None = None
    memory_tools_enabled: bool | None = None


class AgentOut(BaseModel):
    agent_id: str
    name: str
    system_prompt: str
    voice_enabled: bool
    voice_config: dict[str, Any] | None = None
    profile: dict[str, Any] | None = None
    has_profile: bool
    um_user_id: int | None = None
    um_api_key: str | None = None
    tool_use_enabled: bool = False
    enabled_tools: list[str] = []
    memory_tools_enabled: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("has_profile", mode="before")
    @classmethod
    def compute_has_profile(cls, v: Any) -> bool:
        return bool(v)


class AgentListItem(BaseModel):
    agent_id: str
    name: str
    voice_enabled: bool
    has_profile: bool
    system_prompt: str
    profile: dict[str, Any] | None = None
    voice_config: dict[str, Any] | None = None
    um_user_id: int | None = None
    tool_use_enabled: bool = False
    enabled_tools: list[str] = []
    memory_tools_enabled: bool = True

    model_config = {"from_attributes": True}


class AgentToolItem(BaseModel):
    tool_id: str
    name: str
    description: str
    state: str
    enabled: bool
    skill_md: str
    grant_id: int
    grant_enabled: bool


class AgentToolConfig(BaseModel):
    tool_use_enabled: bool
    enabled_tools: list[str]  # list of tool names


class SessionBrowserEntry(BaseModel):
    session_id: str
    started_at: datetime | None = None
    username: str | None = None
    user_id: str | None = None
    title: str | None = None
    first_line: str | None = None
    display_title: str
    has_saved_title: bool = False


class SessionBrowserUserGroup(BaseModel):
    username: str
    session_count: int
    sessions: list[SessionBrowserEntry]


class SessionLogEvent(BaseModel):
    ts: str | None = None
    turn: int | None = None
    role: str | None = None
    source: str | None = None
    text: str | None = None
    chunk_index: int | None = None
    is_final: bool | None = None
    duration_ms: int | None = None
    audio_file: str | None = None
    timeline: list[dict[str, Any]] | None = None
    raw_llm: str | None = None
    details: dict[str, Any]


class SessionLogDetail(BaseModel):
    session_id: str
    agent_id: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    turn_count: int | None = None
    username: str | None = None
    user_id: str | None = None
    device_capabilities: dict[str, Any] | None = None
    title: str | None = None
    first_line: str | None = None
    display_title: str
    has_saved_title: bool = False
    events: list[SessionLogEvent]


# ── Session schemas ──────────────────────────────────────────────────────────

class DeviceCapabilities(BaseModel):
    device_id: str | None = None
    capabilities: dict[str, Any] = {}


class SessionOut(BaseModel):
    session_id: str
    agent_id: str
    type: str  # "interaction" or "functional"
    profile: dict[str, Any] | None = None


# ── Message / response schemas ───────────────────────────────────────────────

class TextMessage(BaseModel):
    text: str
    history: list[dict[str, str]] = []


class TimelineEvent(BaseModel):
    t: int          # milliseconds from start of audio
    type: str       # "emotion" | "action" | "viseme"
    value: str | int


class AgentResponse(BaseModel):
    session_id: str
    text: str = ""                          # clean text (tags stripped)
    reasoning: str | None = None            # chain-of-thought from thinking models
    transcript: str | None = None           # if input was audio
    audio: str | None = None               # base64 WAV
    duration_ms: int | None = None
    sample_rate: int | None = None
    buffer_bytes: int | None = None
    timeline: list[TimelineEvent] = []
    chunk_index: int = 0
    is_final: bool = True
    tool_call: dict | None = None           # tool status event: {name, status, elapsed_ms?, reason?}


class InterruptRequest(BaseModel):
    session_id: str


class HistoryMessage(BaseModel):
    role: str       # "user" or "assistant"
    content: str


class HistoryLoad(BaseModel):
    """Body for POST /sessions/{id}/history — pre-populates in-memory session history."""
    messages: list[HistoryMessage]
