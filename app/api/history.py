from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.auth.supabase import get_user_id
from app.cache.client import get_redis
from app.config.settings import HISTORY_SESSIONS_TTL, HISTORY_MESSAGES_TTL
from app.db.base import get_pool
from app.middleware.auth import verify_api_key
from app.schemas.response import ApiResponse
from app.config.logger import Logger

logger = Logger.get(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])

class SessionUpsert(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str

class SessionPatch(BaseModel):
    title: Optional[str] = None

class MessageSave(BaseModel):
    id: str
    role: str
    content: str
    metadata: Optional[dict] = None
    created_at: str

async def _bust_sessions(redis, user_id: str) -> None:
    if redis:
        await redis.delete(f"history:sessions:{user_id}")

async def _bust_messages(redis, session_id: str) -> None:
    if redis:
        await redis.delete(f"history:messages:{session_id}")

def _parse_token(authorization: str) -> str:
    return authorization.removeprefix("Bearer ").strip()

def _parse_dt(s: str) -> datetime:
    """Parse ISO datetime — handles both 'Z' (JS) and '+00:00' (Python) suffixes."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

@router.get("/history/sessions")
async def list_sessions(authorization: str = Header(...)):
    try:
        user_id = await get_user_id(_parse_token(authorization))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_sessions auth failed: %s", e, exc_info=True)
        raise HTTPException(500, str(e))
    redis = await get_redis()
    key = f"history:sessions:{user_id}"

    if redis:
        cached = await redis.get(key)
        if cached:
            return ApiResponse.ok(json.loads(cached))

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, title, created_at, updated_at FROM chat_sessions "
                "WHERE user_id = $1 ORDER BY updated_at DESC",
                user_id,
            )
    except Exception as e:
        logger.error("list_sessions db failed: %s", e, exc_info=True)
        raise HTTPException(500, str(e))

    data = [
        {
            "id": r["id"],
            "title": r["title"],
            "created_at": r["created_at"].isoformat(),
            "updated_at": r["updated_at"].isoformat(),
        }
        for r in rows
    ]

    if redis:
        await redis.setex(key, HISTORY_SESSIONS_TTL, json.dumps(data))

    return ApiResponse.ok(data)

@router.post("/history/sessions")
async def upsert_session(body: SessionUpsert, authorization: str = Header(...)):
    user_id = await get_user_id(_parse_token(authorization))

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (id) DO UPDATE
              SET title = EXCLUDED.title, updated_at = EXCLUDED.updated_at
            """,
            body.id,
            user_id,
            body.title,
            _parse_dt(body.created_at),
            _parse_dt(body.updated_at),
        )

    await _bust_sessions(await get_redis(), user_id)
    return ApiResponse.ok({"id": body.id})

@router.patch("/history/sessions/{session_id}")
async def patch_session(session_id: str, body: SessionPatch, authorization: str = Header(...)):
    user_id = await get_user_id(_parse_token(authorization))

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT user_id FROM chat_sessions WHERE id = $1", session_id)
        if not row or row["user_id"] != user_id:
            raise HTTPException(404, "Session not found")

        sets, params = ["updated_at = $2"], [session_id, datetime.now(timezone.utc)]
        if body.title is not None:
            params.append(body.title)
            sets.append(f"title = ${len(params)}")

        await conn.execute(
            f"UPDATE chat_sessions SET {', '.join(sets)} WHERE id = $1", *params
        )

    await _bust_sessions(await get_redis(), user_id)
    return ApiResponse.ok({"id": session_id})

@router.delete("/history/sessions/{session_id}")
async def delete_session(session_id: str, authorization: str = Header(...)):
    user_id = await get_user_id(_parse_token(authorization))

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT user_id FROM chat_sessions WHERE id = $1", session_id)
        if not row or row["user_id"] != user_id:
            raise HTTPException(404, "Session not found")
        await conn.execute("DELETE FROM chat_sessions WHERE id = $1", session_id)

    redis = await get_redis()
    await _bust_sessions(redis, user_id)
    await _bust_messages(redis, session_id)
    return ApiResponse.ok({"deleted": session_id})

@router.get("/history/sessions/{session_id}/messages")
async def get_messages(session_id: str, authorization: str = Header(...)):
    user_id = await get_user_id(_parse_token(authorization))
    redis = await get_redis()
    key = f"history:messages:{session_id}"

    if redis:
        cached = await redis.get(key)
        if cached:
            return ApiResponse.ok(json.loads(cached))

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT user_id FROM chat_sessions WHERE id = $1", session_id)
        if not row or row["user_id"] != user_id:
            raise HTTPException(404, "Session not found")

        msgs = await conn.fetch(
            "SELECT id, role, content, metadata, created_at FROM chat_messages "
            "WHERE session_id = $1 ORDER BY created_at ASC",
            session_id,
        )

    data = [
        {
            "id": m["id"],
            "role": m["role"],
            "content": m["content"],
            "metadata": m["metadata"],  # auto-decoded by pool init codec
            "created_at": m["created_at"].isoformat(),
        }
        for m in msgs
    ]

    if redis:
        await redis.setex(key, HISTORY_MESSAGES_TTL, json.dumps(data))

    return ApiResponse.ok(data)

@router.post("/history/sessions/{session_id}/messages")
async def save_messages(session_id: str, body: list[MessageSave], authorization: str = Header(...)):
    user_id = await get_user_id(_parse_token(authorization))

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT user_id FROM chat_sessions WHERE id = $1", session_id)
        if not row or row["user_id"] != user_id:
            raise HTTPException(404, "Session not found")

        for msg in body:
            await conn.execute(
                """
                INSERT INTO chat_messages (id, session_id, role, content, metadata, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO NOTHING
                """,
                msg.id,
                session_id,
                msg.role,
                msg.content,
                msg.metadata,  # passed as dict, encoded by pool init codec
                _parse_dt(msg.created_at),
            )

        await conn.execute(
            "UPDATE chat_sessions SET updated_at = NOW() WHERE id = $1", session_id
        )

    redis = await get_redis()
    await _bust_messages(redis, session_id)
    await _bust_sessions(redis, user_id)
    return ApiResponse.ok({"saved": len(body)})
