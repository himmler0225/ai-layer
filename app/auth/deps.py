from typing import Any

from fastapi import Header

from app.auth.gotrue import get_user
from app.auth.profiles import get_profile
from app.exceptions import AiLayerAuthError, AiLayerForbiddenError


def parse_bearer(authorization: str | None) -> str:
    """Phân tích bearer.

    Args:
        authorization: (str | None) Tham số `authorization`.

    Returns:
        (str) Kết quả trả về."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AiLayerAuthError("Thiếu header Authorization", message_key="errors.missing_authorization")
    token = authorization[7:].strip()
    if not token:
        raise AiLayerAuthError("Thiếu header Authorization", message_key="errors.missing_authorization")
    return token


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Lấy current user (async).

    Args:
        authorization: (str | None, mặc định Header(default=None)) Tham số `authorization`.

    Returns:
        (dict[str, Any]) Kết quả trả về."""
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
    """Require admin (async).

    Args:
        authorization: (str | None, mặc định Header(default=None)) Tham số `authorization`.

    Returns:
        (dict[str, Any]) Kết quả trả về."""
    ctx = await get_current_user(authorization)
    profile = ctx.get("profile")
    if not profile or profile.get("role") != "admin":
        raise AiLayerForbiddenError("Cần quyền admin", message_key="errors.admin_required")
    return ctx
