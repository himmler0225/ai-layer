from typing import Any, Literal
from pydantic import BaseModel, Field

ROUTING_VIDEO = "video.upsert"
ROUTING_COMMENTS = "comments.upsert"
ROUTING_TRANSCRIPT = "transcript.upsert"
ROUTING_EMBED = "chunks.embed"
ROUTING_SUMMARIZE = "movie.summarize"
Platform = Literal["youtube", "tiktok"]


class IngestEnvelope(BaseModel):
    """Message envelope passed through the in-process ingest pipeline.

    Carries a routing key selecting the handler, the source platform/video/movie
    context, and the handler-specific payload.
    """

    job_id: str
    routing_key: str
    platform: Platform
    video_id: str = ""
    movie_hint: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    fetched_at: str = ""


class ChunkItem(BaseModel):
    """A single embeddable text chunk (transcript or comment) awaiting embedding."""

    id: str
    content: str
    chunk_type: str = "text"
    metadata: dict[str, Any] = Field(default_factory=dict)
