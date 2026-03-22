# AgentManager

Agent orchestration service for the AI infrastructure stack. Manages agent definitions, runs session-based STT→LLM→TTS pipelines, and assembles emotion/action/viseme timelines for expressive voice interactions.

**Ports:** `8003` (internal) / `13374` (external, HTTPS via Caddy)

---

## Overview

- Agent CRUD — functional (text-only) or interaction (voice + personality profile) agents
- Session-based conversation model with in-memory history
- Orchestrates STT (VoiceService) → LLM (AIGateway) → TTS (VoiceService) per turn
- Parses `{emotion:name}` / `{action:name}` tags from LLM output
- Assembles `timeline[]` merging emotion events, action events, and visemes with millisecond timestamps
- File-based session logging (audio in/out + conversation JSONL)
- Seeded agents: **GlaDOS** and **TARS**

---

## Configuration

Set via environment variables or `.env` file:

| Variable          | Default                                        | Description                       |
|-------------------|------------------------------------------------|-----------------------------------|
| `AIGATEWAY_URL`   | `http://localhost:8001`                        | AIGateway base URL                |
| `VOICESERVICE_URL`| `http://localhost:8002`                        | VoiceService base URL             |
| `DATABASE_URL`    | `sqlite+aiosqlite:///./data/agentmanager.db`   | SQLite connection string          |

---

## Agent Types

### Functional
- No `profile` field
- System prompt used as-is — no annotation instructions injected
- Voice optional. No emotional expression.
- Session type returned: `"functional"`

### Interaction
- Has a `profile` JSON block defining appearance, per-agent emotions, actions, and idle behaviour
- System prompt is automatically augmented with an annotation block listing the agent's emotions and actions
- LLM is expected to embed `{emotion:name}` and `{action:name}` tags in its responses
- Timeline assembled from tag positions + TTS visemes
- Session type returned: `"interaction"`

---

## API Reference

### Health & Discovery

| Method | Path      | Auth | Description               |
|--------|-----------|------|---------------------------|
| GET    | `/health` | None | Service health check      |
| GET    | `/voices` | None | Proxy to VoiceService `/voices` — list available TTS voices |

---

### Agent Management

| Method | Path                        | Auth | Description                     |
|--------|-----------------------------|------|---------------------------------|
| GET    | `/agents`                   | None | List all agents                 |
| POST   | `/agents`                   | None | Create agent (201)              |
| GET    | `/agents/{agent_id}`        | None | Get agent by ID                 |
| PUT    | `/agents/{agent_id}`        | None | Update agent (all fields optional) |
| PUT    | `/agents/{agent_id}/profile`| None | Replace agent profile only      |
| DELETE | `/agents/{agent_id}`        | None | Delete agent (204)              |

**Agent fields:**

| Field             | Type   | Description                                                       |
|-------------------|--------|-------------------------------------------------------------------|
| `name`            | str    | Unique display name                                               |
| `ai_gateway_token`| str    | Bearer token for AIGateway LLM calls                             |
| `system_prompt`   | str    | Base LLM system message                                           |
| `voice_enabled`   | bool   | Enable TTS synthesis (default false)                              |
| `voice_config`    | dict   | `{"voice_id": "glados", "base_pitch": 0.55, "base_speed": 0.42}` |
| `profile`         | dict   | Interaction agent profile (appearance, emotions, actions, idle)   |

**`AgentOut` response:**

```json
{
  "agent_id": "uuid",
  "name": "GlaDOS",
  "system_prompt": "...",
  "voice_enabled": true,
  "voice_config": {"voice_id": "glados", "base_pitch": 0.55, "base_speed": 0.42},
  "profile": { ... },
  "has_profile": true,
  "created_at": "2026-01-01T00:00:00",
  "updated_at": "2026-01-01T00:00:00"
}
```

---

### Session Lifecycle

Sessions are in-memory and ephemeral (cleared on service restart).

| Method | Path                                | Auth | Description                                      |
|--------|-------------------------------------|------|--------------------------------------------------|
| POST   | `/agents/{agent_id}/session`        | None | Start session → returns `SessionOut`             |
| DELETE | `/sessions/{session_id}`            | None | End session (204)                                |
| POST   | `/sessions/{session_id}/interrupt`  | None | Cancel in-flight request (204)                   |

**Start session request (optional):**
```json
{ "device_id": "phone_1", "capabilities": {"audio": true} }
```

Optional headers: `X-User-Id`, `X-Username` (for session logging).

