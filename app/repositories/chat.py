from datetime import date, datetime, timedelta, UTC
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from app.config.db.models import ChatMessage, ChatSession
from app.config.db.session import get_session_factory


async def list_sessions(user_id: str) -> list[ChatSession]:
    """List a user's chat sessions, most recently updated first.

    Args:
        user_id: The user's id.

    Returns:
        The user's `ChatSession` rows.
    """
    factory = await get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.updated_at.desc())
        )
        return list(result.scalars().all())


async def get_session_user_id(session_id: str) -> str | None:
    """Look up the owning user id for a chat session.

    Args:
        session_id: The session's id.

    Returns:
        The owning user's id, or None if the session doesn't exist.
    """
    factory = await get_session_factory()
    async with factory() as session:
        return await session.scalar(select(ChatSession.user_id).where(ChatSession.id == session_id))


async def upsert_session(
    *, session_id: str, user_id: str, title: str, created_at: datetime, updated_at: datetime
) -> None:
    """Insert a chat session, or update its title/updated_at if it already exists.

    Args:
        session_id: The session's id.
        user_id: Id of the user who owns the session.
        title: Session title.
        created_at: Creation timestamp (used only on insert).
        updated_at: Timestamp to set on insert or conflict.
    """
    factory = await get_session_factory()
    async with factory() as session:
        stmt = insert(ChatSession).values(
            id=session_id, user_id=user_id, title=title, created_at=created_at, updated_at=updated_at
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ChatSession.id], set_={"title": stmt.excluded.title, "updated_at": stmt.excluded.updated_at}
        )
        await session.execute(stmt)
        await session.commit()


async def patch_session(session_id: str, *, title: str | None = None) -> None:
    """Partially update a chat session, always bumping updated_at.

    Args:
        session_id: The session's id.
        title: New title to set; left unchanged if None.
    """
    values: dict = {"updated_at": datetime.now(UTC)}
    if title is not None:
        values["title"] = title
    factory = await get_session_factory()
    async with factory() as session:
        await session.execute(update(ChatSession).where(ChatSession.id == session_id).values(**values))
        await session.commit()


async def delete_session(session_id: str) -> None:
    """Delete a chat session by id.

    Args:
        session_id: The session's id.
    """
    factory = await get_session_factory()
    async with factory() as session:
        await session.execute(delete(ChatSession).where(ChatSession.id == session_id))
        await session.commit()


async def list_messages(session_id: str) -> list[ChatMessage]:
    """List a chat session's messages in chronological order.

    Args:
        session_id: The session's id.

    Returns:
        The session's `ChatMessage` rows, oldest first.
    """
    factory = await get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
        )
        return list(result.scalars().all())


async def save_messages(session_id: str, messages: list[dict]) -> None:
    """Append new messages to a session and bump the session's updated_at.

    Existing message ids are ignored (no-op on conflict), so this is safe
    to call with messages that may have already been saved.

    Args:
        session_id: The session to append messages to.
        messages: Message dicts with "id", "role", "content", optional
            "metadata", and "created_at".
    """
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
        await session.execute(update(ChatSession).where(ChatSession.id == session_id).values(updated_at=func.now()))
        await session.commit()


async def session_stats(days: int = 7) -> dict:
    """Compute chat session counts for a dashboard: today's total, all-time total, and a daily breakdown.

    Args:
        days: Number of trailing days (including today) to include in the
            daily breakdown; clamped to the range [1, 30].

    Returns:
        A dict with "sessionsToday" (int), "totalSessions" (int), and
        "daily" (list of {"date", "label", "count"} dicts, one per day in
        the requested range, oldest first).
    """
    days = max(1, min(int(days), 30))
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    range_start = today_start - timedelta(days=days - 1)
    factory = await get_session_factory()
    async with factory() as session:
        sessions_today = await session.scalar(
            select(func.count()).select_from(ChatSession).where(ChatSession.created_at >= today_start)
        )
        total_sessions = await session.scalar(select(func.count()).select_from(ChatSession))
        day_col = func.date_trunc("day", ChatSession.created_at).label("day")
        rows = await session.execute(
            select(day_col, func.count().label("cnt"))
            .where(ChatSession.created_at >= range_start)
            .group_by(day_col)
            .order_by(day_col)
        )
        by_day: dict[date, int] = {row.day.date(): int(row.cnt) for row in rows if row.day is not None}
    daily: list[dict] = []
    for offset in range(days):
        d = (range_start + timedelta(days=offset)).date()
        daily.append({"date": d.isoformat(), "label": d.strftime("%d/%m"), "count": by_day.get(d, 0)})
    return {"sessionsToday": int(sessions_today or 0), "totalSessions": int(total_sessions or 0), "daily": daily}
