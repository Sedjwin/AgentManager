"""Parses LLM annotated output into clean text + annotation list with char positions."""
from __future__ import annotations

import re
from dataclasses import dataclass

# Matches {emotion:name}, {action:name} — tolerant of extra whitespace
_TAG_RE = re.compile(r"\{\s*(emotion|action)\s*:\s*([a-zA-Z0-9_]+)\s*\}")


@dataclass
class Annotation:
    char: int   # position in clean_text where this event fires
    type: str   # "emotion" or "action"
    value: str  # the name


def parse_response(raw: str) -> tuple[str, list[Annotation]]:
    """
    Strip {emotion:x} and {action:x} tags from raw LLM output.
    Returns (clean_text, annotations) where each annotation records
    its character position in the clean text.
    """
    annotations: list[Annotation] = []
    clean_parts: list[str] = []
    cursor = 0  # current position in clean_text being built

    for match in _TAG_RE.finditer(raw):
        # Text before this tag → add to clean output
        preceding = raw[cursor:match.start()]
        clean_parts.append(preceding)
        cursor = match.end()

        annotations.append(Annotation(
            char=sum(len(p) for p in clean_parts),
            type=match.group(1),
            value=match.group(2),
        ))

    # Remainder after last tag
    clean_parts.append(raw[cursor:])
    clean_text = "".join(clean_parts).strip()
    return clean_text, annotations
