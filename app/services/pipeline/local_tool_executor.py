"""Local tool executor — built-in AgentManager memory tools that don't route through ToolGateway."""
from __future__ import annotations

import logging

import httpx

from app.config import settings  # noqa: F401 — used in _check_tg_permission and _ask_agent
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
    "ask-agent",
}

# Injected into every agent's system prompt regardless of ToolGateway tool configuration.
LOCAL_TOOL_SKILL_MD = """\
---
MEMORY TOOLS:
You have built-in tools for managing your persistent memory and communicating with other agents. Use {tool:name|param=value} syntax.

{tool:update-personal-context|content=<your updated memory text>}
  Replaces your PersonalContext.md with <content>. Call this when you want to remember something across sessions.
  Best practice: include the previous context plus your new additions — this replaces the whole file.

{tool:read-history|limit=<N>}
  Returns your last N history events (session starts/ends, tool calls). Default limit: 30.

{tool:list-sessions|limit=<N>}
  Lists your past N sessions with metadata (session_id, username, started_at). Default limit: 20.

{tool:read-session|session_id=<id>}
  Reads the full conversation log for a specific past session.

{tool:read-personal-context}
  Re-reads your current PersonalContext.md (already injected at session start, but call this after updating it).

{tool:ask-agent|agent_id=<uuid>|message=<text>}
  Send a message to another agent and receive their response. The other agent decides what to share based on their own context and judgment. Use this to consult specialists or coordinate tasks across agents.

Current session ID: {current_session_id}

RULES:
- When a user asks you to "remember", "note", "save", or "keep" something across sessions, you MUST call update-personal-context immediately in that same response. Do not just say you will remember — call the tool or it will not be saved.
- When asked to recall something from a previous session: call list-sessions, then read-session on the sessions with the highest turn_count. Skip ONLY sessions where turn_count=1 (those are system sessions). Sessions with turn_count=null are old sessions that may contain real conversations — read them too. Read as many sessions as needed until you find what you're looking for.
- Do NOT call read-session on your own current session ID listed above.\
"""


def is_local_tool(name: str) -> bool:
    return name in LOCAL_TOOL_NAMES


async def execute_local_tool_async(call: ToolCall, agent_id: str, session_id: str | None = None) -> dict:
    """Async version — required for ask-agent which makes HTTP calls.
    Checks ToolGateway permission (enabled/disabled) before executing if service key is configured.
    """
    # Permission check via ToolGateway (logs the call + enforces system-wide enable/disable)
    tg_denied = await _check_tg_permission(call, agent_id, session_id)
    if tg_denied:
        return tg_denied

    if call.name == "ask-agent":
        return await _ask_agent(call, agent_id, session_id)
    # All other local tools are sync — delegate
    return execute_local_tool(call, agent_id, session_id)


async def _check_tg_permission(call: ToolCall, agent_id: str, session_id: str | None) -> dict | None:
    """
    Call ToolGateway /api/execute for permission check + audit logging.
    For kind=local tools, TG returns {proceed: True} on success.
    Returns None if allowed (or TG is not configured), a rejection dict if denied.
    """
    key = settings.toolgateway_service_key
    if not key:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                f"{settings.toolgateway_url}/api/execute",
                json={
                    "tool_name": call.name,
                    "payload": call.params,
                    "session_id": session_id,
                    "originating_user_id": agent_id,
                },
                headers={"Authorization": f"Bearer {key}"},
            )
            if r.status_code == 200:
                result = r.json()
                if result.get("status") == "rejected":
                    return {
                        "tool": call.name,
                        "status": "error",
                        "reason": f"Tool denied by ToolGateway: {result.get('reason', 'disabled')}",
                    }
                return None  # allowed
            # Non-200: TG unavailable or tool not registered yet — allow anyway
            return None
    except Exception:
        return None  # TG unavailable — fail open (don't break agents)


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
            limit = int(call.params.get("limit", 20))
            sessions = list_sessions(agent_id)[:limit]
            summary = [
                {
                    "session_id": s["session_id"],
                    "started_at": s["started_at"],
                    "ended_at": s.get("ended_at"),
                    "turn_count": s.get("turn_count"),
                    "username": s.get("username"),
                }
                for s in sessions
            ]
            return {"tool": call.name, "status": "ok", "data": {"sessions": summary, "shown": len(summary)}}

        elif call.name == "read-session":
            sid = call.params.get("session_id", "")
            if not sid:
                return {"tool": call.name, "status": "error", "reason": "session_id parameter is required"}
            events = read_session_conversation(agent_id, sid)
            return {"tool": call.name, "status": "ok", "data": {"events": events, "count": len(events)}}

        elif call.name == "ask-agent":
            # ask-agent is async — callers should use execute_local_tool_async instead
            return {"tool": call.name, "status": "error", "reason": "ask-agent requires async context"}

    except Exception as exc:
        logger.warning("Local tool %s error: %s", call.name, exc)
        return {"tool": call.name, "status": "error", "reason": str(exc)}

    return {"tool": call.name, "status": "error", "reason": f"Unknown local tool: {call.name}"}


async def _ask_agent(call: ToolCall, caller_agent_id: str, session_id: str | None) -> dict:
    """
    Send a message to another agent via a system session.
    The target agent's full pipeline runs: PersonalContext injected, all tools available.
    The target agent decides what to share based on their own context and judgment.
    """
    target_agent_id = call.params.get("agent_id", "")
    message = call.params.get("message", "")

    if not target_agent_id:
        return {"tool": call.name, "status": "error", "reason": "agent_id parameter is required"}
    if not message:
        return {"tool": call.name, "status": "error", "reason": "message parameter is required"}
    if target_agent_id == caller_agent_id:
        return {"tool": call.name, "status": "error", "reason": "An agent cannot ask itself"}

    base = settings.agentmanager_url if hasattr(settings, "agentmanager_url") else "http://localhost:8003"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Start a cross-agent system session
            r = await client.post(
                f"{base}/agents/{target_agent_id}/session",
                json={},
                headers={
                    "X-Username": f"agent:{caller_agent_id}",
                    "X-User-Id": f"agent:{caller_agent_id}",
                },
            )
            r.raise_for_status()
            target_session_id = r.json()["session_id"]

            try:
                r2 = await client.post(
                    f"{base}/sessions/{target_session_id}/message",
                    json={"text": message},
                )
                r2.raise_for_status()
                response_text = r2.json().get("text", "")
                logger.info("ask-agent: %s → %s: %d chars response", caller_agent_id, target_agent_id, len(response_text))
                if session_id:
                    append_history_event(
                        caller_agent_id, "ask_agent",
                        session_id=session_id,
                        target_agent_id=target_agent_id,
                        status="ok",
                    )
                return {"tool": call.name, "status": "ok", "data": {"response": response_text, "agent_id": target_agent_id}}
            finally:
                await client.delete(f"{base}/sessions/{target_session_id}")

    except httpx.HTTPStatusError as exc:
        logger.warning("ask-agent to %s failed: %s", target_agent_id, exc)
        return {"tool": call.name, "status": "error", "reason": f"Agent returned {exc.response.status_code}"}
    except Exception as exc:
        logger.warning("ask-agent error: %s", exc)
        return {"tool": call.name, "status": "error", "reason": str(exc)}
