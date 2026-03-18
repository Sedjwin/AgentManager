import secrets
import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped

from app.database import Base
from pydantic import BaseModel, Field


# ── SQLAlchemy ORM ─────────────────────────────────────────────────────────────

class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    api_key: Mapped[str] = Column(String(64), unique=True, index=True, default=lambda: secrets.token_hex(32))

    # Identity
    name: Mapped[str] = Column(String(128), nullable=False)
    bio: Mapped[Optional[str]] = Column(Text, nullable=True)
    avatar_spec: Mapped[Optional[str]] = Column(Text, nullable=True)  # JSON string

    # Setup
    system_prompt: Mapped[Optional[str]] = Column(Text, nullable=True)
    gateway_token: Mapped[Optional[str]] = Column(String(256), nullable=True)
    default_model: Mapped[Optional[str]] = Column(String(128), nullable=True)
    smart_routing: Mapped[bool] = Column(Boolean, default=True)
    mcp_tools: Mapped[Optional[str]] = Column(Text, nullable=True)  # JSON list string
    accepts_attachments: Mapped[bool] = Column(Boolean, default=False)
    accepts_images: Mapped[bool] = Column(Boolean, default=False)
    enabled: Mapped[bool] = Column(Boolean, default=True)
    demo_playground_enabled: Mapped[bool] = Column(Boolean, default=True)

    # Voice
    voice: Mapped[str] = Column(String(32), default="glados")
    voice_speed: Mapped[float] = Column(Float, default=1.0)
    noise_scale: Mapped[float] = Column(Float, default=0.333)
    noise_w: Mapped[float] = Column(Float, default=0.333)

    # Personality
    personality_description: Mapped[Optional[str]] = Column(Text, nullable=True)
    traits: Mapped[Optional[str]] = Column(Text, nullable=True)   # JSON list string
    emotions: Mapped[Optional[str]] = Column(Text, nullable=True) # JSON object string

    created_at: Mapped[datetime] = Column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str
    bio: Optional[str] = None
    avatar_spec: Optional[Any] = None        # dict or None
    system_prompt: Optional[str] = None
    gateway_token: Optional[str] = None
    default_model: Optional[str] = None
    smart_routing: bool = True
    mcp_tools: Optional[Any] = None          # list or None
    accepts_attachments: bool = False
    accepts_images: bool = False
    enabled: bool = True
    demo_playground_enabled: bool = True
    voice: str = "glados"
    voice_speed: float = 1.0
    noise_scale: float = 0.333
    noise_w: float = 0.333
    personality_description: Optional[str] = None
    traits: Optional[Any] = None             # list or None
    emotions: Optional[Any] = None           # dict or None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    avatar_spec: Optional[Any] = None
    system_prompt: Optional[str] = None
    gateway_token: Optional[str] = None
    default_model: Optional[str] = None
    smart_routing: Optional[bool] = None
    mcp_tools: Optional[Any] = None
    accepts_attachments: Optional[bool] = None
    accepts_images: Optional[bool] = None
    enabled: Optional[bool] = None
    demo_playground_enabled: Optional[bool] = None
    voice: Optional[str] = None
    voice_speed: Optional[float] = None
    noise_scale: Optional[float] = None
    noise_w: Optional[float] = None
    personality_description: Optional[str] = None
    traits: Optional[Any] = None
    emotions: Optional[Any] = None


class AgentResponse(BaseModel):
    id: int
    api_key: str
    name: str
    bio: Optional[str] = None
    avatar_spec: Optional[Any] = None
    system_prompt: Optional[str] = None
    gateway_token: Optional[str] = None
    default_model: Optional[str] = None
    smart_routing: bool
    mcp_tools: Optional[Any] = None
    accepts_attachments: bool
    accepts_images: bool
    enabled: bool
    demo_playground_enabled: bool
    voice: str
    voice_speed: float
    noise_scale: float
    noise_w: float
    personality_description: Optional[str] = None
    traits: Optional[Any] = None
    emotions: Optional[Any] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_agent(cls, agent: Agent) -> "AgentResponse":
        """Deserialize JSON string fields before returning."""
        data = {
            "id": agent.id,
            "api_key": agent.api_key,
            "name": agent.name,
            "bio": agent.bio,
            "avatar_spec": _parse_json(agent.avatar_spec),
            "system_prompt": agent.system_prompt,
            "gateway_token": agent.gateway_token,
            "default_model": agent.default_model,
            "smart_routing": agent.smart_routing,
            "mcp_tools": _parse_json(agent.mcp_tools),
            "accepts_attachments": agent.accepts_attachments,
            "accepts_images": agent.accepts_images,
            "enabled": agent.enabled,
            "demo_playground_enabled": agent.demo_playground_enabled,
            "voice": agent.voice,
            "voice_speed": agent.voice_speed,
            "noise_scale": agent.noise_scale,
            "noise_w": agent.noise_w,
            "personality_description": agent.personality_description,
            "traits": _parse_json(agent.traits),
            "emotions": _parse_json(agent.emotions),
            "created_at": agent.created_at,
            "updated_at": agent.updated_at,
        }
        return cls(**data)


def _parse_json(value: Optional[str]) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def _dump_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)


def apply_create(schema: AgentCreate) -> Agent:
    """Convert AgentCreate schema to ORM Agent instance."""
    return Agent(
        name=schema.name,
        bio=schema.bio,
        avatar_spec=_dump_json(schema.avatar_spec),
        system_prompt=schema.system_prompt,
        gateway_token=schema.gateway_token,
        default_model=schema.default_model,
        smart_routing=schema.smart_routing,
        mcp_tools=_dump_json(schema.mcp_tools),
        accepts_attachments=schema.accepts_attachments,
        accepts_images=schema.accepts_images,
        enabled=schema.enabled,
        demo_playground_enabled=schema.demo_playground_enabled,
        voice=schema.voice,
        voice_speed=schema.voice_speed,
        noise_scale=schema.noise_scale,
        noise_w=schema.noise_w,
        personality_description=schema.personality_description,
        traits=_dump_json(schema.traits),
        emotions=_dump_json(schema.emotions),
    )


def apply_update(agent: Agent, schema: AgentUpdate) -> Agent:
    """Merge non-None fields from AgentUpdate into ORM Agent."""
    data = schema.model_dump(exclude_none=True)
    json_fields = {"avatar_spec", "mcp_tools", "traits", "emotions"}
    for field, value in data.items():
        if field in json_fields:
            setattr(agent, field, _dump_json(value))
        else:
            setattr(agent, field, value)
    return agent
