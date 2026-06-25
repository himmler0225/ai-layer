from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# RabbitMQ topology — xem broker/README.md
EXCHANGE_NAME = "knowledge.ingest"
DLX_NAME = "knowledge.ingest.dlx"
DLQ_NAME = "ingest.dlq"

ROUTING_VIDEO = "video.upsert"
ROUTING_COMMENTS = "comments.upsert"
ROUTING_TRANSCRIPT = "transcript.upsert"
ROUTING_EMBED = "chunks.embed"

QUEUE_VIDEO = "ingest.video"
QUEUE_COMMENTS = "ingest.comments"
QUEUE_TRANSCRIPT = "ingest.transcript"
QUEUE_EMBED = "ingest.embed"

ROUTING_SUMMARIZE = "product.summarize"
QUEUE_SUMMARIZE = "ingest.summarize"

Platform = Literal["youtube", "tiktok"]


class IngestEnvelope(BaseModel):
    """Message JSON gửi qua RabbitMQ."""

    job_id: str
    routing_key: str
    platform: Platform
    video_id: str = ""
    product_hint: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    fetched_at: str = ""


class ChunkItem(BaseModel):
    """Một đoạn text trước khi embed."""

    id: str
    content: str
    chunk_type: str = "text"
    metadata: dict[str, Any] = Field(default_factory=dict)
