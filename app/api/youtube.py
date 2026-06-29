from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.config.rate_limits import youtube_rate_limit
from app.middleware.auth import verify_api_key
from app.middleware.rate_limit import limiter
import app.processors.youtube as processor
from app.schemas.response import ApiResponse
router = APIRouter(prefix='/youtube', dependencies=[Depends(verify_api_key)])

@router.get('/videos/{video_id}/summary')
@limiter.limit(youtube_rate_limit)
async def summarize_video(request: Request, video_id: str):
    """Tóm tắt video (async).

    Args:
        request: (Request) Tham số `request`.
        video_id: (str) Tham số `video_id`."""
    try:
        return ApiResponse.ok(await processor.summarize_video(video_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/videos/{video_id}/comments/analysis')
@limiter.limit(youtube_rate_limit)
async def analyze_comments(request: Request, video_id: str):
    """Analyze comments (async).

    Args:
        request: (Request) Tham số `request`.
        video_id: (str) Tham số `video_id`."""
    try:
        return ApiResponse.ok(await processor.analyze_comments(video_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/trending/analysis')
@limiter.limit(youtube_rate_limit)
async def analyze_trends(request: Request, limit: int=Query(20, ge=5, le=50)):
    """Analyze trends (async).

    Args:
        request: (Request) Tham số `request`.
        limit: (int, mặc định Query(20, ge=5, le=50)) Tham số `limit`."""
    try:
        return ApiResponse.ok(await processor.analyze_trends(limit=limit))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
