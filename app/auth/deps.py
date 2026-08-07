from typing import Any

from fastapi import Header

from app.auth.gotrue import get_user
from app.auth.profiles import get_profile
from app.exceptions import AiLayerAuthError, AiLayerForbiddenError


def parse_bearer(authorization: str | None) -> str:
    """Extract the bearer token from an `Authorization` header value.

    Args:
        authorization: Raw `Authorization` header value, expected to start
            with `"Bearer "`.

    Returns:
        The token string (without the `Bearer ` prefix).

    Raises:
        AiLayerAuthError: If the header is missing, doesn't start with
            `"Bearer "`, or the token part is empty."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AiLayerAuthError("Thiếu header Authorization", message_key="errors.missing_authorization")
    token = authorization[7:].strip()
    if not token:
        raise AiLayerAuthError("Thiếu header Authorization", message_key="errors.missing_authorization")
    return token


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """FastAPI dependency that resolves the authenticated user from the request.

    Validates the bearer token against Supabase and loads the user's profile.

    Args:
        authorization: The request's `Authorization` header.

    Returns:
        A dict with `user` (Supabase user object), `profile` (profile row or
        `None`), and `token` (the raw bearer token)."""
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
    """FastAPI dependency that requires the authenticated user to have the
    `admin` role.

    Args:
        authorization: The request's `Authorization` header.

    Returns:
        The same context dict as `get_current_user`.

    Raises:
        AiLayerForbiddenError: If the user has no profile or isn't an admin."""
    ctx = await get_current_user(authorization)
    profile = ctx.get("profile")
    if not profile or profile.get("role") != "admin":
        raise AiLayerForbiddenError("Cần quyền admin", message_key="errors.admin_required")
    return ctx
