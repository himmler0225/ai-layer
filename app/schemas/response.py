from datetime import datetime, UTC
from typing import Any
from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    """Standard response envelope returned by all API endpoints."""

    success: bool
    data: Any = None
    error: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def ok(cls, data: Any = None, **meta: Any) -> ApiResponse:
        """Build a successful response envelope.

        Args:
            data: Payload to return to the client.
            meta: Extra metadata fields merged in alongside the timestamp.

        Returns:
            ApiResponse with success=True."""
        return cls(success=True, data=data, meta={"timestamp": _ts(), **meta})

    @classmethod
    def fail(cls, error: str, **meta: Any) -> ApiResponse:
        """Build a failure response envelope.

        Args:
            error: Human-readable error message for the client.
            meta: Extra metadata fields merged in alongside the timestamp.

        Returns:
            ApiResponse with success=False."""
        return cls(success=False, error=error, meta={"timestamp": _ts(), **meta})


def _ts() -> str:
    """Return the current UTC time as an ISO-8601 string, used for response timestamps."""
    return datetime.now(UTC).isoformat()
