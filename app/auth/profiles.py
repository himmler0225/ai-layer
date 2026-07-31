from typing import Any

import httpx

from app.config.constants import SUPABASE_AUTH_TIMEOUT
from app.config.headers import get_supabase_rest_headers
from app.config.settings import SUPABASE_SERVICE_KEY, SUPABASE_URL
from app.exceptions import AiLayerAuthError, AiLayerError
from datetime import UTC

_PROFILE_FIELDS = "id,email,full_name,role,created_at,updated_at"
_VALID_ROLES = {"user", "admin"}


def _require_service_key() -> None:
    """(Nội bộ) Require service key `_require_service_key`.

    Returns:
        (None) Kết quả trả về."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise AiLayerError("Supabase service key is not configured")


async def get_profile(user_id: str) -> dict[str, Any] | None:
    """Load a single profile row."""
    _require_service_key()
    async with httpx.AsyncClient(timeout=SUPABASE_AUTH_TIMEOUT) as client:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/profiles",
            params={"id": f"eq.{user_id}", "select": _PROFILE_FIELDS},
            headers={**get_supabase_rest_headers(SUPABASE_SERVICE_KEY), "Accept": "application/json"},
        )
    if not r.is_success:
        raise AiLayerError("Failed to load profile")
    rows = r.json()
    return rows[0] if rows else None


async def list_profiles() -> list[dict[str, Any]]:
    """List all profiles (admin)."""
    _require_service_key()
    async with httpx.AsyncClient(timeout=SUPABASE_AUTH_TIMEOUT) as client:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/profiles",
            params={"select": _PROFILE_FIELDS, "order": "created_at.desc"},
            headers={**get_supabase_rest_headers(SUPABASE_SERVICE_KEY), "Accept": "application/json"},
        )
    if not r.is_success:
        raise AiLayerError("Failed to list profiles")
    return r.json()


async def update_profile_role(user_id: str, role: str) -> dict[str, Any]:
    """Update user role (admin)."""
    if role not in _VALID_ROLES:
        raise AiLayerAuthError("Invalid role")
    _require_service_key()
    from datetime import datetime

    now = datetime.now(UTC).isoformat()
    async with httpx.AsyncClient(timeout=SUPABASE_AUTH_TIMEOUT) as client:
        r = await client.patch(
            f"{SUPABASE_URL}/rest/v1/profiles",
            params={"id": f"eq.{user_id}", "select": "id,email,full_name,role"},
            headers={
                **get_supabase_rest_headers(SUPABASE_SERVICE_KEY),
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json={"role": role, "updated_at": now},
        )
    if not r.is_success:
        raise AiLayerError("Failed to update profile")
    rows = r.json()
    if not rows:
        raise AiLayerError("Profile not found")
    return rows[0]


async def count_profiles() -> tuple[int, int]:
    """Return (total_users, admin_users)."""
    _require_service_key()
    headers = {
        **get_supabase_rest_headers(SUPABASE_SERVICE_KEY),
        "Prefer": "count=exact",
    }
    async with httpx.AsyncClient(timeout=SUPABASE_AUTH_TIMEOUT) as client:
        total_r = await client.head(
            f"{SUPABASE_URL}/rest/v1/profiles",
            params={"select": "id"},
            headers=headers,
        )
        admin_r = await client.head(
            f"{SUPABASE_URL}/rest/v1/profiles",
            params={"select": "id", "role": "eq.admin"},
            headers=headers,
        )
    total = _parse_content_range(total_r.headers.get("content-range"))
    admins = _parse_content_range(admin_r.headers.get("content-range"))
    return total, admins


def _parse_content_range(value: str | None) -> int:
    """(Nội bộ) Phân tích content range `_parse_content_range`.

    Args:
        value: (str | None) Tham số `value`.

    Returns:
        (int) Kết quả trả về."""
    if not value or "/" not in value:
        return 0
    try:
        return int(value.split("/")[-1])
    except ValueError:
        return 0
