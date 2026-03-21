"""Builds the LLM messages list for a given agent and conversation turn."""
from __future__ import annotations

from typing import Any


def build_messages(
    agent_system_prompt: str,
    profile: dict[str, Any] | None,
    history: list[dict[str, str]],
    user_text: str,
) -> list[dict[str, str]]:
    system = _build_system(agent_system_prompt, profile)
    messages = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    return messages


def _build_system(agent_system_prompt: str, profile: dict[str, Any] | None) -> str:
    if profile is None:
        # Functional agent — plain system prompt, optionally voice-aware
        return agent_system_prompt

    display_name = profile.get("display_name", "Assistant")
    emotions = list(profile.get("emotions", {}).keys())
    actions = list(profile.get("actions", {}).keys())

    emotion_list = ", ".join(emotions) if emotions else "(none)"
    action_list = ", ".join(actions) if actions else "(none)"

    annotation_block = f"""
---
RESPONSE FORMAT:
You are {display_name}. You have a face and voice. When you respond, embed emotional and action cues inline in your text using curly brace tags.

Your available emotions (use ONLY these): {emotion_list}
Your available actions (use ONLY these): {action_list}

Syntax:
  {{emotion:name}} — shift to this emotional state. Stays active until changed.
  {{action:name}}  — trigger a one-time expression/gesture at this point.

Rules:
- Start every response with an emotion tag.
- Change emotions when your feeling genuinely shifts, not on every sentence.
- Use actions to punctuate key moments — a reaction, emphasis, a beat.
- Do NOT use emotions or actions not listed above.
- Write your spoken text naturally. The tags are invisible to the listener.
- Your response will be spoken aloud via text-to-speech. Write naturally — no markdown, no bullet points unless asked."""

    return agent_system_prompt + annotation_block
