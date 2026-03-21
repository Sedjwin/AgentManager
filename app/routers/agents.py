"""Agent CRUD endpoints."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Agent
from app.schemas import AgentCreate, AgentListItem, AgentOut, AgentUpdate

router = APIRouter(prefix="/agents", tags=["agents"])


def _agent_to_out(agent: Agent) -> AgentOut:
    return AgentOut(
        agent_id=agent.agent_id,
        name=agent.name,
        system_prompt=agent.system_prompt,
        voice_enabled=agent.voice_enabled,
        voice_config=json.loads(agent.voice_config) if agent.voice_config else None,
        profile=json.loads(agent.profile) if agent.profile else None,
        has_profile=agent.profile is not None,
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
    await db.delete(agent)
    await db.commit()