**`SessionOut` response:**
```json
{
  "session_id": "uuid",
  "agent_id": "uuid",
  "type": "interaction",
  "profile": { ... }
}
```

`type` is `"interaction"` if the agent has a profile, `"functional"` otherwise.

---

### Interaction

| Method | Path                             | Auth | Description                                      |
|--------|----------------------------------|------|--------------------------------------------------|
| POST   | `/sessions/{session_id}/message` | None | Send text → `AgentResponse`                      |
| POST   | `/sessions/{session_id}/audio`   | None | Upload WAV → STT + `AgentResponse`               |
| POST   | `/sessions/{session_id}/stream`  | None | Send text → SSE stream of `AgentResponse` chunks |
| GET    | `/sessions/{session_id}/stream`  | None | Same as above but via query param `?text=...`    |

**Text message request:**
```json
{
  "text": "Hello there.",
  "history": []
}
```

**Audio request:** `multipart/form-data` with field `audio` (WAV file).

**`AgentResponse`:**
```json
{
  "session_id": "uuid",
  "text": "I am functioning optimally, test subject.",
  "transcript": "Hello there.",
  "audio": "<base64 WAV>",
  "duration_ms": 2400,
  "sample_rate": 22050,
  "buffer_bytes": 22050,
  "timeline": [
    {"t": 0,   "type": "emotion", "value": "disdainful"},
    {"t": 80,  "type": "viseme",  "value": 17},
    {"t": 1200,"type": "action",  "value": "slow_blink"}
  ],
  "chunk_index": 0,
  "is_final": true
}
```

`transcript` is present only when input was audio. `audio` is null for functional agents or when `voice_enabled` is false. `timeline` `t` values are milliseconds from audio start.

---

## Annotation Tags

LLM output uses **curly-brace** tags (stripped from `text`, merged into `timeline[]`):

```
{emotion:name}   — set agent emotion (e.g. {emotion:disdainful})
{action:name}    — trigger one-time action (e.g. {action:slow_blink})
```

The available emotion and action names are per-agent (defined in the profile). They are injected into the system prompt automatically so the LLM knows the vocabulary.

**Timeline timestamp mapping:** `t_ms = (char_position / total_chars) * duration_ms`

Visemes come directly from VoiceService with `offset_ms`.

---

## Seeded Agents

Both are seeded idempotently on startup.

### GlaDOS — Aperture Science AI
- **Token:** `34e93070d8a934d841322a0418936ab8fc9b7658f8c52142d7fd0648b639c1d5`
- **Voice:** `glados` · pitch 0.55 · speed 0.42 (slow, deliberate)
- **Personality:** Highly intelligent, condescending, dry dark humour. Treats humans as test subjects.
- **Emotions:** `disdainful`, `satisfied`, `curious`, `irritated`, `sinister_pleased`, `bored`, `mock_concern`
- **Actions:** `slow_blink`, `eye_narrow`, `head_tilt`, `scan`, `emphasis`

### TARS — Interstellar Tactical AI
- **Voice:** `atlas` · pitch 0.3 · speed 0.48
- **Personality:** USMC tactical robot. Dry deadpan humour (75%). Honest (90%). Short, efficient sentences.
- **Emotions:** `precise`, `humorous`, `loyal`, `concerned`, `calculating`, `determined`
- **Actions:** `data_scan`, `acknowledgment`, `emphasis`, `standby`

---

## Session Logging

Each session logs to disk at `data/agents/{agent_id}/sessions/{session_id}/`:

```
session.json         — metadata (agent, user, device, started_at)
conversation.jsonl   — one JSON line per event (user input + assistant output)
audio_in/            — user audio uploads (turn_NNNN_user.wav)
audio_out/           — TTS output per chunk (turn_NNNN_chunk_NNN.wav)
```

---

## Database Models

### Agent

| Column            | Type     | Notes                 |
|-------------------|----------|-----------------------|
| `agent_id`        | str PK   | UUID                  |
| `name`            | str      | Unique                |
| `ai_gateway_token`| str      | Bearer token for LLM  |
| `system_prompt`   | str      | Base system message   |
| `voice_enabled`   | bool     |                       |
| `voice_config`    | str/JSON | Nullable              |
| `profile`         | str/JSON | Nullable              |
| `created_at`      | datetime |                       |
| `updated_at`      | datetime | Auto-updated          |

---

## Running

```bash
cd AgentManager
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8003

# production
sudo systemctl start agentmanager
sudo journalctl -u agentmanager -f
```
