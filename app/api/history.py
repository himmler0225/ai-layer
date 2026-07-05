import json
from datetime import datetime
from fastapi import APIRouter, Depends, Header
from app.exceptions import AiLayerAuthError, AiLayerError, AiLayerNotFoundError
from pydantic import BaseModel
from app.auth.supabase import get_user_id
from app.cache.client import get_redis
from app.config.logger import Logger
from app.config.settings import HISTORY_MESSAGES_TTL, HISTORY_SESSIONS_TTL
from app.middleware.auth import verify_api_key
from app.repositories import chat as chat_repo
from app.schemas.response import ApiResponse

logger = Logger.get(__name__)
router = APIRouter(dependencies=[Depends(verify_api_key)])


class SessionUpsert(BaseModel):
    """Lớp `SessionUpsert` (kế thừa BaseModel)."""

    id: str
    title: str
    created_at: str
    updated_at: str


class SessionPatch(BaseModel):
    """Lớp `SessionPatch` (kế thừa BaseModel)."""

    title: str | None = None


class MessageSave(BaseModel):
    """Lớp `MessageSave` (kế thừa BaseModel)."""

    id: str
    role: str
    content: str
    metadata: dict | None = None
    created_at: str


async def _bust_sessions(redis, user_id: str) -> None:
    """(Nội bộ) Bust sessions (async).

    Args:
        redis: (Any) Tham số `redis`.
        user_id: (str) Tham số `user_id`.

    Returns:
        (None) Kết quả trả về."""
    if redis:
        await redis.delete(f"history:sessions:{user_id}")


async def _bust_messages(redis, session_id: str) -> None:
    """(Nội bộ) Bust messages (async).

    Args:
        redis: (Any) Tham số `redis`.
        session_id: (str) Tham số `session_id`.

    Returns:
        (None) Kết quả trả về."""
    if redis:
        await redis.delete(f"history:messages:{session_id}")


def _parse_token(authorization: str) -> str:
    """(Nội bộ) Phân tích token.

    Args:
        authorization: (str) Tham số `authorization`.

    Returns:
        (str) Kết quả trả về."""
    return authorization.removeprefix("Bearer ").strip()


def _parse_dt(s: str) -> datetime:
    """(Nội bộ) Phân tích dt.

    Args:
        s: (str) Tham số `s`.

    Returns:
        (datetime) Kết quả trả về."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


@router.get("/history/admin/stats")
async def admin_session_stats(days: int = 7):
    """Admin session stats (async).

    Args:
        days: (int, mặc định 7) Tham số `days`."""
    try:
        data = await chat_repo.session_stats(days=days)
    except Exception as e:
        logger.error("[history] admin_session_stats failed: %s", e, exc_info=True)
        raise AiLayerError(str(e), cause=e) from e
    return ApiResponse.ok(data)


@router.get("/history/sessions")
async def list_sessions(authorization: str = Header(...)):
    """List sessions (async).

    Args:
        authorization: (str, mặc định Header(...)) Tham số `authorization`."""
    try:
        user_id = await get_user_id(_parse_token(authorization))
    except AiLayerAuthError:
        raise
    except Exception as e:
        logger.error("[history] list_sessions auth failed: %s", e, exc_info=True)
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
        logger.error("[history] list_sessions db failed: %s", e, exc_info=True)
        raise AiLayerError(str(e), cause=e) from e
    data = [
        {"id": r.id, "title": r.title, "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat()}
        for r in rows
    ]
    if redis:
        await redis.setex(key, HISTORY_SESSIONS_TTL, json.dumps(data))
    return ApiResponse.ok(data)


@router.post("/history/sessions")
async def upsert_session(body: SessionUpsert, authorization: str = Header(...)):
    """Upsert session (async).

    Args:
        body: (SessionUpsert) Tham số `body`.
        authorization: (str, mặc định Header(...)) Tham số `authorization`."""
    user_id = await get_user_id(_parse_token(authorization))
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
async def patch_session(session_id: str, body: SessionPatch, authorization: str = Header(...)):
    """Patch session (async).

    Args:
        session_id: (str) Tham số `session_id`.
        body: (SessionPatch) Tham số `body`.
        authorization: (str, mặc định Header(...)) Tham số `authorization`."""
    user_id = await get_user_id(_parse_token(authorization))
    owner_id = await chat_repo.get_session_user_id(session_id)
    if owner_id != user_id:
        raise AiLayerNotFoundError("Không tìm thấy phiên chat", message_key="errors.session_not_found")
    await chat_repo.patch_session(session_id, title=body.title)
    await _bust_sessions(await get_redis(), user_id)
    return ApiResponse.ok({"id": session_id})


@router.delete("/history/sessions/{session_id}")
async def delete_session(session_id: str, authorization: str = Header(...)):
    """Delete session (async).

    Args:
        session_id: (str) Tham số `session_id`.
        authorization: (str, mặc định Header(...)) Tham số `authorization`."""
    user_id = await get_user_id(_parse_token(authorization))
    owner_id = await chat_repo.get_session_user_id(session_id)
    if owner_id != user_id:
        raise AiLayerNotFoundError("Không tìm thấy phiên chat", message_key="errors.session_not_found")
    await chat_repo.delete_session(session_id)
    redis = await get_redis()
    await _bust_sessions(redis, user_id)
    await _bust_messages(redis, session_id)
    return ApiResponse.ok({"deleted": session_id})


@router.get("/history/sessions/{session_id}/messages")
async def get_messages(session_id: str, authorization: str = Header(...)):
    """Lấy messages (async).

    Args:
        session_id: (str) Tham số `session_id`.
        authorization: (str, mặc định Header(...)) Tham số `authorization`."""
    user_id = await get_user_id(_parse_token(authorization))
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
async def save_messages(session_id: str, body: list[MessageSave], authorization: str = Header(...)):
    """Save messages (async).

    Args:
        session_id: (str) Tham số `session_id`.
        body: (list[MessageSave]) Tham số `body`.
        authorization: (str, mặc định Header(...)) Tham số `authorization`."""
    user_id = await get_user_id(_parse_token(authorization))
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
