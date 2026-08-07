import json
from datetime import datetime
from fastapi import APIRouter, Depends, Header
from app.exceptions import AiLayerAuthError, AiLayerError, AiLayerNotFoundError
from pydantic import BaseModel
from app.auth.supabase import get_user_id
from app.cache.client import get_redis
from app.config.logger import Logger, log_event
from app.config.settings import HISTORY_MESSAGES_TTL, HISTORY_SESSIONS_TTL
from app.middleware.auth import verify_api_key
from app.repositories import chat as chat_repo
from app.schemas.response import ApiResponse

logger = Logger.get(__name__)
router = APIRouter(dependencies=[Depends(verify_api_key)])


class SessionUpsert(BaseModel):
    """Request body for creating or updating a chat session record."""

    id: str
    title: str
    created_at: str
    updated_at: str


class SessionPatch(BaseModel):
    """Request body for partially updating a chat session (currently just the title)."""

    title: str | None = None


class MessageSave(BaseModel):
    """A single chat message to persist, as sent by the client when saving history."""

    id: str
    role: str
    content: str
    metadata: dict | None = None
    created_at: str


async def _bust_sessions(redis, user_id: str) -> None:
    """Invalidate the cached session list for a user after it changes.

    Args:
        redis: Redis client, or None if caching is disabled.
        user_id: id whose cached session list should be dropped."""
    if redis:
        await redis.delete(f"history:sessions:{user_id}")


async def _bust_messages(redis, session_id: str) -> None:
    """Invalidate the cached message list for a session after it changes.

    Args:
        redis: Redis client, or None if caching is disabled.
        session_id: id whose cached messages should be dropped."""
    if redis:
        await redis.delete(f"history:messages:{session_id}")


def _parse_token(authorization: str) -> str:
    """Strip the "Bearer " prefix from an Authorization header value.

    Args:
        authorization: Raw Authorization header value.

    Returns:
        The bare token string."""
    return authorization.removeprefix("Bearer ").strip()


def _parse_dt(s: str) -> datetime:
    """Parse an ISO-8601 timestamp (with trailing "Z" or offset) into a datetime.

    Args:
        s: ISO-8601 timestamp string, e.g. a client-supplied created_at/updated_at.

    Returns:
        The parsed datetime."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


async def _resolve_user_id(authorization: str | None, x_user_id: str | None) -> str:
    """Resolve the caller's user id, preferring the trusted `X-User-Id` header
    from a service-to-service caller (already authenticated by that caller,
    since this router is protected by `verify_api_key`), falling back to a
    Supabase bearer token for direct client calls (legacy behavior).

    Raises:
        AiLayerAuthError: if neither an X-User-Id header nor an Authorization
            header is provided."""
    if x_user_id:
        return x_user_id
    if not authorization:
        raise AiLayerAuthError("Thiếu thông tin xác thực", message_key="errors.invalid_token")
    return await get_user_id(_parse_token(authorization))


@router.get("/history/admin/stats")
async def admin_session_stats(days: int = 7):
    """Return chat session/message counts for the admin dashboard.

    Args:
        days: number of trailing days to aggregate over (default 7)."""
    try:
        data = await chat_repo.session_stats(days=days)
    except Exception as e:
        logger.error(log_event("history", "admin session stats failed", error=e), exc_info=True)
        raise AiLayerError(str(e), cause=e) from e
    return ApiResponse.ok(data)


@router.get("/history/sessions")
async def list_sessions(
    authorization: str | None = Header(None),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """List the authenticated user's chat sessions, serving from cache when available.

    Args:
        authorization: Bearer token header, for direct client calls.
        x_user_id: Trusted user id header, for service-to-service callers."""
    try:
        user_id = await _resolve_user_id(authorization, x_user_id)
    except AiLayerAuthError:
        raise
    except Exception as e:
        logger.error(log_event("history", "list sessions auth failed", error=e), exc_info=True)
        raise AiLayerError(str(e), cause=e) from e
    redis = await get_redis()
    key = f"history:sessions:{user_id}"
    if redis:
        cached = await redis.get(key)
        if cached:
            return ApiResponse.ok(json.loads(cached))
    try:
        rows = await chat_repo.list_sessions(user_id)
    except Exception as e:
        logger.error(log_event("history", "list sessions db failed", error=e), exc_info=True)
        raise AiLayerError(str(e), cause=e) from e
    data = [
        {"id": r.id, "title": r.title, "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat()}
        for r in rows
    ]
    if redis:
        await redis.setex(key, HISTORY_SESSIONS_TTL, json.dumps(data))
    return ApiResponse.ok(data)


@router.post("/history/sessions")
async def upsert_session(
    body: SessionUpsert,
    authorization: str | None = Header(None),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """Create or update a chat session record and invalidate its cached session list.

    Args:
        body: Session id, title, and created/updated timestamps.
        authorization: Bearer token header, for direct client calls.
        x_user_id: Trusted user id header, for service-to-service callers."""
    user_id = await _resolve_user_id(authorization, x_user_id)
    await chat_repo.upsert_session(
        session_id=body.id,
        user_id=user_id,
        title=body.title,
        created_at=_parse_dt(body.created_at),
        updated_at=_parse_dt(body.updated_at),
    )
    await _bust_sessions(await get_redis(), user_id)
    return ApiResponse.ok({"id": body.id})


@router.patch("/history/sessions/{session_id}")
async def patch_session(
    session_id: str,
    body: SessionPatch,
    authorization: str | None = Header(None),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """Rename an existing chat session after verifying the caller owns it.

    Args:
        session_id: id of the session to update.
        body: New title for the session.
        authorization: Bearer token header, for direct client calls.
        x_user_id: Trusted user id header, for service-to-service callers.

    Raises:
        AiLayerNotFoundError: if the session doesn't belong to the caller."""
    user_id = await _resolve_user_id(authorization, x_user_id)
    owner_id = await chat_repo.get_session_user_id(session_id)
    if owner_id != user_id:
        raise AiLayerNotFoundError("Không tìm thấy phiên chat", message_key="errors.session_not_found")
    await chat_repo.patch_session(session_id, title=body.title)
    await _bust_sessions(await get_redis(), user_id)
    return ApiResponse.ok({"id": session_id})


