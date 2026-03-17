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
voice, colours, and behaviours should feel like one unified character.

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
- system_prompt should be 2-4 sentences written in first person, defining role + constraints.
- traits: 3-5 single words or short phrases (e.g. "sardonic", "methodical", "darkly witty").
- emotions: one word each for idle/processing/speaking/error states.
- avatar colours should match the personality (e.g. cold=cyan/blue, warm=amber/orange, sinister=red/purple).
- voice: "glados" (robotic, female, dry) or "atlas" (professional, male, neutral).
- voice_speed: 0.8–1.3. noise_scale/noise_w: 0.1–0.8.
- idle_animation: "scanning" for alert/robotic, "breathing" for organic/calm, "pulsing" for energetic, "flickering" for unstable.

Return ONLY valid JSON with exactly these fields — no explanation, no markdown:
{{
  "personality_description": "...",
  "system_prompt": "...",
  "traits": ["...", "..."],
  "emotions": {{"idle": "...", "processing": "...", "speaking": "...", "error": "..."}},
  "avatar_spec": {{
    "color_primary": "#rrggbb",
    "color_secondary": "#rrggbb",
    "color_accent": "#rrggbb",
    "face_theme": "mechanical|organic|abstract|minimal",
    "eye_style": "angular|circular|compound|visor",
    "mouth_style": "thin|wide|segmented|aperture",
    "idle_animation": "breathing|scanning|pulsing|flickering"
  }},
  "voice": "glados|atlas",
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
