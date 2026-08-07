from fastapi import APIRouter, Depends, Query, Request
from app.config.rate_limits import youtube_rate_limit
from app.middleware.auth import verify_api_key
from app.middleware.rate_limit import limiter
import app.processors.youtube as processor
from app.schemas.response import ApiResponse

router = APIRouter(prefix="/youtube", dependencies=[Depends(verify_api_key)])


@router.get("/videos/{video_id}/summary")
@limiter.limit(youtube_rate_limit)
async def summarize_video(request: Request, video_id: str):
    """Generate an AI summary of a YouTube video.

    Args:
        request: Incoming request, used for rate limiting.
        video_id: YouTube video id to summarize."""
    return ApiResponse.ok(await processor.summarize_video(video_id))


@router.get("/videos/{video_id}/comments/analysis")
@limiter.limit(youtube_rate_limit)
async def analyze_comments(request: Request, video_id: str):
    """Analyze the comments on a YouTube video.

    Args:
        request: Incoming request, used for rate limiting.
        video_id: YouTube video id whose comments should be analyzed."""
    return ApiResponse.ok(await processor.analyze_comments(video_id))


@router.get("/trending/analysis")
@limiter.limit(youtube_rate_limit)
async def analyze_trends(request: Request, limit: int = Query(20, ge=5, le=50)):
    """Analyze currently trending YouTube videos.

    Args:
        request: Incoming request, used for rate limiting.
        limit: Maximum number of trending videos to analyze (5-50, default 20)."""
    return ApiResponse.ok(await processor.analyze_trends(limit=limit))
