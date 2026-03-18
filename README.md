# AgentManager

Agent lifecycle and orchestration service. Manages AI agent identities (personality, voice, system prompt, avatar) and orchestrates conversations through AIGateway's LLM and VoiceService's STT/TTS pipeline.

**Ports:** `8003` (internal) / `13374` (external, HTTPS via nginx)

---

## Overview

- Create and configure agents with full personality profiles (bio, traits, emotions, avatar)
- Each agent has its own gateway token and voice settings
- Chat endpoint handles text and voice input, routes through AIGateway → VoiceService
- AI-powered agent generation: auto-fills system prompt, personality, and avatar from a name
- MCP tool integration support per agent
- Syncs agent records to AIGateway on create/update/delete

---

## Configuration

Set via environment variables or `.env` file:

| Variable               | Default                    | Description                                           |
|------------------------|----------------------------|-------------------------------------------------------|
| `HOST`                 | `0.0.0.0`                  | Listen address                                        |
| `PORT`                 | `13374`                    | Listen port                                           |
| `AIGATEWAY_URL`        | `http://localhost:8001`    | AIGateway base URL                                    |
| `VOICESERVICE_URL`     | `http://localhost:8002`    | VoiceService base URL                                 |
| `SYSTEM_GATEWAY_KEY`   | _(empty)_                  | Bearer token for AI generation calls to AIGateway     |
| `AIGATEWAY_ADMIN_KEY`  | _(empty)_                  | `X-Admin-Key` for AIGateway admin endpoints           |

---

## API Reference

### Agents — CRUD (`/agents`)

| Method | Path                              | Description                                         |
|--------|-----------------------------------|-----------------------------------------------------|
| GET    | `/agents`                         | List all agents                                     |
| POST   | `/agents`                         | Create agent                                        |
| GET    | `/agents/{id}`                    | Get agent details                                   |
| PUT    | `/agents/{id}`                    | Update agent (syncs to AIGateway)                   |
| DELETE | `/agents/{id}`                    | Delete agent (deregisters from AIGateway)           |
| POST   | `/agents/{id}/regenerate-key`     | Generate new gateway API key                        |
| POST   | `/agents/{id}/register-gateway`   | Re-register agent with AIGateway                    |

**Create/update body (`AgentCreate` / `AgentUpdate`):**

| Field                    | Type    | Description                                          |
|--------------------------|---------|------------------------------------------------------|
| `name`                   | string  | Display name (unique)                                |
| `bio`                    | string  | Short biography / character background               |
| `avatar_spec`            | JSON    | Avatar configuration (colors, shape, expressions)   |
| `system_prompt`          | string  | LLM system message                                   |
| `gateway_token`          | string  | AIGateway API key (auto-created if omitted)          |
| `default_model`          | string  | Preferred LLM model ID (empty = gateway default)     |
| `smart_routing`          | bool    | Enable AIGateway smart routing                       |
| `mcp_tools`              | JSON    | MCP tool definitions                                 |
| `accepts_attachments`    | bool    | Whether agent accepts file attachments               |
| `accepts_images`         | bool    | Whether agent accepts images                         |
| `enabled`                | bool    | Whether agent is active                              |
| `demo_playground_enabled`| bool    | Show agent in demo/playground                        |
| `voice`                  | string  | `glados` or `atlas`                                  |
| `voice_speed`            | float   | TTS speed multiplier                                 |
| `noise_scale`            | float   | GLaDOS noise_scale (pitch variance)                  |
| `noise_w`                | float   | GLaDOS noise_w (duration variance)                   |
| `personality_description`| string  | Free-text personality overview                       |
| `traits`                 | JSON    | List of personality trait strings                    |
| `emotions`               | JSON    | Emotion-to-TTS-param mapping                         |

---

### Chat (`/agents/{id}/chat`)

| Method | Path                  | Auth | Description                                 |
|--------|-----------------------|------|---------------------------------------------|
| POST   | `/agents/{id}/chat`   | None | Full conversation turn (text or voice input) |

**Request — multipart/form-data:**

