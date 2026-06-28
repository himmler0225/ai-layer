from __future__ import annotations

"""ORM cache kết quả search theo query."""


from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.config.db.models.base import Base


class SearchCache(Base):
    """Cache video_ids theo query search."""

    __tablename__ = "search_cache"

    query: Mapped[str] = mapped_column(Text, primary_key=True)
    platform: Mapped[str] = mapped_column(Text, primary_key=True)
    video_ids: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
