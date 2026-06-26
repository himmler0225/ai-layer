from __future__ import annotations

"""ORM videos, comments, video_chunks (pgvector)."""


from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base
from app.db.models.vector_dim import embedding_vector


class Video(Base):
    """Metadata video YouTube/TikTok."""

    __tablename__ = "videos"
    __table_args__ = (
        CheckConstraint(
            "platform IN ('youtube', 'tiktok')",
            name="videos_platform_check",
        ),
        Index("videos_platform", "platform"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    views: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    likes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    comments_count: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Comment(Base):
    """Comment của video."""

    __tablename__ = "comments"
    __table_args__ = (Index("comments_video_id", "video_id"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    video_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    )
    author: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    likes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )


class VideoChunk(Base):
    """Đoạn text + vector embedding cho RAG."""

    __tablename__ = "video_chunks"
    __table_args__ = (
        CheckConstraint(
            "platform IN ('youtube', 'tiktok')",
            name="video_chunks_platform_check",
        ),
        Index("video_chunks_video_id", "video_id"),
        Index(
            "video_chunks_embedding_idx",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    video_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    embedding: Mapped[Optional[list]] = mapped_column(embedding_vector(), nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
