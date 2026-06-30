from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field
EXCHANGE_NAME = 'knowledge.ingest'
DLX_NAME = 'knowledge.ingest.dlx'
DLQ_NAME = 'ingest.dlq'
ROUTING_VIDEO = 'video.upsert'
ROUTING_COMMENTS = 'comments.upsert'
ROUTING_TRANSCRIPT = 'transcript.upsert'
ROUTING_EMBED = 'chunks.embed'
QUEUE_VIDEO = 'ingest.video'
QUEUE_COMMENTS = 'ingest.comments'
QUEUE_TRANSCRIPT = 'ingest.transcript'
QUEUE_EMBED = 'ingest.embed'
ROUTING_SUMMARIZE = 'movie.summarize'
QUEUE_SUMMARIZE = 'ingest.summarize'
Platform = Literal['youtube', 'tiktok']

class IngestEnvelope(BaseModel):
    """    Lớp `IngestEnvelope` (kế thừa BaseModel)."""
    job_id: str
    routing_key: str
    platform: Platform
    video_id: str = ''
    movie_hint: str = ''
    payload: dict[str, Any] = Field(default_factory=dict)
    fetched_at: str = ''

class ChunkItem(BaseModel):
    """    Lớp `ChunkItem` (kế thừa BaseModel)."""
    id: str
    content: str
    chunk_type: str = 'text'
    metadata: dict[str, Any] = Field(default_factory=dict)
