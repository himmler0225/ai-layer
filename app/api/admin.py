"""API admin — monitoring ingest, thống kê nội bộ."""

from fastapi import APIRouter, Depends, HTTPException

from app.ingest.monitor import get_ingest_queue_stats
from app.middleware.auth import verify_api_key
from app.schemas.response import ApiResponse
from app.services.health import collect_checks, is_healthy

router = APIRouter(prefix="/admin", dependencies=[Depends(verify_api_key)])


@router.get("/health/detail")
async def health_detail():
    """Health đầy đủ — giống /health nhưng cần API key."""
    checks = await collect_checks()
    return ApiResponse.ok({
        "service": "ai-layer",
        "healthy": is_healthy(checks),
        "checks": checks,
    })


@router.get("/ingest/queues")
async def ingest_queues():
    """Độ sâu queue ingest + số message trong DLQ."""
    try:
        return ApiResponse.ok(await get_ingest_queue_stats())
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
