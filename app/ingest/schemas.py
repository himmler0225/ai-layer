from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator

ROUTING_VIDEO = "video.upsert"
ROUTING_COMMENTS = "comments.upsert"
ROUTING_TRANSCRIPT = "transcript.upsert"
ROUTING_EMBED = "chunks.embed"
ROUTING_SUMMARIZE = "movie.summarize"
Platform = Literal["youtube", "tiktok"]
ASPECTS = ["battery", "camera", "screen", "performance", "design", "price", "software", "durability", "other"]


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


class AspectGroupItem(BaseModel):
    """One aspect bucket (battery, camera, etc.) grouped from curated reviews."""

    aspect: str
    review_ids: list[str] = Field(default_factory=list)
    content: str
    positive_percent: float | None = None
    negative_percent: float | None = None

    @field_validator("aspect")
    @classmethod
    def _normalize_aspect(cls, v: str) -> str:
        aspect = v.lower().strip()
        return aspect if aspect in ASPECTS else "other"


class AspectGroupsResult(BaseModel):
    """LLM response shape for grouping curated reviews into aspect buckets."""

    groups: list[AspectGroupItem] = Field(default_factory=list)


class AspectSummaryResult(BaseModel):
    """LLM response shape for summarizing one aspect's grouped review content."""

    summary: str
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    positive_percent: float | None = None
