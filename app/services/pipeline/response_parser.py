"""Parses LLM annotated output into clean text + annotation list with char positions."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Matches {emotion:name}, {action:name} — tolerant of extra whitespace
_TAG_RE = re.compile(r"\{\s*(emotion|action)\s*:\s*([a-zA-Z0-9_]+)\s*\}")

# Matches any {word} or {word_word} — used for bare-name pass when profile present
_BARE_TAG_RE = re.compile(r"\{\s*([a-zA-Z0-9_]+)\s*\}")

# Matches {tool:name} or {tool:name|key=value|key=value}
_TOOL_RE = re.compile(r"\{\s*tool\s*:\s*([a-zA-Z0-9_-]+)([^}]*)?\s*\}")


@dataclass
class Annotation:
    char: int   # position in clean_text where this event fires
    type: str   # "emotion" or "action"
    value: str  # the name


@dataclass
class ToolCall:
    name: str
    params: dict = field(default_factory=dict)


def _parse_tool_params(raw: str) -> dict:
    """Parse |key=value|key=value into a dict. Returns {} if raw is empty."""
    params = {}
    for part in raw.split("|"):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            params[k.strip()] = v.strip()
    return params


def parse_response(
    raw: str,
    profile: dict[str, Any] | None = None,
) -> tuple[str, list[Annotation], list[ToolCall]]:
    """
    Strip {emotion:x}, {action:x}, and {tool:name} tags from raw LLM output.

    When an interaction agent profile is provided, also recognises bare {name}
    tags where the name is in the agent's emotion or action vocabulary — this
    handles the common case where the model omits the type prefix.

    Returns:
        clean_text  — text with all tags removed (safe to send to TTS)
        annotations — emotion/action events with char positions in clean_text
        tool_calls  — ordered list of tool invocations extracted from the text
    """
    tool_calls: list[ToolCall] = []

    # First pass: extract and remove tool tags, recording them in order
    def _extract_tool(m: re.Match) -> str:
        tool_calls.append(ToolCall(
            name=m.group(1),
            params=_parse_tool_params(m.group(2) or ""),
        ))
        return ""  # remove the tag from text

    after_tools = _TOOL_RE.sub(_extract_tool, raw)

    # Build profile vocabulary lookups (only for interaction agents)
    emotion_names: set[str] = set()
    action_names: set[str] = set()
    if profile:
        emotion_names = set(profile.get("emotions", {}).keys())
        action_names = set(profile.get("actions", {}).keys())

    # Choose tag pattern: prefer prefixed {emotion:x}/{action:x}; also accept
    # bare {name} when it matches a known profile vocabulary term.
    annotations: list[Annotation] = []
    clean_parts: list[str] = []
    cursor = 0

    # Collect all tag matches — prefixed and (if profile present) bare
    matches: list[tuple[int, int, str, str]] = []  # (start, end, type, value)

    for m in _TAG_RE.finditer(after_tools):
        matches.append((m.start(), m.end(), m.group(1), m.group(2)))

    if emotion_names or action_names:
        for m in _BARE_TAG_RE.finditer(after_tools):
            name = m.group(1)
            if name in emotion_names:
                matches.append((m.start(), m.end(), "emotion", name))
            elif name in action_names:
                matches.append((m.start(), m.end(), "action", name))

    # Sort by position and deduplicate overlapping spans (prefixed wins)
    matches.sort(key=lambda x: x[0])
    deduped: list[tuple[int, int, str, str]] = []
    last_end = 0
    for start, end, typ, val in matches:
        if start >= last_end:
            deduped.append((start, end, typ, val))
            last_end = end

    for start, end, typ, val in deduped:
        preceding = after_tools[cursor:start]
        clean_parts.append(preceding)
        cursor = end
        annotations.append(Annotation(
            char=sum(len(p) for p in clean_parts),
            type=typ,
            value=val,
        ))

    clean_parts.append(after_tools[cursor:])
    clean_text = "".join(clean_parts).strip()
    # Collapse any double-spaces left by removed tags
    clean_text = re.sub(r" {2,}", " ", clean_text)

    return clean_text, annotations, tool_calls
