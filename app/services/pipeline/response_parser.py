"""Parses LLM annotated output into clean text + annotation list with char positions."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Matches {emotion:name}, {action:name} — tolerant of extra whitespace
_TAG_RE = re.compile(r"\{\s*(emotion|action)\s*:\s*([a-zA-Z0-9_]+)\s*\}")

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


def parse_response(raw: str) -> tuple[str, list[Annotation], list[ToolCall]]:
    """
    Strip {emotion:x}, {action:x}, and {tool:name} tags from raw LLM output.

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

    # Second pass: extract emotion/action tags with char positions
    annotations: list[Annotation] = []
    clean_parts: list[str] = []
    cursor = 0

    for match in _TAG_RE.finditer(after_tools):
        preceding = after_tools[cursor:match.start()]
        clean_parts.append(preceding)
        cursor = match.end()
        annotations.append(Annotation(
            char=sum(len(p) for p in clean_parts),
            type=match.group(1),
            value=match.group(2),
        ))

    clean_parts.append(after_tools[cursor:])
    clean_text = "".join(clean_parts).strip()
    # Collapse any double-spaces left by removed tags
    clean_text = re.sub(r" {2,}", " ", clean_text)

    return clean_text, annotations, tool_calls
