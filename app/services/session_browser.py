from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.services.agent_memory import agent_data_dir, list_sessions

_SESSION_TITLE_PROMPT = "Summarise the following conversation into a title of 3 to 6 words."
_TITLE_MATCH_WINDOW_SECONDS = 15 * 60


def build_session_browser(agent_id: str) -> list[dict]:
    sessions = [_read_session_entry(agent_id, meta) for meta in list_sessions(agent_id)]
    sessions = [s for s in sessions if s and not s["is_internal"]]
    _apply_chatportal_titles(agent_id, sessions)

    grouped: dict[str, list[dict]] = {}
    for session in sessions:
        username = session["username"] or "Unknown"
        grouped.setdefault(username, []).append(_public_entry(session))

    out = []
    for username, items in grouped.items():
        items.sort(key=lambda item: item.get("started_at") or "", reverse=True)
        out.append({
            "username": username,
            "session_count": len(items),
            "sessions": items,
        })
    out.sort(key=lambda group: group["sessions"][0].get("started_at") or "", reverse=True)
    return out


def _read_session_entry(agent_id: str, meta: dict) -> dict | None:
    session_id = meta.get("session_id")
    if not session_id:
        return None

    conversation_path = agent_data_dir(agent_id) / "sessions" / session_id / "conversation.jsonl"
    first_event = _read_first_user_event(conversation_path)
    first_line = _first_line(first_event.get("text")) if first_event else None

    return {
        "session_id": session_id,
        "started_at": meta.get("started_at"),
        "username": meta.get("username"),
        "user_id": str(meta.get("user_id")) if meta.get("user_id") is not None else None,
        "first_line": first_line,
        "first_user_text": first_event.get("text") if first_event else None,
        "first_user_ts": first_event.get("ts") if first_event else None,
        "display_title": first_line or session_id,
        "title": None,
        "has_saved_title": False,
        "is_internal": bool(first_event and isinstance(first_event.get("text"), str) and first_event["text"].startswith(_SESSION_TITLE_PROMPT)),
    }


def _read_first_user_event(conversation_path: Path) -> dict | None:
    if not conversation_path.exists():
        return None

    for line in conversation_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("role") == "user" and isinstance(event.get("text"), str):
            return event
    return None


def _apply_chatportal_titles(agent_id: str, sessions: list[dict]) -> None:
    db_path = Path(__file__).resolve().parents[3] / "ChatPortal" / "data" / "chatportal.db"
    if not db_path.exists():
        return

    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
              c.id,
              c.title,
              c.created_at,
              (
                SELECT m.content
                FROM messages m
                WHERE m.conversation_id = c.id AND m.role = 'user'
                ORDER BY m.created_at ASC, m.id ASC
                LIMIT 1
              ) AS first_user_text
            FROM conversations c
            WHERE c.agent_id = ?
            """,
            (agent_id,),
        ).fetchall()
    except sqlite3.Error:
        return
    finally:
        if conn is not None:
            conn.close()

    by_first_text: dict[str, list[dict]] = {}
    for row in rows:
        first_user_text = row["first_user_text"]
        if not isinstance(first_user_text, str) or not first_user_text.strip():
            continue
        by_first_text.setdefault(first_user_text, []).append({
            "title": row["title"],
            "created_at": _parse_dt(row["created_at"]),
        })

    for session in sessions:
        first_user_text = session.get("first_user_text")
        if not first_user_text:
            continue
        candidates = by_first_text.get(first_user_text, [])
        if not candidates:
            continue

        session_ts = _parse_dt(session.get("first_user_ts")) or _parse_dt(session.get("started_at"))
        if not session_ts:
            continue

        best = None
        best_delta = None
        for candidate in candidates:
            created_at = candidate["created_at"]
            if not created_at:
                continue
            delta = abs((created_at - session_ts).total_seconds())
            if delta > _TITLE_MATCH_WINDOW_SECONDS:
                continue
            if best_delta is None or delta < best_delta:
                best = candidate
                best_delta = delta

        if not best:
            continue

        title = (best.get("title") or "").strip()
        if not title or title == "New Chat":
            continue

        session["title"] = title
        session["display_title"] = title
        session["has_saved_title"] = True


def _public_entry(session: dict) -> dict:
    return {
        "session_id": session["session_id"],
        "started_at": session.get("started_at"),
        "username": session.get("username"),
        "user_id": session.get("user_id"),
        "title": session.get("title"),
        "first_line": session.get("first_line"),
        "display_title": session["display_title"],
        "has_saved_title": session["has_saved_title"],
    }


def _first_line(text: str | None) -> str | None:
    if not text:
        return None
    first = text.strip().splitlines()[0].strip()
    return first[:140] if first else None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
