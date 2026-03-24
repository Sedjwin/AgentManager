"""Builds the LLM messages list for a given agent and conversation turn."""
from __future__ import annotations

from typing import Any

from app.services.pipeline.local_tool_executor import LOCAL_TOOL_SKILL_MD


_TOOL_PREAMBLE = """
---
TOOL CALLING:
You have access to tools. When you need to call a tool, emit a {tool:name} tag inline in your response at the point where the result should be inserted. You may optionally pass parameters using pipe-separated key=value pairs: {tool:name|key=value|key=value}.

Important:
- Only call tools you have been given instructions for below.
- The gateway may deny tool requests based on policy. If a call is denied, acknowledge it gracefully.
- Do not emit tool tags in your final response — only in your first pass."""


def build_messages(
    agent_system_prompt: str,
    profile: dict[str, Any] | None,
    history: list[dict[str, str]],
    user_text: str,
    tool_use_enabled: bool = False,
    tool_skill_mds: list[str] | None = None,
    personal_context: str | None = None,
    task_list: str | None = None,
) -> list[dict[str, str]]:
    system = _build_system(
        agent_system_prompt, profile, tool_use_enabled, tool_skill_mds or [],
        personal_context=personal_context, task_list=task_list,
    )
    messages = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    return messages


def _build_system(
    agent_system_prompt: str,
    profile: dict[str, Any] | None,
    tool_use_enabled: bool,
    tool_skill_mds: list[str],
    personal_context: str | None = None,
    task_list: str | None = None,
) -> str:
    base = agent_system_prompt

    # Inject agent's persistent memory
    if personal_context:
        base += f"\n\n---\nPERSONAL CONTEXT (your persistent memory across sessions):\n{personal_context}"

    # Inject HeartbeatService task list if present
    if task_list:
        base += f"\n\n---\nTASK LIST (scheduled tasks from HeartbeatService):\n{task_list}"

    if profile is not None:
        display_name = profile.get("display_name", "Assistant")
        emotions = list(profile.get("emotions", {}).keys())
        actions = list(profile.get("actions", {}).keys())

        emotion_list = ", ".join(emotions) if emotions else "(none)"
        action_list = ", ".join(actions) if actions else "(none)"

        base += f"""
---
RESPONSE FORMAT:
You are {display_name}. You have a face and voice. When you respond, embed emotional and action cues inline in your text using curly brace tags.

Your available emotions (use ONLY these): {emotion_list}
Your available actions (use ONLY these): {action_list}

Syntax:
  {{name}} — use the exact name from the lists above, wrapped in curly braces.
  Emotions stay active until changed. Actions are one-time triggers.

Rules:
- Start every response with an emotion tag.
- Change emotions when your feeling genuinely shifts, not on every sentence.
- Use actions to punctuate key moments — a reaction, emphasis, a beat.
- Do NOT use emotions or actions not listed above.
- Write your spoken text naturally. The tags are invisible to the listener.
- Your response will be spoken aloud via text-to-speech. Write naturally — no markdown, no bullet points unless asked."""

    # Always inject memory tools (available to every agent)
    base += "\n\n" + LOCAL_TOOL_SKILL_MD

    # Inject gateway tools if configured
    if tool_use_enabled and tool_skill_mds:
        base += _TOOL_PREAMBLE
        for md in tool_skill_mds:
            if md.strip():
                base += "\n\n" + md.strip()

    return base
