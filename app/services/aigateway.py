"""HTTP client for AIGateway (http://localhost:8001).

Two layers:
  - AIGatewayClient(token)  — LLM calls via agent Bearer token
  - admin_*()               — admin API calls (X-Admin-Key header required)
"""

import logging

import httpx
from app.config import settings

logger = logging.getLogger(__name__)


def _admin_headers() -> dict:
    """Headers required for AIGateway admin endpoints."""
    headers = {}
    if settings.aigateway_admin_key:
        headers["X-Admin-Key"] = settings.aigateway_admin_key
    return headers


async def admin_register_agent(name: str, bio: str, smart_routing: bool, preferred_model: str) -> str:
    """
    Create (or find existing) agent entry in AIGateway.
    Returns the AIGateway-generated api_key to use as gateway_token.
    """
    base = settings.aigateway_url
    headers = _admin_headers()

    # Check if an agent with this name already exists
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{base}/admin/agents", headers=headers)
        existing = {a["name"]: a for a in (r.json() if r.is_success else [])}

        if name in existing:
            # Return existing key (preserve it — don't regenerate)
            return existing[name]["api_key"]

        # Create new agent in AIGateway (system_prompt empty — owned by AgentManager)
        payload = {
            "name": name,
            "description": bio or "Managed by AgentManager",
            "notes": "Agent config (system_prompt, personality, avatar) lives in AgentManager.",
            "system_prompt": "",
            "permissions": {
                "allowed_providers": ["all"],
                "allowed_models": [],
                "default_model": preferred_model or "",
                "auto_route": smart_routing,
            },
        }
        r = await client.post(f"{base}/admin/agents", json=payload, headers=headers)
        r.raise_for_status()
        return r.json()["api_key"]


async def admin_sync_agent(gateway_token: str, name: str, smart_routing: bool, preferred_model: str) -> None:
    """Update AIGateway routing policy for an existing agent (best-effort)."""
    base = settings.aigateway_url
    headers = _admin_headers()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{base}/admin/agents", headers=headers)
            if not r.is_success:
                return
            for a in r.json():
                if a.get("api_key") == gateway_token:
                    await client.put(
                        f"{base}/admin/agents/{a['id']}",
                        json={
                            "permissions": {
                                "allowed_providers": ["all"],
                                "allowed_models": [],
                                "default_model": preferred_model or "",
                                "auto_route": smart_routing,
                            }
                        },
                        headers=headers,
                    )
                    return
    except Exception as exc:
        logger.warning("AIGateway sync failed: %s", exc)


async def admin_delete_agent(gateway_token: str) -> None:
    """Remove an agent from AIGateway by its api_key (best-effort)."""
    base = settings.aigateway_url
    headers = _admin_headers()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{base}/admin/agents", headers=headers)
            if not r.is_success:
                return
            for a in r.json():
                if a.get("api_key") == gateway_token:
                    await client.delete(f"{base}/admin/agents/{a['id']}", headers=headers)
                    return
    except Exception as exc:
        logger.warning("AIGateway delete failed: %s", exc)


class AIGatewayClient:
    def __init__(self, gateway_token: str):
        self.base_url = settings.aigateway_url
        self.headers = {"Authorization": f"Bearer {gateway_token}"}

    async def complete(
        self,
        messages: list,
        model: str | None = None,
        prefer_premium: bool = False,
    ) -> dict:
        """POST /v1/chat/completions — returns the full response dict."""
        payload: dict = {"messages": messages, "stream": False}
        if model:
            payload["model"] = model

        headers = dict(self.headers)
        if prefer_premium:
            headers["X-Quality"] = "premium"

        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            r.raise_for_status()
            return r.json()

    async def list_models(self) -> list:
        """GET /v1/models — returns list of model objects."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{self.base_url}/v1/models",
                headers=self.headers,
            )
            r.raise_for_status()
            data = r.json()
            return data.get("data", data) if isinstance(data, dict) else data
