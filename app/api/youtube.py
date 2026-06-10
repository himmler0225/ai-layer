from fastapi import APIRouter, Depends, HTTPException, Query
from app.middleware.auth import verify_api_key
from app.processors import youtube as processor
from app.schemas.response import ApiResponse

router = APIRouter(prefix="/youtube", dependencies=[Depends(verify_api_key)])

@router.get("/videos/{video_id}/summary")
async def summarize_video(video_id: str):
    try:
        return ApiResponse.ok(await processor.summarize_video(video_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/videos/{video_id}/comments/analysis")
async def analyze_comments(video_id: str):
    try:
        return ApiResponse.ok(await processor.analyze_comments(video_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trending/analysis")
async def analyze_trends(limit: int = Query(20, ge=5, le=50)):
    try:
        return ApiResponse.ok(await processor.analyze_trends(limit=limit))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
