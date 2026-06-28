from __future__ import annotations

"""CRUD lịch sử chat Postgres."""


from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert

from app.config.db.models import ChatMessage, ChatSession
from app.config.db.session import get_session_factory


async def list_sessions(user_id: str) -> list[ChatSession]:
    """Lấy tất cả phiên chat của user, mới nhất trước."""
    factory = await get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
        )
        return list(result.scalars().all())


async def get_session_user_id(session_id: str) -> str | None:
    """Lấy user_id sở hữu session (để kiểm tra quyền)."""
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
    """Tạo mới hoặc cập nhật phiên chat."""
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
    """Cập nhật title hoặc updated_at của session."""
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
    """Xóa phiên chat (cascade message)."""
    factory = await get_session_factory()
    async with factory() as session:
        await session.execute(delete(ChatSession).where(ChatSession.id == session_id))
        await session.commit()


async def list_messages(session_id: str) -> list[ChatMessage]:
    """Lấy message trong session theo thứ tự thời gian."""
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
    """Lưu batch message, bỏ qua nếu trùng id."""
    if not messages:
        return

    factory = await get_session_factory()
    async with factory() as session:
        stmt = insert(ChatMessage).on_conflict_do_nothing(
            index_elements=[ChatMessage.id]
        )
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


async def session_stats(days: int = 7) -> dict:
    """Thống kê session theo ngày cho admin dashboard."""
    days = max(1, min(int(days), 30))
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    range_start = today_start - timedelta(days=days - 1)

    factory = await get_session_factory()
    async with factory() as session:
        sessions_today = await session.scalar(
            select(func.count())
            .select_from(ChatSession)
            .where(ChatSession.created_at >= today_start)
        )
        total_sessions = await session.scalar(
            select(func.count()).select_from(ChatSession)
        )

        day_col = func.date_trunc("day", ChatSession.created_at).label("day")
        rows = await session.execute(
            select(day_col, func.count().label("cnt"))
            .where(ChatSession.created_at >= range_start)
            .group_by(day_col)
            .order_by(day_col)
        )
        by_day: dict[date, int] = {
            row.day.date(): int(row.cnt) for row in rows if row.day is not None
        }

    daily: list[dict] = []
    for offset in range(days):
        d = (range_start + timedelta(days=offset)).date()
        daily.append(
            {
                "date": d.isoformat(),
                "label": d.strftime("%d/%m"),
                "count": by_day.get(d, 0),
            }
        )

    return {
        "sessionsToday": int(sessions_today or 0),
        "totalSessions": int(total_sessions or 0),
        "daily": daily,
    }
