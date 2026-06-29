from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class ApiResponse(BaseModel):
    """    Lớp `ApiResponse` (kế thừa BaseModel)."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def ok(cls, data: Any=None, **meta: Any) -> ApiResponse:
        """Ok `ok`.

    Args:
        data: (Any) Tham số `data`.
        meta: (Any, mặc định None) Tham số `meta`.

    Returns:
        (ApiResponse) Kết quả trả về."""
        return cls(success=True, data=data, meta={'timestamp': _ts(), **meta})

    @classmethod
    def fail(cls, error: str, **meta: Any) -> ApiResponse:
        """Fail `fail`.

    Args:
        error: (str) Tham số `error`.
        meta: (Any) Tham số `meta`.

    Returns:
        (ApiResponse) Kết quả trả về."""
        return cls(success=False, error=error, meta={'timestamp': _ts(), **meta})

def _ts() -> str:
    """(Nội bộ) Ts `_ts`.

    Returns:
        (str) Kết quả trả về."""
    return datetime.now(timezone.utc).isoformat()
