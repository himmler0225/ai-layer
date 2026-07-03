from typing import Any

from fastapi import Header

from app.auth.gotrue import get_user
from app.auth.profiles import get_profile
from app.exceptions import AiLayerAuthError, AiLayerForbiddenError


def parse_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise AiLayerAuthError("Missing authorization")
    token = authorization[7:].strip()
    if not token:
        raise AiLayerAuthError("Missing authorization")
    return token


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    token = parse_bearer(authorization)
    user = await get_user(token)
    profile = await get_profile(user["id"])
    return {
        "user": user,
        "profile": profile,
        "token": token,
    }


async def require_admin(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    ctx = await get_current_user(authorization)
    profile = ctx.get("profile")
    if not profile or profile.get("role") != "admin":
        raise AiLayerForbiddenError("Admin access required")
    return ctx
