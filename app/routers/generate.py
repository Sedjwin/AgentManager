"""AI generation endpoint — fills agent fields from personality_description."""

import json
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Agent, AgentResponse, apply_update, AgentUpdate
from app.services.aigateway import AIGatewayClient

router = APIRouter(prefix="/agents", tags=["Generate"])


class GenerateRequest(BaseModel):
    quality: str = "standard"   # "standard" | "premium"


_PROMPT = """\
You are configuring an AI agent. Read all current settings carefully, then generate \
improved coherent values for every field. Make everything consistent — name, personality, \
voice, colours, DNA traits, and emotional states should feel like one unified character.

=== CURRENT SETTINGS ===
Name:                   {name}
Bio:                    {bio}
Personality description:{personality_description}
System prompt:          {system_prompt}
Voice:                  {voice}
Voice speed:            {voice_speed}
Noise scale:            {noise_scale}
Noise W:                {noise_w}
Traits:                 {traits}
Emotions:               {emotions}
Avatar spec:            {avatar_spec}
========================

Rules:
- Keep the name as-is.
- If personality_description is vague or empty, invent a coherent one based on name/bio.
- system_prompt: 2-4 sentences in first person, defining role and constraints. Append one sentence listing the agent's emotion tags like: "Express state using tags: [CALM] [CURIOUS] [DELIGHTED]"
- traits: 3-6 single words or short phrases (e.g. "sardonic", "methodical", "darkly witty").
- emotions: a free-form dictionary of 3-6 named emotional states unique to this character.
  Each emotion maps to performance parameters:
    energy        0.0–1.0  (0=lethargic, 1=frantic)
    valence       -1.0–1.0 (negative=unhappy, positive=happy)
    eye_openness  0.0–1.0  (0=half-closed, 1=wide open)
    mouth_curve   -1.0–1.0 (negative=frown, positive=smile)
  Choose emotion names that suit the character (e.g. for GLaDOS: "sardonic", "triumphant", "disappointed").
- avatar colours should match personality (cold=cyan/blue, warm=amber/orange, sinister=red/purple, mechanical=gray/white).
- avatar_spec.dna: personality DNA (4 floats 0.0–1.0):
    energy       overall animation pace and intensity
    warmth       colour temperature and ambient glow warmth
    confidence   eye scale and assertiveness
    erraticness  jitter and instability in idle animation
- voice options: "glados" (robotic female, dry humour), "atlas" (professional male, neutral),
  "jarvis" (warm British male, sophisticated butler), "tars" (direct US male, efficient wit).
- voice_speed: 0.8–1.3. noise_scale/noise_w: 0.1–0.8 (GLaDOS only; use 0.333 for others).
- idle_animation: "scanning" (alert/robotic), "breathing" (organic/calm), "pulsing" (energetic), "flickering" (unstable).

Return ONLY valid JSON with exactly these fields — no explanation, no markdown:
{{
  "personality_description": "...",
  "system_prompt": "...",
  "traits": ["...", "..."],
  "emotions": {{
    "emotion_name": {{"energy": 0.5, "valence": 0.0, "eye_openness": 0.7, "mouth_curve": 0.0}},
    "emotion_name2": {{"energy": 0.8, "valence": 0.7, "eye_openness": 1.0, "mouth_curve": 0.6}}
  }},
  "avatar_spec": {{
    "color_primary": "#rrggbb",
    "color_secondary": "#rrggbb",
    "color_accent": "#rrggbb",
    "face_theme": "mechanical|organic|abstract|minimal",
    "eye_style": "angular|circular|compound|visor",
    "mouth_style": "thin|wide|segmented|aperture",
    "idle_animation": "breathing|scanning|pulsing|flickering",
    "dna": {{
      "energy": 0.5,
      "warmth": 0.5,
      "confidence": 0.7,
      "erraticness": 0.1
    }}
  }},
  "voice": "glados|atlas|jarvis|tars",
  "voice_speed": 1.0,
  "noise_scale": 0.333,
  "noise_w": 0.333
}}\
"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fenced = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    fenced = re.sub(r"```\s*$", "", fenced, flags=re.MULTILINE).strip()
    try:
        return json.loads(fenced)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]+\}", text)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}")


def _fmt(v) -> str:
    """Safely stringify a field that may be a JSON string or a native object."""
    if v is None:
        return "(not set)"
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    # May be a JSON-encoded string stored in SQLite TEXT column
    try:
        parsed = json.loads(v)
        return json.dumps(parsed)
    except (json.JSONDecodeError, TypeError):
        return str(v) or "(not set)"


@router.post("/{agent_id}/generate")
async def generate(
    agent_id: int,
    body: GenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Use AI to improve and complete all agent fields.
    Reads the full current agent state as context so the output is coherent.
    """
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    # Use the system key (admin-level, smart routing) for generation calls.
    # Falls back to the agent's own key if no system key is configured.
    key = settings.system_gateway_key or agent.gateway_token
    if not key:
        raise HTTPException(status_code=422, detail="No system_gateway_key configured and agent has no gateway_token.")

    prompt_text = _PROMPT.format(
        name=agent.name or "(not set)",
        bio=agent.bio or "(not set)",
        personality_description=agent.personality_description or "(not set)",
        system_prompt=agent.system_prompt or "(not set)",
        voice=agent.voice or "glados",
        voice_speed=agent.voice_speed or 1.0,
        noise_scale=agent.noise_scale or 0.333,
        noise_w=agent.noise_w or 0.333,
        traits=_fmt(agent.traits),
        emotions=_fmt(agent.emotions),
        avatar_spec=_fmt(agent.avatar_spec),
    )

    gw_client = AIGatewayClient(key)
    try:
        gw_response = await gw_client.complete(
            messages=[{"role": "user", "content": prompt_text}],
            prefer_premium=(body.quality == "premium"),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AIGateway error: {exc}")

    raw_text = gw_response.get("choices", [{}])[0].get("message", {}).get("content", "")

    try:
        generated = _extract_json(raw_text)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=f"Failed to parse AI response: {exc}\nRaw: {raw_text[:300]}")

    update_schema = AgentUpdate(**{k: v for k, v in generated.items() if k in AgentUpdate.model_fields})
    apply_update(agent, update_schema)
    await db.commit()
    await db.refresh(agent)

    return {
        "generated": generated,
        "model_used": gw_response.get("model"),
        "agent": AgentResponse.from_orm_agent(agent).model_dump(mode="json"),
    }
