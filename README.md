# AgentManager

Agent orchestration service for the AI infrastructure stack. Manages agent definitions, runs session-based STT→LLM→TTS pipelines, assembles emotion/action/viseme timelines for expressive voice interactions, and integrates with ToolGateway for agent tool use.

**Ports:** `8003` (internal) / `13374` (external, HTTPS via Caddy)

---

## Overview

- Agent CRUD — functional (text-only) or interaction (voice + personality profile) agents
- Session-based conversation model with in-memory history
- Orchestrates STT (VoiceService) → LLM (AIGateway) → TTS (VoiceService) per turn
- Parses `{emotion:name}` / `{action:name}` / `{tool:name}` tags from LLM output
- Assembles `timeline[]` merging emotion events, action events, and visemes with millisecond timestamps
- Tool use — per-agent tool grants fetched from ToolGateway; SkillMD cached on agent and injected into system prompt at inference
- File-based session logging (audio in/out + conversation JSONL)
- Seeded agents: **GlaDOS** and **TARS**

---

## Configuration

Set via environment variables or `.env` file:

| Variable              | Default                                        | Description                          |
|-----------------------|------------------------------------------------|--------------------------------------|
| `AIGATEWAY_URL`       | `http://localhost:8001`                        | AIGateway base URL                   |
| `VOICESERVICE_URL`    | `http://localhost:8002`                        | VoiceService base URL                |
| `DATABASE_URL`        | `sqlite+aiosqlite:///./data/agentmanager.db`   | SQLite connection string             |
| `USERMANAGER_URL`     | `http://localhost:8005`                        | UserManager base URL                 |
| `USERMANAGER_SERVICE_KEY` | `change-me-service-key`                  | Service key for internal UM calls    |
| `TOOLGATEWAY_URL`     | `http://localhost:8006`                        | ToolGateway base URL                 |

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

### Tool Use (any agent type)
- Toggle `tool_use_enabled` on any agent (functional or interaction)
- Available tools come from grants in ToolGateway for the agent's principal
- Enabling a tool caches its SkillMD (markdown instructions) on the agent record
- At inference time, a tool preamble + each SkillMD is appended to the system prompt
- LLM emits `{tool:name}` inline when it needs a tool; the pipeline calls ToolGateway `/api/execute`, injects the result, and asks the LLM for a final response

---

## API Reference

### Health & Discovery

| Method | Path      | Auth | Description               |
|--------|-----------|------|---------------------------|
| GET    | `/health` | None | Service health check      |
| GET    | `/voices` | None | Proxy to VoiceService `/voices` — list available TTS voices |

---

### Agent Management

| Method | Path                          | Auth | Description                          |
|--------|-------------------------------|------|--------------------------------------|
| GET    | `/agents`                     | None | List all agents                      |
| POST   | `/agents`                     | None | Create agent (201)                   |
| GET    | `/agents/{agent_id}`          | None | Get agent by ID                      |
| PUT    | `/agents/{agent_id}`          | None | Update agent (all fields optional)   |
| PUT    | `/agents/{agent_id}/profile`  | None | Replace agent profile only           |
| DELETE | `/agents/{agent_id}`          | None | Delete agent (204)                   |
| GET    | `/agents/{agent_id}/tools`    | None | List tools granted to this agent (fetched from ToolGateway) |
| PUT    | `/agents/{agent_id}/tools`    | None | Set tool_use_enabled + cache SkillMDs for selected tools |

**Agent fields:**

| Field               | Type   | Description                                                       |
|---------------------|--------|-------------------------------------------------------------------|
| `name`              | str    | Unique display name                                               |
| `ai_gateway_token`  | str    | Bearer token for AIGateway LLM calls                             |
| `system_prompt`     | str    | Base LLM system message                                           |
| `voice_enabled`     | bool   | Enable TTS synthesis (default false)                              |
| `voice_config`      | dict   | `{"voice_id": "glados"}` — speed/pitch controlled in VoiceService |
| `profile`           | dict   | Interaction agent profile (appearance, emotions, actions, idle)   |
| `tool_use_enabled`  | bool   | Whether tool calling is active for this agent                     |
| `enabled_tools`     | list   | Names of currently enabled tools (read-only — set via PUT /tools) |

**`AgentOut` response:**

```json
{
  "agent_id": "uuid",
  "name": "GlaDOS",
  "system_prompt": "...",
  "voice_enabled": true,
  "voice_config": {"voice_id": "glados"},
  "profile": { ... },
  "has_profile": true,
  "um_user_id": 42,
  "um_api_key": "...",
  "tool_use_enabled": true,
  "enabled_tools": ["get-time"],
  "created_at": "2026-01-01T00:00:00",
  "updated_at": "2026-01-01T00:00:00"
}
```

