"""Parses LLM annotated output into clean text + annotation list with char positions."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Matches {emotion:name}, {action:name} — tolerant of extra whitespace
_TAG_RE = re.compile(r"\{\s*(emotion|action)\s*:\s*([a-zA-Z0-9_]+)\s*\}")

# Matches any {word} or {word_word} — used for bare-name pass when profile present
_BARE_TAG_RE = re.compile(r"\{\s*([a-zA-Z0-9_]+)\s*\}")

# Detects the start of a tool tag — used by the manual scanner below
_TOOL_START_RE = re.compile(r"\{\s*tool\s*:\s*([a-zA-Z0-9_.\-]+)")


@dataclass
class Annotation:
    char: int   # position in clean_text where this event fires
    type: str   # "emotion" or "action"
    value: str  # the name


@dataclass
class ToolCall:
    name: str
    params: dict = field(default_factory=dict)


_XML_TOOL_BLOCK_RE = re.compile(
    r"<tool_call>\s*<tool:([a-zA-Z0-9_.\-]+)>(.*?)</tool_call>",
    re.DOTALL | re.IGNORECASE,
)
_XML_PARAM_RE = re.compile(r"<parameter=([^>]+)>(.*?)</parameter>", re.DOTALL)


def _normalize_xml_tool_calls(text: str) -> str:
    """Convert XML-style tool calls to {tool:name|...} format.

    Handles the hallucinated format:
        <tool_call>
        <tool:web.search>
        <parameter=query>foo</parameter>
        </tool_call>

    Converts to:
        {tool:web.search|query=foo}
    """
    def _replace(m: re.Match) -> str:
        name = m.group(1)
        body = m.group(2)
        pairs = [
            f"{pm.group(1).strip()}={pm.group(2).strip()}"
            for pm in _XML_PARAM_RE.finditer(body)
        ]
        if pairs:
            return "{tool:" + name + "|" + "|".join(pairs) + "}"
        return "{tool:" + name + "}"

    return _XML_TOOL_BLOCK_RE.sub(_replace, text)


def _extract_tool_tags(text: str, tool_calls: list) -> str:
    """Scan *text* for {tool:name|...} tags, append ToolCall objects to *tool_calls*,
    and return the text with all tool tags removed.

    Unlike a simple regex, this handles } characters inside parameter values
    (e.g. HTML/CSS/JS content) by finding every possible closing } and choosing
    the last one that falls before the next {tool: occurrence.
    """
    result_parts: list[str] = []
    pos = 0
    n = len(text)

    while pos < n:
        m = _TOOL_START_RE.search(text, pos)
        if m is None:
            result_parts.append(text[pos:])
            break

        tag_start = m.start()
        tool_name = m.group(1)
        after_name = m.end()  # index right after the tool name

        # Find the next {tool: start (if any) — our closing } must come before it
        next_m = _TOOL_START_RE.search(text, after_name)
        search_end = next_m.start() if next_m else n

        # Collect every } between after_name and search_end
        closing_candidates = [
            i for i in range(after_name, search_end)
            if text[i] == "}"
        ]

        if not closing_candidates:
            # Malformed — no closing brace; emit the literal { and advance past it
            result_parts.append(text[pos: tag_start + 1])
            pos = tag_start + 1
            continue

        # Pick the last candidate: maximises the captured param string
        tag_end = closing_candidates[-1] + 1  # exclusive
        params_raw = text[after_name: tag_end - 1]  # strip closing }

        tool_calls.append(ToolCall(
            name=tool_name,
            params=_parse_tool_params(params_raw),
        ))

        result_parts.append(text[pos: tag_start])  # text before this tag
        pos = tag_end

    return "".join(result_parts)


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

    # Normalise any XML-style <tool_call> blocks the model may have hallucinated
    normalised = _normalize_xml_tool_calls(raw)

    # First pass: extract and remove tool tags using a manual scanner.
    # We cannot use a simple [^}]* regex because parameter values (HTML, CSS, JS)
    # legitimately contain } characters.  Strategy: for each {tool: start found,
    # scan forward to find all }-terminated candidates; pick the last } that still
    # produces a parseable param block before the next {tool: start (or end of string).
    after_tools = _extract_tool_tags(normalised, tool_calls)

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