@router.delete("/history/sessions/{session_id}")
async def delete_session(
    session_id: str,
    authorization: str | None = Header(None),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """Delete a chat session and its cached session/message lists.

    Verifies the caller owns the session before deleting.

    Args:
        session_id: id of the session to delete.
        authorization: Bearer token header, for direct client calls.
        x_user_id: Trusted user id header, for service-to-service callers.

    Raises:
        AiLayerNotFoundError: if the session doesn't belong to the caller."""
    user_id = await _resolve_user_id(authorization, x_user_id)
    owner_id = await chat_repo.get_session_user_id(session_id)
    if owner_id != user_id:
        raise AiLayerNotFoundError("Không tìm thấy phiên chat", message_key="errors.session_not_found")
    await chat_repo.delete_session(session_id)
    redis = await get_redis()
    await _bust_sessions(redis, user_id)
    await _bust_messages(redis, session_id)
    return ApiResponse.ok({"deleted": session_id})


@router.get("/history/sessions/{session_id}/messages")
async def get_messages(
    session_id: str,
    authorization: str | None = Header(None),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """Return a chat session's messages, serving from cache when available.

    Verifies the caller owns the session before returning its messages.

    Args:
        session_id: id of the session to fetch messages for.
        authorization: Bearer token header, for direct client calls.
        x_user_id: Trusted user id header, for service-to-service callers.

    Raises:
        AiLayerNotFoundError: if the session doesn't belong to the caller."""
    user_id = await _resolve_user_id(authorization, x_user_id)
    redis = await get_redis()
    key = f"history:messages:{session_id}"
    if redis:
        cached = await redis.get(key)
        if cached:
            return ApiResponse.ok(json.loads(cached))
    owner_id = await chat_repo.get_session_user_id(session_id)
    if owner_id != user_id:
        raise AiLayerNotFoundError("Không tìm thấy phiên chat", message_key="errors.session_not_found")
    msgs = await chat_repo.list_messages(session_id)
    data = [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "metadata": m.metadata_,
            "created_at": m.created_at.isoformat(),
        }
        for m in msgs
    ]
    if redis:
        await redis.setex(key, HISTORY_MESSAGES_TTL, json.dumps(data))
    return ApiResponse.ok(data)


@router.post("/history/sessions/{session_id}/messages")
async def save_messages(
    session_id: str,
    body: list[MessageSave],
    authorization: str | None = Header(None),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """Persist a batch of messages for a chat session and invalidate its caches.

    Verifies the caller owns the session before saving.

    Args:
        session_id: id of the session to save messages under.
        body: Messages to persist.
        authorization: Bearer token header, for direct client calls.
        x_user_id: Trusted user id header, for service-to-service callers.

    Raises:
        AiLayerNotFoundError: if the session doesn't belong to the caller.

    Returns:
        ApiResponse with the number of messages saved."""
    user_id = await _resolve_user_id(authorization, x_user_id)
    owner_id = await chat_repo.get_session_user_id(session_id)
    if owner_id != user_id:
        raise AiLayerNotFoundError("Không tìm thấy phiên chat", message_key="errors.session_not_found")
    await chat_repo.save_messages(
        session_id,
        [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "metadata": msg.metadata,
                "created_at": _parse_dt(msg.created_at),
            }
            for msg in body
        ],
    )
    redis = await get_redis()
    await _bust_messages(redis, session_id)
    await _bust_sessions(redis, user_id)
    return ApiResponse.ok({"saved": len(body)})