Note: `ai_gateway_token` is never returned. On edit, omit the field to keep the existing token.

**`PUT /agents/{id}/tools` request:**
```json
{
  "tool_use_enabled": true,
  "enabled_tools": ["get-time"]
}
```

This fetches SkillMD for each named tool from ToolGateway and caches it on the agent. SkillMD is only refreshed when tools are re-saved via this endpoint.

---

### Session Lifecycle

Sessions are in-memory and ephemeral (cleared on service restart).

| Method | Path                                | Auth | Description                                      |
|--------|-------------------------------------|------|--------------------------------------------------|
| POST   | `/agents/{agent_id}/session`        | None | Start session → returns `SessionOut`             |
| DELETE | `/sessions/{session_id}`            | None | End session (204)                                |
| POST   | `/sessions/{session_id}/history`    | None | Pre-load prior messages into session history (204) |
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

**`POST /sessions/{id}/history`** — pre-populates the session's in-memory history without triggering a live response. Used by ChatPortal to replay stored conversation messages when resuming after a restart. Replaces any existing history.

```json
{
  "messages": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Good morning, test subject."}
  ]
}
```

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
  "reasoning": "The user greeted me. I should respond in character...",
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

`transcript` is present only when input was audio. `audio` is null for functional agents or when `voice_enabled` is false. `timeline` `t` values are milliseconds from audio start. `reasoning` is the model's chain-of-thought from thinking models (e.g. DeepSeek R1, Claude extended thinking) — `null` for standard models. In streaming mode it is attached to the first chunk only.

---

## Annotation Tags

LLM output uses **curly-brace** tags (stripped from `text`, merged into `timeline[]` or processed as tool calls):

```
{emotion:name}   — set agent emotion (e.g. {emotion:disdainful})
{action:name}    — trigger one-time action (e.g. {action:slow_blink})
{tool:name}      — call a tool (e.g. {tool:get-time}); result injected and LLM re-prompted
```

Emotion and action names are per-agent (defined in the profile) and injected into the system prompt automatically. Tool names come from the agent's enabled tools list.

**Timeline timestamp mapping:** `t_ms = (char_position / total_chars) * duration_ms`

Visemes come directly from VoiceService with `offset_ms`.

---

## Tool Call Flow

When `tool_use_enabled` is true, the system prompt is augmented with:
1. A tool preamble explaining the `{tool:name}` syntax and gateway denial behaviour
2. The SkillMD for each enabled tool (cached from ToolGateway at configuration time)

At runtime, when the LLM emits `{tool:name}`:
1. Pipeline detects the tag in the first-pass response
2. Calls `POST /api/execute` on ToolGateway (using the agent's `um_api_key`)
3. Injects the tool result into the conversation
4. LLM produces the final user-facing response

---

## Seeded Agents

Both are seeded idempotently on startup.

### GlaDOS — Aperture Science AI
- **Token:** `34e93070d8a934d841322a0418936ab8fc9b7658f8c52142d7fd0648b639c1d5`
- **Voice:** `glados`
- **Personality:** Highly intelligent, condescending, dry dark humour. Treats humans as test subjects.
- **Emotions:** `disdainful`, `satisfied`, `curious`, `irritated`, `sinister_pleased`, `bored`, `mock_concern`
- **Actions:** `slow_blink`, `eye_narrow`, `head_tilt`, `scan`, `emphasis`

### TARS — Interstellar Tactical AI
- **Voice:** `atlas`
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

| Column              | Type     | Notes                                              |
|---------------------|----------|----------------------------------------------------|
| `agent_id`          | str PK   | UUID                                               |
| `name`              | str      | Unique                                             |
| `ai_gateway_token`  | str      | Bearer token for LLM (never returned in responses) |
| `system_prompt`     | str      | Base system message                                |
| `voice_enabled`     | bool     |                                                    |
| `voice_config`      | str/JSON | Nullable; `{"voice_id": "glados"}`                 |
| `profile`           | str/JSON | Nullable; full interaction profile                 |
| `um_user_id`        | int      | Nullable; principal ID in UserManager              |
| `um_api_key`        | str      | Nullable; API key for UserManager/ToolGateway auth |
| `tool_use_enabled`  | bool     | Default false                                      |
| `enabled_tools`     | str/JSON | Default `[]`; `[{"name": "...", "skill_md": "..."}]` |
| `created_at`        | datetime |                                                    |
| `updated_at`        | datetime | Auto-updated                                       |

New columns (`um_user_id`, `um_api_key`, `tool_use_enabled`, `enabled_tools`) are added via `migrate_db()` on startup — safe to run against existing databases.

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
