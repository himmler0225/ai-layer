from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from app.auth.config_admin import json_keys, load_config_bundle, patch_config
from app.config.defaults import load_schema
from app.auth.deps import get_current_user, require_admin
from app.auth.gotrue import (
    exchange_oauth_code,
    get_user,
    oauth_authorize_url,
    refresh_token,
    sign_in_email,
    sign_up_email,
)
from app.auth.profiles import count_profiles, get_profile, list_profiles, update_profile_role
from app.exceptions import AiLayerValidationError
from app.middleware.auth import verify_api_key
from app.schemas.response import ApiResponse

router = APIRouter(prefix="/auth", dependencies=[Depends(verify_api_key)])


class SignInBody(BaseModel):
    email: EmailStr
    password: str


class SignUpBody(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class OAuthCallbackBody(BaseModel):
    code: str
    code_verifier: str
    redirect_uri: str | None = None


class OAuthStartBody(BaseModel):
    provider: str = "google"
    redirect_to: str
    code_challenge: str


class RefreshBody(BaseModel):
    refresh_token: str


class RolePatchBody(BaseModel):
    role: str


class ConfigPatchBody(BaseModel):
    updates: dict[str, str]


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    """Extract the publicly safe fields from a raw GoTrue user record.

    Args:
        user: Raw user object as returned by Supabase GoTrue.

    Returns:
        dict with id, email, full_name, and avatar_url, pulling display name
        and avatar from user_metadata."""
    meta = user.get("user_metadata") or {}
    return {
        "id": user.get("id"),
        "email": user.get("email"),
        "full_name": meta.get("full_name") or meta.get("name"),
        "avatar_url": meta.get("avatar_url") or meta.get("picture"),
    }


async def _session_with_profile(payload: dict[str, Any]) -> dict[str, Any]:
    """Build the client-facing session response by attaching the user's profile.

    Fetches the user record from GoTrue if it isn't already embedded in the
    payload (e.g. when only an access token is available).

    Args:
        payload: Auth response from sign-in/sign-up/OAuth/refresh, containing
            access_token, refresh_token, expires_in, and optionally user.

    Returns:
        dict with access_token, refresh_token, expires_in, and the merged
        user/profile object."""
    user = payload.get("user") or {}
    if not user.get("id") and payload.get("access_token"):
        user = await get_user(payload["access_token"])
    profile = await get_profile(user.get("id") or "")
    return {
        "access_token": payload.get("access_token"),
        "refresh_token": payload.get("refresh_token"),
        "expires_in": payload.get("expires_in"),
        "user": _profile_response({"user": user, "profile": profile}),
    }


def _profile_response(ctx: dict[str, Any]) -> dict[str, Any]:
    """Merge a GoTrue user with its app profile row into the client-facing shape.

    Args:
        ctx: dict with "user" (raw GoTrue user) and optional "profile"
            (row from the profiles table).

    Returns:
        dict with id, email, full_name, role (defaults to "user" if the
        profile has none), and avatar_url."""
    user = ctx["user"]
    profile = ctx.get("profile") or {}
    pub = _public_user(user)
    return {
        "id": pub["id"],
        "email": profile.get("email") or pub["email"],
        "full_name": profile.get("full_name") or pub["full_name"],
        "role": profile.get("role") or "user",
        "avatar_url": pub.get("avatar_url"),
    }


@router.post("/signin")
async def signin(body: SignInBody):
    """Sign in with email and password and return a session with profile.

    Args:
        body: Email and password credentials."""
    payload = await sign_in_email(body.email, body.password)
    return ApiResponse.ok(await _session_with_profile(payload))


@router.post("/signup")
async def signup(body: SignUpBody):
    """Register a new account with email and password.

    Returns an active session with profile if a session was issued
    immediately (no email confirmation required), otherwise just the
    newly created user with no session.

    Args:
        body: Email, password, and optional display name."""
    payload = await sign_up_email(body.email, body.password, body.full_name or "")
    if payload.get("access_token"):
        return ApiResponse.ok(await _session_with_profile(payload))
    user = payload.get("user") or {}
    return ApiResponse.ok({"user": _public_user(user), "session": None})


@router.post("/oauth/start")
async def oauth_start(body: OAuthStartBody):
    """Build the provider's OAuth authorization URL to begin a PKCE sign-in flow.

    Args:
        body: OAuth provider, redirect target, and PKCE code challenge."""
    url = oauth_authorize_url(body.provider, body.redirect_to, body.code_challenge)
    return ApiResponse.ok({"url": url})


@router.post("/oauth/callback")
async def oauth_callback(body: OAuthCallbackBody):
    """Exchange an OAuth authorization code for a session with profile.

    Args:
        body: Authorization code, PKCE code verifier, and optional redirect URI."""
    payload = await exchange_oauth_code(body.code, body.code_verifier, body.redirect_uri)
    return ApiResponse.ok(await _session_with_profile(payload))


@router.post("/refresh")
async def refresh(body: RefreshBody):
    """Exchange a refresh token for a new session with profile.

    Args:
        body: The refresh token to redeem."""
    payload = await refresh_token(body.refresh_token)
    return ApiResponse.ok(await _session_with_profile(payload))


@router.get("/me")
async def me(ctx: dict = Depends(get_current_user)):
    """Return the current authenticated user's profile.

    Args:
        ctx: Auth context injected by the get_current_user dependency."""
    return ApiResponse.ok(_profile_response(ctx))


@router.get("/admin/me")
async def admin_me(ctx: dict = Depends(require_admin)):
    """Return the current admin user's own profile.

    Args:
        ctx: Auth context injected by the require_admin dependency."""
    return ApiResponse.ok(_profile_response(ctx))


@router.get("/admin/users")
async def admin_users(_ctx: dict = Depends(require_admin)):
    """List all user profiles (admin-only).

    Args:
        _ctx: Auth context injected by the require_admin dependency; only
            used to enforce authorization."""
    return ApiResponse.ok(await list_profiles())


@router.patch("/admin/users/{user_id}")
async def admin_patch_user(user_id: str, body: RolePatchBody, ctx: dict = Depends(require_admin)):
    """Update a user's role (admin-only).

    Args:
        user_id: id of the user whose role is being changed.
        body: The new role to assign.
        ctx: Auth context of the calling admin, used to prevent an admin
            from demoting their own account.

    Raises:
        AiLayerValidationError: if the caller targets their own account
            with a role other than "admin"."""
    if user_id == ctx["user"]["id"] and body.role != "admin":
        raise AiLayerValidationError(
            "Không thể hạ quyền tài khoản của chính bạn",
            message_key="errors.cannot_demote_self",
        )
    row = await update_profile_role(user_id, body.role)
    return ApiResponse.ok(row)


@router.get("/admin/config")
async def admin_get_config(_ctx: dict = Depends(require_admin)):
    """Return the current remote config bundle and its metadata (admin-only).

    Args:
        _ctx: Auth context injected by the require_admin dependency; only
            used to enforce authorization.

    Returns:
        dict with "config" (current values) and "meta" describing which
        keys are JSON-typed, long text, or secret, plus per-key update
        timestamps."""
    bundle = await load_config_bundle()
    admin_cfg = load_schema().get("admin") or {}
    return ApiResponse.ok(
        {
            "config": bundle["config"],
            "meta": {
                "jsonKeys": sorted(json_keys()),
                "longTextKeys": sorted(admin_cfg.get("long_text_keys") or []),
                "secretKeys": sorted(admin_cfg.get("secret_keys") or []),
                "updatedAt": bundle.get("updated_at") or {},
                "items": bundle.get("items") or {},
            },
        }
    )


@router.patch("/admin/config")
async def admin_patch_config(body: ConfigPatchBody, _ctx: dict = Depends(require_admin)):
    """Patch one or more remote config keys (admin-only).

    Args:
        body: Mapping of config keys to their new values.
        _ctx: Auth context injected by the require_admin dependency; only
            used to enforce authorization.

    Raises:
        AiLayerValidationError: if body.updates is empty."""
    if not body.updates:
        raise AiLayerValidationError("Không có trường nào để cập nhật", message_key="errors.no_updates")
    saved = await patch_config(body.updates)
    return ApiResponse.ok({"saved": saved})


@router.get("/admin/stats")
async def admin_stats(_ctx: dict = Depends(require_admin)):
    """Return aggregate user counts for the admin dashboard (admin-only).

    Args:
        _ctx: Auth context injected by the require_admin dependency; only
            used to enforce authorization.

    Returns:
        dict with totalUsers and adminUsers counts."""
    total, admins = await count_profiles()
    return ApiResponse.ok({"totalUsers": total, "adminUsers": admins})
