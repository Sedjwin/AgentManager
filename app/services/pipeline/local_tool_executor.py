"""Local tool executor — built-in AgentManager memory tools that don't route through ToolGateway."""
from __future__ import annotations

import logging

from app.services.agent_memory import (
    append_history_event,
    list_sessions,
    read_history,
    read_personal_context,
    read_session_conversation,
    write_personal_context,
)
from app.services.pipeline.response_parser import ToolCall

logger = logging.getLogger(__name__)

LOCAL_TOOL_NAMES: set[str] = {
    "update-personal-context",
    "read-personal-context",
    "read-history",
    "list-sessions",
    "read-session",
}

# Injected into every agent's system prompt regardless of ToolGateway tool configuration.
LOCAL_TOOL_SKILL_MD = """\
---
MEMORY TOOLS:
You have built-in tools for managing your persistent memory. Use {tool:name|param=value} syntax (same as other tools).

Available memory tools:

{tool:update-personal-context|content=<your updated memory text>}
  Replaces your PersonalContext.md with <content>. Call this when you want to remember something across sessions.
  Best practice: include the previous context plus your new additions — this replaces the whole file.

{tool:read-history|limit=<N>}
  Returns your last N history events (session starts/ends, tool calls). Default limit: 30.

{tool:list-sessions}
  Lists your past sessions with metadata (session_id, username, started_at).

{tool:read-session|session_id=<id>}
  Reads the full conversation log for a specific past session.

{tool:read-personal-context}
  Re-reads your current PersonalContext.md (already injected at session start, but call this after updating it).\
"""


def is_local_tool(name: str) -> bool:
    return name in LOCAL_TOOL_NAMES


def execute_local_tool(call: ToolCall, agent_id: str, session_id: str | None = None) -> dict:
    """Execute a local memory tool. Returns a ToolGateway-compatible result dict."""
    try:
        if call.name == "update-personal-context":
            content = call.params.get("content", "")
            if not content:
                return {"tool": call.name, "status": "error", "reason": "content parameter is required"}
            write_personal_context(agent_id, content)
            if session_id:
                append_history_event(agent_id, "tool_call", session_id=session_id, tool=call.name, status="ok")
            return {"tool": call.name, "status": "ok", "data": {"message": "PersonalContext.md updated."}}

        elif call.name == "read-personal-context":
            content = read_personal_context(agent_id)
            return {"tool": call.name, "status": "ok", "data": {"content": content or "(empty)"}}

        elif call.name == "read-history":
            limit = int(call.params.get("limit", 30))
            events = read_history(agent_id, limit=limit)
            return {"tool": call.name, "status": "ok", "data": {"events": events, "count": len(events)}}

        elif call.name == "list-sessions":
            sessions = list_sessions(agent_id)
            summary = [
                {
                    "session_id": s["session_id"],
                    "started_at": s["started_at"],
                    "user_id": s.get("user_id"),
                    "username": s.get("username"),
                }
                for s in sessions
            ]
            return {"tool": call.name, "status": "ok", "data": {"sessions": summary}}

        elif call.name == "read-session":
            sid = call.params.get("session_id", "")
            if not sid:
                return {"tool": call.name, "status": "error", "reason": "session_id parameter is required"}
            events = read_session_conversation(agent_id, sid)
            return {"tool": call.name, "status": "ok", "data": {"events": events, "count": len(events)}}

    except Exception as exc:
        logger.warning("Local tool %s error: %s", call.name, exc)
        return {"tool": call.name, "status": "error", "reason": str(exc)}

    return {"tool": call.name, "status": "error", "reason": f"Unknown local tool: {call.name}"}
