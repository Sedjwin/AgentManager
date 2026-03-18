"""CRUD endpoints for Agent resources."""

import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Agent, AgentCreate, AgentResponse, AgentUpdate, apply_create, apply_update
from app.services.aigateway import admin_delete_agent, admin_register_agent, admin_sync_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.get("", response_model=list[AgentResponse])
async def list_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).order_by(Agent.id))
    agents = result.scalars().all()
    return [AgentResponse.from_orm_agent(a) for a in agents]


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(body: AgentCreate, db: AsyncSession = Depends(get_db)):
    agent = apply_create(body)
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    # Register in AIGateway and store the returned api_key as gateway_token
    if not agent.gateway_token:
        try:
            gw_key = await admin_register_agent(
                name=agent.name,
                bio=agent.bio or "",
                smart_routing=agent.smart_routing,
                preferred_model=agent.default_model or "",
            )
            agent.gateway_token = gw_key
            await db.commit()
            await db.refresh(agent)
        except Exception as exc:
            logger.warning("AIGateway registration failed for '%s': %s", agent.name, exc)

    return AgentResponse.from_orm_agent(agent)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    agent = await _get_or_404(agent_id, db)
    return AgentResponse.from_orm_agent(agent)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int, body: AgentUpdate, db: AsyncSession = Depends(get_db)
):
    agent = await _get_or_404(agent_id, db)
    agent = apply_update(agent, body)
    await db.commit()
    await db.refresh(agent)

    # Sync name, description, and routing policy with AIGateway (best-effort)
    if agent.gateway_token:
        await admin_sync_agent(
            gateway_token=agent.gateway_token,
            name=agent.name,
            bio=agent.bio or "",
            smart_routing=agent.smart_routing,
            preferred_model=agent.default_model or "",
        )

    return AgentResponse.from_orm_agent(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    agent = await _get_or_404(agent_id, db)
    if agent.gateway_token:
        await admin_delete_agent(agent.gateway_token)
    await db.delete(agent)
    await db.commit()


@router.post("/{agent_id}/regenerate-key", response_model=AgentResponse)
async def regenerate_key(agent_id: int, db: AsyncSession = Depends(get_db)):
    agent = await _get_or_404(agent_id, db)
    agent.api_key = secrets.token_hex(32)
    await db.commit()
    await db.refresh(agent)
    return AgentResponse.from_orm_agent(agent)


@router.post("/{agent_id}/register-gateway", response_model=AgentResponse)
async def register_gateway(agent_id: int, db: AsyncSession = Depends(get_db)):
    """(Re)register this agent with AIGateway and store the returned gateway_token."""
    agent = await _get_or_404(agent_id, db)
    try:
        gw_key = await admin_register_agent(
            name=agent.name,
            bio=agent.bio or "",
            smart_routing=agent.smart_routing,
            preferred_model=agent.default_model or "",
        )
        agent.gateway_token = gw_key
        await db.commit()
        await db.refresh(agent)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AIGateway registration failed: {exc}")
    return AgentResponse.from_orm_agent(agent)


# ── Helper ─────────────────────────────────────────────────────────────────────

async def _get_or_404(agent_id: int, db: AsyncSession) -> Agent:
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return agent
