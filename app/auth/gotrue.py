from typing import Any
from urllib.parse import urlencode

import httpx

from app.config.constants import SUPABASE_AUTH_TIMEOUT
from app.config.headers import get_supabase_auth_headers
from app.config.settings import SUPABASE_ANON_KEY, SUPABASE_URL
from app.exceptions import AiLayerAuthError

_AUTH_HEADERS = {
    "apikey": SUPABASE_ANON_KEY,
    "Content-Type": "application/json",
}


def _require_supabase() -> None:
    """Ensure Supabase URL and anon key are configured before making auth calls.

    Returns:
        None.

    Raises:
        AiLayerAuthError: If `SUPABASE_URL` or `SUPABASE_ANON_KEY` is unset."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise AiLayerAuthError("Supabase auth chưa cấu hình", message_key="errors.supabase_auth_not_configured")


async def sign_in_email(email: str, password: str) -> dict[str, Any]:
    """Sign in with email/password via Supabase GoTrue."""
    _require_supabase()
    async with httpx.AsyncClient(timeout=SUPABASE_AUTH_TIMEOUT) as client:
        r = await client.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers=_AUTH_HEADERS,
            json={"email": email, "password": password},
        )
    if r.status_code != 200:
        detail = r.json().get("error_description") or r.json().get("msg") or "Invalid credentials"
        raise AiLayerAuthError(str(detail))
    return r.json()


async def sign_up_email(email: str, password: str, full_name: str = "") -> dict[str, Any]:
    """Register a new user."""
    _require_supabase()
    payload: dict[str, Any] = {"email": email, "password": password}
    if full_name:
        payload["data"] = {"full_name": full_name}
    async with httpx.AsyncClient(timeout=SUPABASE_AUTH_TIMEOUT) as client:
        r = await client.post(
            f"{SUPABASE_URL}/auth/v1/signup",
            headers={**_AUTH_HEADERS, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"},
            json=payload,
        )
    if r.status_code not in (200, 201):
        detail = r.json().get("error_description") or r.json().get("msg") or "Sign up failed"
        raise AiLayerAuthError(str(detail))
    return r.json()


def oauth_authorize_url(provider: str, redirect_to: str, code_challenge: str) -> str:
    """Build Supabase OAuth authorize URL (PKCE)."""
    _require_supabase()
    query = urlencode(
        {
            "provider": provider,
            "redirect_to": redirect_to,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{SUPABASE_URL}/auth/v1/authorize?{query}"


async def exchange_oauth_code(
    code: str,
    code_verifier: str,
    redirect_uri: str | None = None,
) -> dict[str, Any]:
    """Exchange OAuth authorization code for session tokens."""
    _require_supabase()
    headers = {
        **_AUTH_HEADERS,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    }
    body: dict[str, Any] = {"auth_code": code, "code_verifier": code_verifier}
    if redirect_uri:
        body["redirect_uri"] = redirect_uri

    async with httpx.AsyncClient(timeout=SUPABASE_AUTH_TIMEOUT) as client:
        r = await client.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=pkce",
            headers=headers,
            json=body,
        )

    if r.status_code == 200:
        return r.json()

    # Legacy/alternate GoTrue payload key
    alt_body: dict[str, Any] = {"code": code, "code_verifier": code_verifier}
    if redirect_uri:
        alt_body["redirect_uri"] = redirect_uri
    async with httpx.AsyncClient(timeout=SUPABASE_AUTH_TIMEOUT) as client:
        r2 = await client.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=pkce",
            headers=headers,
            json=alt_body,
        )
    if r2.status_code != 200:
        detail = (
            r.json().get("error_description")
            or r.json().get("msg")
            or r2.json().get("error_description")
            or r2.json().get("msg")
            or "OAuth exchange failed"
        )
        raise AiLayerAuthError(str(detail))
    return r2.json()


async def refresh_token(refresh_token_value: str) -> dict[str, Any]:
    """Exchange a refresh token for a new access token via Supabase GoTrue."""
    _require_supabase()
    async with httpx.AsyncClient(timeout=SUPABASE_AUTH_TIMEOUT) as client:
        r = await client.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
            headers=_AUTH_HEADERS,
            json={"refresh_token": refresh_token_value},
        )
    if r.status_code != 200:
        detail = r.json().get("error_description") or r.json().get("msg") or "Invalid refresh token"
        raise AiLayerAuthError(str(detail))
    return r.json()


async def get_user(token: str) -> dict[str, Any]:
    """Validate JWT and return Supabase user object."""
    _require_supabase()
    async with httpx.AsyncClient(timeout=SUPABASE_AUTH_TIMEOUT) as client:
        r = await client.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers=get_supabase_auth_headers(token, SUPABASE_ANON_KEY),
        )
    if r.status_code != 200:
        raise AiLayerAuthError("Token không hợp lệ hoặc đã hết hạn", message_key="errors.invalid_token")
    user = r.json()
    if not user.get("id"):
        raise AiLayerAuthError("Không lấy được thông tin user từ token", message_key="errors.cannot_extract_user")
    return user
