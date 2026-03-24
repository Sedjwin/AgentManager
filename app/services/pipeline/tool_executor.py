"""Calls ToolGateway to execute tools on behalf of an agent."""
from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.services.pipeline.response_parser import ToolCall

logger = logging.getLogger(__name__)


async def execute_tool_calls(
    tool_calls: list[ToolCall],
    agent_api_key: str,
    session_id: str | None = None,
) -> list[dict]:
    """
    Execute a list of tool calls via ToolGateway.

    Each result is a dict:
        {tool_name, status, data, reason}  — matches ToolGateway ToolResult schema

    Failures (network, rejected) are returned as result dicts, not raised, so the
    orchestrator can always pass results back to the LLM for graceful handling.
    """
    results = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        for call in tool_calls:
            try:
                r = await client.post(
                    f"{settings.toolgateway_url}/api/execute",
                    json={
                        "tool_name": call.name,
                        "payload": call.params,
                        "session_id": session_id,
                    },
                    headers={"Authorization": f"Bearer {agent_api_key}"},
                )
                r.raise_for_status()
                results.append(r.json())
                logger.info("Tool call: %s → %s", call.name, r.json().get("status"))
            except httpx.HTTPStatusError as exc:
                logger.warning("Tool call %s failed: %s", call.name, exc)
                results.append({
                    "status": "error",
                    "tool": call.name,
                    "reason": f"ToolGateway returned {exc.response.status_code}",
                })
            except Exception as exc:
                logger.warning("Tool call %s error: %s", call.name, exc)
                results.append({
                    "status": "error",
                    "tool": call.name,
                    "reason": str(exc),
                })
    return results


def format_tool_results_for_llm(results: list[dict]) -> str:
    """
    Format tool results as a system message for the LLM's second pass.
    """
    lines = ["[Tool results — review these and call more tools if needed, or give your final response if you have all the information you need]"]
    for r in results:
        tool = r.get("tool", "unknown")
        status = r.get("status", "unknown")
        if status == "ok":
            data = r.get("data", {})
            lines.append(f"Tool '{tool}': {data}")
        else:
            reason = r.get("reason", "unknown error")
            lines.append(f"Tool '{tool}': {status} — {reason}")
    return "\n".join(lines)
