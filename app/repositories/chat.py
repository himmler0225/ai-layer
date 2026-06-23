from __future__ import annotations

from datetime import datetime, timezone

from typing import Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert

from app.db.models import ChatMessage, ChatSession
from app.db.session import get_session_factory


async def list_sessions(user_id: str) -> list[ChatSession]:
    factory = await get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
        )
        return list(result.scalars().all())


async def get_session_user_id(session_id: str) -> str | None:
    factory = await get_session_factory()
    async with factory() as session:
        return await session.scalar(
            select(ChatSession.user_id).where(ChatSession.id == session_id)
        )


async def upsert_session(
    *,
    session_id: str,
    user_id: str,
    title: str,
    created_at: datetime,
    updated_at: datetime,
) -> None:
    factory = await get_session_factory()
    async with factory() as session:
        stmt = insert(ChatSession).values(
            id=session_id,
            user_id=user_id,
            title=title,
            created_at=created_at,
            updated_at=updated_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ChatSession.id],
            set_={
                "title": stmt.excluded.title,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await session.execute(stmt)
        await session.commit()


async def patch_session(
    session_id: str,
    *,
    title: Optional[str] = None,
) -> None:
    values: dict = {"updated_at": datetime.now(timezone.utc)}
    if title is not None:
        values["title"] = title

    factory = await get_session_factory()
    async with factory() as session:
        await session.execute(
            update(ChatSession).where(ChatSession.id == session_id).values(**values)
        )
        await session.commit()


async def delete_session(session_id: str) -> None:
    factory = await get_session_factory()
    async with factory() as session:
        await session.execute(delete(ChatSession).where(ChatSession.id == session_id))
        await session.commit()


async def list_messages(session_id: str) -> list[ChatMessage]:
    factory = await get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        return list(result.scalars().all())


async def save_messages(
    session_id: str,
    messages: list[dict],
) -> None:
    if not messages:
        return

    factory = await get_session_factory()
    async with factory() as session:
        stmt = insert(ChatMessage).on_conflict_do_nothing(index_elements=[ChatMessage.id])
        await session.execute(
            stmt,
            [
                {
                    "id": msg["id"],
                    "session_id": session_id,
                    "role": msg["role"],
                    "content": msg["content"],
                    "metadata_": msg.get("metadata"),
                    "created_at": msg["created_at"],
                }
                for msg in messages
            ],
        )
        await session.execute(
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(updated_at=func.now())
        )
        await session.commit()
