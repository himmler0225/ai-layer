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
    meta = user.get("user_metadata") or {}
    return {
        "id": user.get("id"),
        "email": user.get("email"),
        "full_name": meta.get("full_name") or meta.get("name"),
        "avatar_url": meta.get("avatar_url") or meta.get("picture"),
    }


async def _session_with_profile(payload: dict[str, Any]) -> dict[str, Any]:
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
    payload = await sign_in_email(body.email, body.password)
    return ApiResponse.ok(await _session_with_profile(payload))


@router.post("/signup")
async def signup(body: SignUpBody):
    payload = await sign_up_email(body.email, body.password, body.full_name or "")
    if payload.get("access_token"):
        return ApiResponse.ok(await _session_with_profile(payload))
    user = payload.get("user") or {}
    return ApiResponse.ok({"user": _public_user(user), "session": None})


@router.post("/oauth/start")
async def oauth_start(body: OAuthStartBody):
    url = oauth_authorize_url(body.provider, body.redirect_to, body.code_challenge)
    return ApiResponse.ok({"url": url})


@router.post("/oauth/callback")
async def oauth_callback(body: OAuthCallbackBody):
    payload = await exchange_oauth_code(body.code, body.code_verifier, body.redirect_uri)
    return ApiResponse.ok(await _session_with_profile(payload))


@router.post("/refresh")
async def refresh(body: RefreshBody):
    payload = await refresh_token(body.refresh_token)
    return ApiResponse.ok(await _session_with_profile(payload))


@router.get("/me")
async def me(ctx: dict = Depends(get_current_user)):
    return ApiResponse.ok(_profile_response(ctx))


@router.get("/admin/me")
async def admin_me(ctx: dict = Depends(require_admin)):
    return ApiResponse.ok(_profile_response(ctx))


@router.get("/admin/users")
async def admin_users(_ctx: dict = Depends(require_admin)):
    return ApiResponse.ok(await list_profiles())


@router.patch("/admin/users/{user_id}")
async def admin_patch_user(user_id: str, body: RolePatchBody, ctx: dict = Depends(require_admin)):
    if user_id == ctx["user"]["id"] and body.role != "admin":
        raise AiLayerValidationError("Cannot demote your own admin account")
    row = await update_profile_role(user_id, body.role)
    return ApiResponse.ok(row)


@router.get("/admin/config")
async def admin_get_config(_ctx: dict = Depends(require_admin)):
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
    if not body.updates:
        raise AiLayerValidationError("No updates")
    saved = await patch_config(body.updates)
    return ApiResponse.ok({"saved": saved})


@router.get("/admin/stats")
async def admin_stats(_ctx: dict = Depends(require_admin)):
    total, admins = await count_profiles()
    return ApiResponse.ok({"totalUsers": total, "adminUsers": admins})
