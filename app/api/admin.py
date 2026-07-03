from fastapi import APIRouter, Depends
from app.exceptions import AiLayerServiceUnavailableError
from app.ingest.monitor import get_ingest_queue_stats
from app.middleware.auth import verify_api_key
from app.schemas.response import ApiResponse
from app.services.health import collect_checks, is_healthy

router = APIRouter(prefix="/admin", dependencies=[Depends(verify_api_key)])


@router.get("/health/detail")
async def health_detail():
    """Health detail (async)."""
    checks = await collect_checks()
    return ApiResponse.ok({"service": "ai-layer", "healthy": is_healthy(checks), "checks": checks})


@router.get("/ingest/queues")
async def ingest_queues():
    """Ingest queues (async)."""
    try:
        return ApiResponse.ok(await get_ingest_queue_stats())
    except Exception as exc:
        raise AiLayerServiceUnavailableError(str(exc), cause=exc) from exc