| Field     | Type   | Description                                          |
|-----------|--------|------------------------------------------------------|
| `text`    | string | User text input (optional if `audio` provided)       |
| `audio`   | file   | WAV audio file (optional if `text` provided)         |
| `history` | JSON   | Conversation history array (optional)                |

**History format:**
```json
[
  {"role": "user", "content": "Hello"},
  {"role": "assistant", "content": "Hi there!"}
]
```

**Response:**
```json
{
  "transcript": "What's the weather?",
  "response_text": "[NEUTRAL] I don't have access to live weather data.",
  "clean_text": "I don't have access to live weather data.",
  "emotion": "neutral",
  "actions": [{"type": "neutral", "value": "neutral"}],
  "audio": "<base64-wav>",
  "visemes": [{"phoneme": "AY", "duration_ms": 80}, ...],
  "audio_duration_ms": 2100,
  "model_used": "qwen2.5:1.5b",
  "t_stt_ms": 210,
  "t_llm_ms": 380,
  "t_tts_ms": 290,
  "pipeline_ms": 880
}
```

---

### AI Generation (`/agents/{id}/generate`)

| Method | Path                    | Auth | Description                                        |
|--------|-------------------------|------|----------------------------------------------------|
| POST   | `/agents/{id}/generate` | None | Auto-fill agent personality fields using an LLM   |

**Request:**
```json
{ "quality": "standard" }
```

`quality`: `standard` (fast/local) or `premium` (high-quality/cloud)

**Response:**
```json
{
  "generated": {
    "personality_description": "...",
    "system_prompt": "...",
    "traits": ["curious", "direct", "technical"],
    "emotions": { "happy": {...}, "angry": {...} },
    "avatar_spec": {...},
    "voice": "glados",
    "noise_scale": 0.4
  },
  "model_used": "qwen2.5:7b",
  "agent": { ...updated agent record... }
}
```

The agent record is updated in-place with the generated fields.

---

### Setup Helpers

| Method | Path             | Auth | Description                                |
|--------|------------------|------|--------------------------------------------|
| GET    | `/setup/models`  | None | Proxy AIGateway model list for UI dropdowns |
| GET    | `/health`        | None | Service health check                        |

---

## Database Model (Agent)

| Column                    | Type     | Notes                                  |
|---------------------------|----------|----------------------------------------|
| `id`                      | int PK   |                                        |
| `name`                    | str      | Unique                                 |
| `bio`                     | str      | Nullable                               |
| `avatar_spec`             | JSON     | Nullable                               |
| `system_prompt`           | str      | Nullable                               |
| `gateway_token`           | str      | AIGateway API key                      |
| `default_model`           | str      | Nullable                               |
| `smart_routing`           | bool     | Default false                          |
| `mcp_tools`               | JSON     | Nullable                               |
| `accepts_attachments`     | bool     | Default false                          |
| `accepts_images`          | bool     | Default false                          |
| `enabled`                 | bool     | Default true                           |
| `demo_playground_enabled` | bool     | Default false                          |
| `voice`                   | str      | `glados` / `atlas`                     |
| `voice_speed`             | float    | Default 1.0                            |
| `noise_scale`             | float    | Default 0.667                          |
| `noise_w`                 | float    | Default 0.8                            |
| `personality_description` | str      | Nullable                               |
| `traits`                  | JSON     | Nullable                               |
| `emotions`                | JSON     | Nullable                               |
| `created_at`              | datetime |                                        |
| `updated_at`              | datetime |                                        |

---

## Architecture

```
Dashboard Playground
        │
        ▼
POST /agents/{id}/chat   (multipart: text or audio + history)
        │
        ├─► VoiceService /stt  (if audio provided)
        │        → transcript
        │
        ├─► AIGateway /v1/chat/completions
        │        → response_text (may contain [EMOTION] / action tags)
        │
        ├─► Tag parser
        │        → emotion, clean_text, actions[]
        │
        └─► VoiceService /tts
                 → audio (base64), visemes[], duration_ms
```

---

## Running

```bash
cd AgentManager
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8003
```
