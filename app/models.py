import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Agent(Base):
    __tablename__ = "agents"

    agent_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    ai_gateway_token: Mapped[str] = mapped_column(String, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    voice_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    voice_config: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON string or null
    profile: Mapped[str | None] = mapped_column(Text, nullable=True)        # JSON string or null
    um_user_id: Mapped[int | None] = mapped_column(nullable=True)           # UserManager principal ID
    um_api_key: Mapped[str | None] = mapped_column(String, nullable=True)  # UserManager API key
    tool_use_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled_tools: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    memory_tools_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # JSON: [{"name": "get-time", "skill_md": "..."}]
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
