"""AI generation endpoint — fills agent fields from personality_description."""

import json
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Agent, AgentResponse, apply_update, AgentUpdate
from app.services.aigateway import AIGatewayClient

router = APIRouter(prefix="/agents", tags=["Generate"])


class GenerateRequest(BaseModel):
    quality: str = "standard"   # "standard" | "premium"
    aspect: str = "all"         # "all" | "personality" | "avatar" | "system_prompt"


_FULL_PROMPT = """\
Given this agent description: "{description}"

Return a JSON object with these exact fields:
{{
  "system_prompt": "...(detailed AI persona instructions, 3-5 sentences)...",
  "traits": ["trait1", "trait2", "trait3"],
  "emotions": {{"idle": "neutral", "processing": "focused", "speaking": "engaged", "error": "irritated"}},
  "avatar_spec": {{
    "color_primary": "#hexcolor",
    "color_secondary": "#hexcolor",
    "color_accent": "#hexcolor",
    "face_theme": "mechanical|organic|abstract|minimal",
    "eye_style": "circular|angular|compound|visor",
    "mouth_style": "thin|wide|segmented|aperture",
    "idle_animation": "breathing|scanning|pulsing|flickering"
  }},
  "voice": "glados|atlas",
  "voice_speed": 1.0,
  "noise_scale": 0.333
}}
Return ONLY valid JSON, no explanation."""

_PERSONALITY_PROMPT = """\
Given this agent description: "{description}"

Return a JSON object with these fields:
{{
  "traits": ["trait1", "trait2", "trait3"],
  "emotions": {{"idle": "neutral", "processing": "focused", "speaking": "engaged", "error": "irritated"}}
}}
Return ONLY valid JSON, no explanation."""

_AVATAR_PROMPT = """\
Given this agent description: "{description}"

Return a JSON object with these exact fields:
{{
  "avatar_spec": {{
    "color_primary": "#hexcolor",
    "color_secondary": "#hexcolor",
    "color_accent": "#hexcolor",
    "face_theme": "mechanical|organic|abstract|minimal",
    "eye_style": "circular|angular|compound|visor",
    "mouth_style": "thin|wide|segmented|aperture",
    "idle_animation": "breathing|scanning|pulsing|flickering"
  }}
}}
Return ONLY valid JSON, no explanation."""

_SYSTEM_PROMPT_PROMPT = """\
Given this agent description: "{description}"

Return a JSON object with this exact field:
{{
  "system_prompt": "...(detailed AI persona instructions, 3-5 sentences)..."
}}
Return ONLY valid JSON, no explanation."""

_ASPECT_PROMPTS = {
    "all":           _FULL_PROMPT,
    "personality":   _PERSONALITY_PROMPT,
    "avatar":        _AVATAR_PROMPT,
    "system_prompt": _SYSTEM_PROMPT_PROMPT,
}


def _extract_json(text: str) -> dict:
    """Extract a JSON object from LLM response text (strips markdown code fences)."""
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Strip code fences
    fenced = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    fenced = re.sub(r"```\s*$", "", fenced, flags=re.MULTILINE).strip()
    try:
        return json.loads(fenced)
    except json.JSONDecodeError:
        pass
    # Try to extract first {...} block
    match = re.search(r"\{[\s\S]+\}", text)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}")


@router.post("/{agent_id}/generate")
async def generate(
    agent_id: int,
    body: GenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate agent fields using AI based on personality_description."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    if not agent.gateway_token:
        raise HTTPException(status_code=422, detail="Agent has no gateway_token configured")

    description = agent.personality_description or agent.bio or agent.name
    aspect = body.aspect if body.aspect in _ASPECT_PROMPTS else "all"
    prompt_template = _ASPECT_PROMPTS[aspect]
    prompt_text = prompt_template.format(description=description)

    prefer_premium = body.quality == "premium"
    gw_client = AIGatewayClient(agent.gateway_token)

    messages = [{"role": "user", "content": prompt_text}]
    try:
        gw_response = await gw_client.complete(
            messages=messages,
            prefer_premium=prefer_premium,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AIGateway error: {exc}")

    choice = gw_response.get("choices", [{}])[0]
    raw_text = choice.get("message", {}).get("content", "")

    try:
        generated = _extract_json(raw_text)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=f"Failed to parse AI response: {exc}")

    # Persist the generated fields back to the agent
    update_schema = AgentUpdate(**{k: v for k, v in generated.items() if hasattr(AgentUpdate, k)})
    apply_update(agent, update_schema)
    await db.commit()
    await db.refresh(agent)

    return generated
