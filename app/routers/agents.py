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
from app.schemas import AgentCreate, AgentListItem, AgentOut, AgentToolConfig, AgentToolItem, AgentUpdate

router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger(__name__)


def _agent_to_out(agent: Agent) -> AgentOut:
    enabled_tools_data = json.loads(agent.enabled_tools or "[]")
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
        tool_use_enabled=agent.tool_use_enabled,
        enabled_tools=[t["name"] for t in enabled_tools_data],
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
        um_user_id=agent.um_user_id,
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


# ── Tool configuration ────────────────────────────────────────────────────────

@router.get("/{agent_id}/tools", response_model=list[AgentToolItem])
async def get_agent_tools(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Return the list of tools granted to this agent (fetched from ToolGateway)."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if not agent.um_user_id or not agent.um_api_key:
        return []

    enabled_tools_data = json.loads(agent.enabled_tools or "[]")
    enabled_names = {t["name"] for t in enabled_tools_data}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Fetch grants for this agent's principal
            grants_r = await client.get(
                f"{settings.toolgateway_url}/api/grants",
                params={"principal_id": str(agent.um_user_id)},
                headers={"Authorization": f"Bearer {agent.um_api_key}"},
            )
            if grants_r.status_code != 200:
                return []
            grants = grants_r.json()

            # Fetch full tool details for each grant
            items: list[AgentToolItem] = []
            for grant in grants:
                tool_r = await client.get(
                    f"{settings.toolgateway_url}/api/tools/{grant['tool_id']}",
                    headers={"Authorization": f"Bearer {agent.um_api_key}"},
                )
                if tool_r.status_code != 200:
                    continue
                t = tool_r.json()
                items.append(AgentToolItem(
                    tool_id=t["tool_id"],
                    name=t["name"],
                    description=t["description"],
                    state=t["state"],
                    enabled=t["enabled"],
                    skill_md=t["skill_md"],
                    grant_id=grant["id"],
                    grant_enabled=grant["enabled"],
                ))
            return items
    except Exception as exc:
        logger.warning("Could not fetch tools from ToolGateway: %s", exc)
        return []


@router.put("/{agent_id}/tools")
async def update_agent_tools(
    agent_id: str,
    body: AgentToolConfig,
    db: AsyncSession = Depends(get_db),
):
    """Update which tools are enabled for this agent and cache their SkillMD."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    agent.tool_use_enabled = body.tool_use_enabled

    if not body.enabled_tools:
        agent.enabled_tools = "[]"
    else:
        # Fetch SkillMD for each enabled tool from ToolGateway
        tools_with_md = []
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                all_tools_r = await client.get(f"{settings.toolgateway_url}/api/tools")
                if all_tools_r.status_code == 200:
                    all_tools = {t["name"]: t for t in all_tools_r.json()}
                    for name in body.enabled_tools:
                        if name in all_tools:
                            tools_with_md.append({
                                "name": name,
                                "skill_md": all_tools[name].get("skill_md", ""),
                            })
                        else:
                            tools_with_md.append({"name": name, "skill_md": ""})
        except Exception as exc:
            logger.warning("Could not fetch tool SkillMDs from ToolGateway: %s", exc)
            tools_with_md = [{"name": n, "skill_md": ""} for n in body.enabled_tools]

        agent.enabled_tools = json.dumps(tools_with_md)

    await db.commit()
    await db.refresh(agent)
    return {"tool_use_enabled": agent.tool_use_enabled, "enabled_tools": body.enabled_tools}
