"""Builds the LLM messages list for a given agent and conversation turn."""
from __future__ import annotations

from typing import Any


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
) -> list[dict[str, str]]:
    system = _build_system(agent_system_prompt, profile, tool_use_enabled, tool_skill_mds or [])
    messages = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    return messages


def _build_system(
    agent_system_prompt: str,
    profile: dict[str, Any] | None,
    tool_use_enabled: bool,
    tool_skill_mds: list[str],
) -> str:
    base = agent_system_prompt

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

    if tool_use_enabled and tool_skill_mds:
        base += _TOOL_PREAMBLE
        for md in tool_skill_mds:
            if md.strip():
                base += "\n\n" + md.strip()

    return base
