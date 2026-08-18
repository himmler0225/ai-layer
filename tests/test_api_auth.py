"""Integration tests for the HTTP surface: API-key auth boundary shared by every
router, the centralized error envelope, and the unauthenticated /health route.

These hit the real ASGI app (no lifespan — Supabase/DB startup is skipped by
using httpx's ASGITransport directly) so they stay hermetic in CI without a
live Postgres/Redis/Supabase instance.
"""

from __future__ import annotations

import httpx
import pytest

from app.main import app

# Each router below applies verify_api_key as a router-level dependency, so
# one representative GET endpoint per router exercises the same auth check.


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.mark.parametrize(
    "path",
    [
        "/ai/youtube/trending/analysis",
        "/ai/history/sessions",
        "/ai/admin/health/detail",
        "/ai/runtime/chat-config",
        # /ai/auth/me is deliberately excluded: it stacks a second dependency
        # (get_current_user) whose own "missing Authorization" check fires
        # first and returns 401 — see test_missing_api_key_on_stacked_auth_route.
        "/ai/auth/admin/config",
    ],
)
async def test_missing_api_key_is_rejected(client: httpx.AsyncClient, path: str):
    resp = await client.get(path)
    assert resp.status_code == 422


async def test_missing_api_key_on_stacked_auth_route(client: httpx.AsyncClient):
    # /ai/auth/me depends on both verify_api_key (router-level) and
    # get_current_user (route-level); with neither X-API-Key nor Authorization
    # present, it still fails closed — just via the other dependency's error.
    resp = await client.get("/ai/auth/me")
    assert resp.status_code == 401
    assert resp.json()["success"] is False


@pytest.mark.parametrize(
    "path",
    [
        "/ai/youtube/trending/analysis",
        "/ai/history/sessions",
        "/ai/admin/health/detail",
        "/ai/auth/me",
        "/ai/runtime/chat-config",
        "/ai/auth/admin/config",
    ],
)
async def test_invalid_api_key_is_rejected_with_error_envelope(client: httpx.AsyncClient, path: str):
    resp = await client.get(path, headers={"X-API-Key": "not-a-real-key"})

    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False
    assert isinstance(body["error"], str) and body["error"]
    assert "X-Process-Time-Ms" in resp.headers


async def test_invalid_api_key_rejected_before_request_body_is_processed(client: httpx.AsyncClient):
    # POST /ai/agent/run requires a body; an invalid key must still short-circuit
    # to 401 rather than falling through to a 422 body-validation error.
    resp = await client.post("/ai/agent/run", headers={"X-API-Key": "not-a-real-key"}, json={})
    assert resp.status_code == 401


async def test_health_endpoint_is_public_and_well_formed(client: httpx.AsyncClient):
    resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["service"] == "ai-layer"
    assert set(body["data"]["checks"].keys()) == {"postgres", "redis", "data_miner", "llm_key"}
    assert body["data"]["healthy"] in (True, False)


async def test_unknown_route_returns_404(client: httpx.AsyncClient):
    # Routing-level 404s (no matching path) bypass the app's registered
    # HTTPException handler and return Starlette's bare default body —
    # unlike every other error path, which is wrapped in the ApiResponse
    # envelope. Documented here as current behavior, not asserted as ideal.
    resp = await client.get("/ai/this-route-does-not-exist")
    assert resp.status_code == 404
