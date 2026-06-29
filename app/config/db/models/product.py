from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, SmallInteger, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.config.db.models.base import Base
from app.config.db.models.vector_dim import embedding_vector

class Product(Base):
    """    Lớp `Product` (kế thừa Base)."""
    __tablename__ = 'products'
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column('metadata', JSONB, nullable=False, server_default='{}')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class RawReview(Base):
    """    Lớp `RawReview` (kế thừa Base)."""
    __tablename__ = 'raw_reviews'
    __table_args__ = (Index('raw_reviews_product_id_idx', 'product_id'), Index('raw_reviews_product_likes_idx', 'product_id', 'likes'))
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_id: Mapped[str] = mapped_column(Text, ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_video_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    likes: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    metadata_: Mapped[dict] = mapped_column('metadata', JSONB, nullable=False, server_default='{}')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class CuratedReview(Base):
    """    Lớp `CuratedReview` (kế thừa Base)."""
    __tablename__ = 'curated_reviews'
    __table_args__ = (UniqueConstraint('product_id', 'raw_review_id', name='curated_reviews_product_raw_uq'), Index('curated_reviews_product_rank_idx', 'product_id', 'rank'))
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_id: Mapped[str] = mapped_column(Text, ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    raw_review_id: Mapped[str] = mapped_column(Text, ForeignKey('raw_reviews.id', ondelete='CASCADE'), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    likes: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class AspectChunk(Base):
    """    Lớp `AspectChunk` (kế thừa Base)."""
    __tablename__ = 'aspect_chunks'
    __table_args__ = (Index('aspect_chunks_product_aspect_idx', 'product_id', 'aspect'), Index('aspect_chunks_embedding_idx', 'embedding', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'}))
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_id: Mapped[str] = mapped_column(Text, ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    aspect: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    review_ids: Mapped[list] = mapped_column(JSONB, nullable=False, server_default='[]')
    positive_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    negative_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    embedding: Mapped[Optional[list]] = mapped_column(embedding_vector(), nullable=True)
    metadata_: Mapped[dict] = mapped_column('metadata', JSONB, nullable=False, server_default='{}')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class AspectSummary(Base):
    """    Lớp `AspectSummary` (kế thừa Base)."""
    __tablename__ = 'aspect_summaries'
    __table_args__ = (UniqueConstraint('product_id', 'aspect', name='aspect_summaries_product_aspect_uq'), Index('aspect_summaries_product_aspect_idx', 'product_id', 'aspect'), Index('aspect_summaries_embedding_idx', 'embedding', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'}))
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    product_id: Mapped[str] = mapped_column(Text, ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    aspect: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    pros: Mapped[list] = mapped_column(JSONB, nullable=False, server_default='[]')
    cons: Mapped[list] = mapped_column(JSONB, nullable=False, server_default='[]')
    positive_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_chunk_ids: Mapped[list] = mapped_column(JSONB, nullable=False, server_default='[]')
    embedding: Mapped[Optional[list]] = mapped_column(embedding_vector(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
