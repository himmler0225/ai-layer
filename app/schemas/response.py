from __future__ import annotations

"""Wrapper JSON ApiResponse chuẩn."""


from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class ApiResponse(BaseModel):
    """Envelope JSON chuẩn {success, data, error, meta}."""

    success: bool
    data:    Any                    = None
    error:   Optional[str]          = None
    meta:    Dict[str, Any]         = Field(default_factory=dict)

    @classmethod
    def ok(cls, data: Any = None, **meta: Any) -> ApiResponse:
        """Tạo response thành công kèm timestamp."""
        return cls(
            success=True,
            data=data,
            meta={"timestamp": _ts(), **meta},
        )

    @classmethod
    def fail(cls, error: str, **meta: Any) -> ApiResponse:
        """Tạo response lỗi kèm timestamp."""
        return cls(
            success=False,
            error=error,
            meta={"timestamp": _ts(), **meta},
        )

def _ts() -> str:
    """Thời điểm UTC dạng ISO cho trường meta."""
    return datetime.now(timezone.utc).isoformat()