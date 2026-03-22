"""Agent CRUD endpoints."""
from __future__ import annotations

import json
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Agent
from app.schemas import AgentCreate, AgentListItem, AgentOut, AgentUpdate

router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger(__name__)


def _agent_to_out(agent: Agent) -> AgentOut:
    return AgentOut(
        agent_id=agent.agent_id,
        name=agent.name,
        system_prompt=agent.system_prompt,
        voice_enabled=agent.voice_enabled,
        voice_config=json.loads(agent.voice_config) if agent.voice_config else None,
        profile=json.loads(agent.profile) if agent.profile else None,
        has_profile=agent.profile is not None,
        um_user_id=agent.um_user_id,
        um_api_key=agent.um_api_key,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def _agent_to_list_item(agent: Agent) -> AgentListItem:
    return AgentListItem(
        agent_id=agent.agent_id,
        name=agent.name,
        voice_enabled=agent.voice_enabled,
        has_profile=agent.profile is not None,
        system_prompt=agent.system_prompt,
        profile=json.loads(agent.profile) if agent.profile else None,
        voice_config=json.loads(agent.voice_config) if agent.voice_config else None,
    )


async def _register_with_usermanager(agent_id: str, display_name: str) -> tuple[int | None, str | None]:
    """Register an agent principal in UserManager. Returns (user_id, api_key) or (None, None)."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{settings.usermanager_url}/internal/principals",
                headers={"X-Service-Key": settings.usermanager_service_key},
                json={"username": f"agent_{agent_id}", "display_name": display_name},
                timeout=5.0,
            )
            if r.status_code == 201:
                data = r.json()
                return data["user_id"], data["api_key"]
    except Exception as exc:
        logger.warning("Failed to register agent with UserManager: %s", exc)
    return None, None


async def _deregister_from_usermanager(um_user_id: int) -> None:
    """Remove an agent principal from UserManager."""
    try:
        async with httpx.AsyncClient() as client:
            await client.delete(
                f"{settings.usermanager_url}/internal/principals/{um_user_id}",
                headers={"X-Service-Key": settings.usermanager_service_key},
                timeout=5.0,
            )
    except Exception as exc:
        logger.warning("Failed to deregister agent from UserManager: %s", exc)


@router.get("", response_model=list[AgentListItem])
async def list_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).order_by(Agent.created_at))
    agents = result.scalars().all()
    return [_agent_to_list_item(a) for a in agents]


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(body: AgentCreate, db: AsyncSession = Depends(get_db)):
    agent = Agent(
        name=body.name,
        ai_gateway_token=body.ai_gateway_token,
        system_prompt=body.system_prompt,
        voice_enabled=body.voice_enabled,
        voice_config=json.dumps(body.voice_config) if body.voice_config else None,
        profile=json.dumps(body.profile) if body.profile else None,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    # Register principal in UserManager
    um_user_id, um_api_key = await _register_with_usermanager(agent.agent_id, body.name)
    if um_user_id:
        agent.um_user_id = um_user_id
        agent.um_api_key = um_api_key
        await db.commit()
        await db.refresh(agent)

    return _agent_to_out(agent)


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return _agent_to_out(agent)


@router.put("/{agent_id}", response_model=AgentOut)
async def update_agent(agent_id: str, body: AgentUpdate, db: AsyncSession = Depends(get_db)):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if body.name is not None:
        agent.name = body.name
    if body.ai_gateway_token is not None:
        agent.ai_gateway_token = body.ai_gateway_token
    if body.system_prompt is not None:
        agent.system_prompt = body.system_prompt
    if body.voice_enabled is not None:
        agent.voice_enabled = body.voice_enabled
    if body.voice_config is not None:
        agent.voice_config = json.dumps(body.voice_config)
    if body.profile is not None:
        agent.profile = json.dumps(body.profile)
    await db.commit()
    await db.refresh(agent)
    return _agent_to_out(agent)


@router.put("/{agent_id}/profile", response_model=AgentOut)
async def update_profile(agent_id: str, profile: dict, db: AsyncSession = Depends(get_db)):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    agent.profile = json.dumps(profile)
    await db.commit()
    await db.refresh(agent)
    return _agent_to_out(agent)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.um_user_id:
        await _deregister_from_usermanager(agent.um_user_id)
    await db.delete(agent)
    await db.commit()
